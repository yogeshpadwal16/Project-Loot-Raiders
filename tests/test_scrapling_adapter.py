import unittest
from utils.scraper import (
    BaseScraperAdapter,
    ScraplingScraperAdapter,
    ScrapedResponse,
    ScrapedElement,
    ScraperFetchError,
    ScraperParseError,
)

class TestScraplingAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = ScraplingScraperAdapter()

    def test_adapter_inheritance(self):
        """Ensure the ScraplingScraperAdapter implements BaseScraperAdapter."""
        self.assertTrue(issubclass(ScraplingScraperAdapter, BaseScraperAdapter))
        self.assertIsInstance(self.adapter, BaseScraperAdapter)

    def test_fetch_success_fast_mode(self):
        """Test fetching a page in fast mode (HTTP)."""
        response = self.adapter.fetch("https://httpbin.org/get", mode="fast")
        self.assertIsInstance(response, ScrapedResponse)
        self.assertEqual(response.status_code, 200)
        self.assertIn("headers", response.content)

    def test_fetch_error_invalid_url(self):
        """Verify internal exceptions are shielded and re-raised as ScraperFetchError."""
        with self.assertRaises(ScraperFetchError):
            self.adapter.fetch("http://invalid-domain-name-that-does-not-exist.local", mode="fast")

    def test_element_selection_and_normalization(self):
        """Verify CSS selection, element parsing, and mapping into ScrapedElement works."""
        mock_html = """
        <html>
            <body>
                <div class="product-item" data-id="p123">
                    <span class="product-name">Gizmo</span>
                </div>
            </body>
        </html>
        """
        response = ScrapedResponse(
            url="http://example.com",
            status_code=200,
            content=mock_html
        )
        
        # Select single element
        el = self.adapter.select(response, "div.product-item")
        self.assertIsNotNone(el)
        self.assertIsInstance(el, ScrapedElement)
        self.assertEqual(el.tag_name, "div")
        self.assertEqual(el.attributes.get("data-id"), "p123")
        self.assertIn("Gizmo", el.text)

        # Select all elements
        all_els = self.adapter.select_all(response, "span")
        self.assertEqual(len(all_els), 1)
        self.assertEqual(all_els[0].tag_name, "span")
        self.assertEqual(all_els[0].text, "Gizmo")

    def test_adaptive_fingerprinting_modes(self):
        """Verify adaptive and auto_save selection configurations do not crash."""
        mock_html = "<html><body><h1 class='title'>Product A</h1></body></html>"
        response = ScrapedResponse(
            url="http://example.com",
            status_code=200,
            content=mock_html
        )
        # Test auto_save phase
        el_save = self.adapter.select(response, "h1.title", adaptive=True, auto_save=True)
        self.assertIsNotNone(el_save)
        self.assertEqual(el_save.text, "Product A")

        # Test adaptive recovery phase
        el_adapt = self.adapter.select(response, "h1.title", adaptive=True)
        self.assertIsNotNone(el_adapt)
        self.assertEqual(el_adapt.text, "Product A")

if __name__ == "__main__":
    unittest.main()
