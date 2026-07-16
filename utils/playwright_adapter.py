import time
import logging
from playwright.sync_api import sync_playwright

class PlaywrightElementAdapter:
    def __init__(self, locator):
        self.locator = locator

    @property
    def text(self):
        try:
            return self.locator.inner_text().strip()
        except Exception as e:
            return ""

    def get_attribute(self, attr):
        try:
            if attr == "textContent":
                return self.locator.text_content()
            elif attr == "outerHTML":
                return self.locator.evaluate("el => el.outerHTML")
            elif attr == "innerHTML":
                return self.locator.evaluate("el => el.innerHTML")
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
            if not (selector.startswith("xpath=") or selector.startswith("//") or selector.startswith("./")):
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

    def _map_selector(self, by, selector):
        by_str = str(by).lower()
        if "xpath" in by_str:
            if not (selector.startswith("xpath=") or selector.startswith("//") or selector.startswith("./")):
                return f"xpath={selector}"
        return selector

    def quit(self):
        try:
            self.context.close()
            self.browser.close()
            self.playwright.stop()
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


def get_playwright_driver(settings=None) -> PlaywrightSeleniumAdapter:
    """
    Spins up a Playwright browser instance and wraps it in a Selenium-compatible adapter.
    """
    playwright = sync_playwright().start()
    
    # Launch Chromium with stealth arguments including undetected new headless flag
    browser_args = [
        "--headless=new",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--disable-gpu"
    ]
    
    proxy_config = None
    if settings and settings.get("proxies_enabled") and settings.get("proxy_list"):
        import random
        valid_proxies = [p.strip() for p in settings["proxy_list"] if p.strip()]
        if valid_proxies:
            proxy_url = random.choice(valid_proxies)
            if not proxy_url.startswith("http"):
                proxy_url = f"http://{proxy_url}"
            proxy_config = {"server": proxy_url}
            logging.info(f"Playwright launching using proxy: {proxy_url}")

    # Set headless=False and pass --headless=new argument to run undetected new headless mode
    browser = playwright.chromium.launch(
        headless=False,
        args=browser_args
    )
    
    # Configure context with custom User-Agent and viewport
    # NOTE: Omit context-level extra_http_headers to avoid corrupting sub-resource fetches (like CSS/JS/APIs)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        proxy=proxy_config,
        ignore_https_errors=True
    )
    
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return PlaywrightSeleniumAdapter(playwright, browser, context, page)
