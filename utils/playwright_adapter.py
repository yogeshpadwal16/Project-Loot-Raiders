import time
import logging
import random
import threading
from rebrowser_playwright.sync_api import sync_playwright

playwright_lock = threading.Lock()

class PlaywrightElementAdapter:
    def __init__(self, locator):
        self.locator = locator

    @property
    def text(self):
        try:
            return self.locator.inner_text().strip()
        except Exception as e:
            return ""

    def inner_text(self):
        try:
            return self.locator.inner_text()
        except Exception:
            return ""

    @property
    def tag_name(self):
        try:
            return self.locator.evaluate("el => el.tagName.toLowerCase()")
        except Exception:
            return ""

    def get_attribute(self, attr):
        try:
            if attr == "textContent":
                return self.locator.text_content()
            elif attr == "outerHTML":
                return self.locator.evaluate("el => el.outerHTML")
            elif attr == "innerHTML":
                return self.locator.evaluate("el => el.innerHTML")
            elif attr == "href":
                try: return self.locator.evaluate("el => el.href")
                except Exception: pass
            elif attr == "src":
                try: return self.locator.evaluate("el => el.src")
                except Exception: pass
            return self.locator.get_attribute(attr)
        except Exception as e:
            return None

    def find_elements(self, by, selector):
        mapped_selector = self._map_selector(by, selector)
        try:
            sub_loc = self.locator.locator(mapped_selector)
            count = sub_loc.count()
            return [PlaywrightElementAdapter(sub_loc.nth(i)) for i in range(count)]
        except Exception as e:
            logging.debug(f"find_elements error on selector {selector}: {e}")
            return []

    def find_element(self, by, selector):
        mapped_selector = self._map_selector(by, selector)
        try:
            sub_loc = self.locator.locator(mapped_selector).first
            if sub_loc.count() == 0:
                raise Exception(f"Element not found: {selector}")
            return PlaywrightElementAdapter(sub_loc)
        except Exception as e:
            raise Exception(f"Element not found for selector {selector}: {e}")

    def _map_selector(self, by, selector):
        by_str = str(by).lower()
        if "xpath" in by_str:
            if not selector.startswith("xpath="):
                return f"xpath={selector}"
        return selector


class PlaywrightSeleniumAdapter:
    def __init__(self, playwright, browser, context, page):
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page
        self.switch_to = self
        self._window_handles = [page]
        self._timeout = 45000
        
        # Listen for dynamically opened pages
        self.context.on("page", self._on_new_page)

    def _on_new_page(self, new_page):
        if new_page not in self._window_handles:
            self._window_handles.append(new_page)

    @property
    def window_handles(self):
        try:
            # Sync with the active context pages
            self._window_handles = self.context.pages
        except Exception:
            pass
        return self._window_handles

    def window(self, handle):
        # Allow switching using index or page object reference
        if isinstance(handle, int):
            handles = self.window_handles
            if 0 <= handle < len(handles):
                self.page = handles[handle]
        else:
            if handle in self.window_handles:
                self.page = handle

    @property
    def title(self):
        try:
            return self.page.title()
        except Exception:
            return ""

    def set_page_load_timeout(self, timeout):
        # Convert seconds to milliseconds
        self._timeout = int(timeout * 1000)

    def get(self, url):
        self.page.goto(url, wait_until="domcontentloaded", timeout=self._timeout)
        time.sleep(1.0)

    def execute_script(self, script, *args):
        # If script requests opening a new window, emulate it via Playwright context
        if "window.open" in script:
            try:
                new_page = self.context.new_page()
                if new_page not in self._window_handles:
                    self._window_handles.append(new_page)
                return None
            except Exception as e:
                logging.warning(f"Failed to open window via execute_script: {e}")
                return None
        try:
            # Guard against operating on a closed page (prevents "Target closed" errors)
            if self.page.is_closed():
                logging.warning("execute_script called on a closed page, skipping.")
                return None

            # Selenium's execute_script() wraps code in a function body where 'return'
            # and 'arguments' are valid. Playwright's evaluate() expects an expression,
            # so bare 'return' causes SyntaxError. Detect and wrap in an IIFE to match
            # Selenium semantics.
            has_return = 'return ' in script or 'return;' in script

            if args:
                # Inject arguments as a local variable inside an IIFE so that
                # scripts using arguments[0], arguments[1] etc. work correctly
                import json as _json
                args_json = _json.dumps(list(args))
                wrapped = f"(() => {{ const arguments = {args_json}; {script} }})()"
                return self.page.evaluate(wrapped)
            elif has_return:
                wrapped = f"(() => {{ {script} }})()"
                return self.page.evaluate(wrapped)
            else:
                return self.page.evaluate(script)
        except Exception as e:
            logging.warning(f"execute_script error: {e}")
            return None

    def find_elements(self, by, selector):
        mapped_selector = self._map_selector(by, selector)
        try:
            locators = self.page.locator(mapped_selector)
            count = locators.count()
            return [PlaywrightElementAdapter(locators.nth(i)) for i in range(count)]
        except Exception as e:
            logging.error(f"find_elements page error on {selector}: {e}")
            return []

    def find_element(self, by, selector):
        mapped_selector = self._map_selector(by, selector)
        try:
            loc = self.page.locator(mapped_selector).first
            if loc.count() == 0:
                raise Exception(f"Element not found on page: {selector}")
            return PlaywrightElementAdapter(loc)
        except Exception as e:
            raise Exception(f"Element not found on page: {selector}: {e}")

    def select(self, selector):
        try:
            return self.find_element("css selector", selector)
        except Exception:
            return None

    def select_all(self, selector):
        try:
            return self.find_elements("css selector", selector)
        except Exception:
            return []

    def _map_selector(self, by, selector):
        by_str = str(by).lower()
        if "xpath" in by_str:
            if not selector.startswith("xpath="):
                return f"xpath={selector}"
        return selector

    def quit(self):
        try:
            if hasattr(self, 'page') and self.page:
                try: self.page.close()
                except Exception: pass
            if hasattr(self, 'context') and self.context:
                try: self.context.close()
                except Exception: pass
            if not getattr(self, '_is_shared', True):
                if hasattr(self, 'browser') and self.browser:
                    try: self.browser.close()
                    except Exception: pass
                if hasattr(self, 'playwright') and self.playwright:
                    try: self.playwright.stop()
                    except Exception: pass
        except Exception as e:
            logging.debug(f"Error closing Playwright elements: {e}")

    def close(self):
        try:
            self.page.close()
            # Remove from list
            if self.page in self._window_handles:
                self._window_handles.remove(self.page)
            # Rollback to first tab
            handles = self.window_handles
            if handles:
                self.page = handles[0]
        except Exception as e:
            logging.debug(f"Error closing current tab: {e}")


# Thread-Local Persistent Playwright Browser Manager
_THREAD_LOCAL = threading.local()

def _get_shared_browser(settings=None):
    """
    Returns the thread-isolated persistent Playwright Chromium browser instance,
    re-launching automatically if disconnected or uninitialized.
    """
    if hasattr(_THREAD_LOCAL, 'browser') and _THREAD_LOCAL.browser is not None:
        try:
            if _THREAD_LOCAL.browser.is_connected():
                return _THREAD_LOCAL.playwright, _THREAD_LOCAL.browser
        except Exception:
            pass
        _shutdown_shared_browser_internal()

    _THREAD_LOCAL.playwright = sync_playwright().start()
    browser_args = [
        "--headless=new",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--hide-scrollbars",
        "--metrics-recording-only",
        "--mute-audio",
        "--no-first-run",
        "--memory-pressure-off",
    ]

    proxy_config = None
    if settings and settings.get("proxies_enabled") and settings.get("proxy_list"):
        try:
            from utils.proxy_validator import get_next_working_proxy
            proxy_url = get_next_working_proxy(settings)
            if proxy_url:
                proxy_config = {"server": proxy_url}
                logging.info(f"Playwright launching using validated proxy: {proxy_url}")
        except Exception as pe:
            logging.error(f"Failed to resolve validated proxy: {pe}")

    _THREAD_LOCAL.browser = _THREAD_LOCAL.playwright.chromium.launch(
        headless=True,
        args=browser_args
    )
    return _THREAD_LOCAL.playwright, _THREAD_LOCAL.browser

def _shutdown_shared_browser_internal():
    if hasattr(_THREAD_LOCAL, 'browser') and _THREAD_LOCAL.browser is not None:
        try: _THREAD_LOCAL.browser.close()
        except Exception: pass
        _THREAD_LOCAL.browser = None
    if hasattr(_THREAD_LOCAL, 'playwright') and _THREAD_LOCAL.playwright is not None:
        try: _THREAD_LOCAL.playwright.stop()
        except Exception: pass
        _THREAD_LOCAL.playwright = None

def shutdown_shared_browser():
    """Cleanly shuts down the thread's persistent Playwright Chromium instance."""
    _shutdown_shared_browser_internal()

import atexit
atexit.register(shutdown_shared_browser)


def get_playwright_driver(settings=None, standalone=False) -> PlaywrightSeleniumAdapter:
    """
    Creates an isolated BrowserContext and Page on the persistent Chromium instance
    (or standalone if requested), wrapped in a Selenium-compatible adapter.
    """
    if standalone:
        playwright = sync_playwright().start()
        browser_args = [
            "--headless=new",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--hide-scrollbars",
            "--metrics-recording-only",
            "--mute-audio",
            "--no-first-run",
            "--memory-pressure-off",
        ]
        browser = playwright.chromium.launch(headless=True, args=browser_args)
        is_shared = False
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
        ]
        selected_ua = random.choice(user_agents)
        context = browser.new_context(
            user_agent=selected_ua,
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        adapter = PlaywrightSeleniumAdapter(playwright, browser, context, page)
        adapter._is_shared = is_shared
        return adapter

    # Persistent browser mode with automatic self-healing on disconnect/crash
    for attempt in range(2):
        try:
            playwright, browser = _get_shared_browser(settings)
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
            ]
            selected_ua = random.choice(user_agents)

            proxy_config = None
            if settings and settings.get("proxies_enabled") and settings.get("proxy_list"):
                try:
                    from utils.proxy_validator import get_next_working_proxy
                    proxy_url = get_next_working_proxy(settings)
                    if proxy_url:
                        proxy_config = {"server": proxy_url}
                except Exception:
                    pass

            context = browser.new_context(
                user_agent=selected_ua,
                viewport={"width": 1280, "height": 720},
                proxy=proxy_config,
                ignore_https_errors=True
            )

            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            def block_slow_resources(route):
                try:
                    resource_type = route.request.resource_type
                    url = route.request.url.lower()
                    exclude_types = ["image", "media", "font", "stylesheet"]
                    exclude_domains = ["google-analytics", "doubleclick", "demdex", "newrelic", "facebook", "youtube", "scorecardresearch", "hotjar"]
                    if resource_type in exclude_types or any(dom in url for dom in exclude_domains):
                        route.abort()
                    else:
                        route.continue_()
                except Exception:
                    try: route.continue_()
                    except Exception: pass

            page.route("**/*", block_slow_resources)

            adapter = PlaywrightSeleniumAdapter(playwright, browser, context, page)
            adapter._is_shared = True
            return adapter
        except Exception as e:
            logging.warning(f"[Playwright Pool] Persistent browser allocation attempt {attempt+1} encountered error: {e}. Re-initializing browser...")
            shutdown_shared_browser()
            if attempt == 1:
                raise e
