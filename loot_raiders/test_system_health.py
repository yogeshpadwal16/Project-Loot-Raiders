import os
import sys
import unittest

# Ensure the parent directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


class ProjectLootRaidersHealthTest(unittest.TestCase):
    """
    Integration CLI health check suite for Project Loot Raiders.
    Checks DB initialization, URL expander, routing mapping, and A/B configurations.
    """
    def setUp(self):
        # Force database initialization
        from database import init_db, SessionLocal, Product
        init_db()
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_database_health(self):
        """Verify that SQLite connection is established and tables exist."""
        from database import Product, PriceHistory, WishlistItem
        # Insert a dummy product
        prod = Product(id="health_check_asin", platform="amazon", title="Health Check Book", url="https://amazon.in/dp/health_check_asin")
        self.db.merge(prod)
        self.db.commit()
        
        db_prod = self.db.query(Product).filter_by(id="health_check_asin").first()
        self.assertIsNotNone(db_prod)
        self.assertEqual(db_prod.title, "Health Check Book")
        
        # Cleanup
        self.db.delete(db_prod)
        self.db.commit()

    def test_affiliate_cleaner(self):
        """Verify Amazon and Flipkart URL canonicalization."""
        from affiliate_cleaner import clean_and_tag_url
        
        # Amazon cleanup
        url_amz, plat_amz = clean_and_tag_url("https://www.amazon.in/Sony-WH-1000XM4-Cancelling-Headphones-Assistant/dp/B0863TXGM3/ref=sr_1_3?qid=123")
        self.assertEqual(plat_amz, "amazon")
        self.assertIn("tag=loot_raiders-21", url_amz)
        self.assertIn("B0863TXGM3", url_amz)

        # Flipkart cleanup
        url_fk, plat_fk = clean_and_tag_url("https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm2d83c20202020?pid=MOBGTAGPA5E4A7HG&lid=LSTMOBGTAGPA5E4A7HG")
        self.assertEqual(plat_fk, "flipkart")
        self.assertIn("affid=loot_raiders", url_fk)
        self.assertIn("MOBGTAGPA5E4A7HG", url_fk)

    def test_channel_router(self):
        """Verify category routing maps to correct Telegram channel niches."""
        from channel_router import resolve_target_channel
        
        # Tech keywords routing
        self.assertEqual(resolve_target_channel("Sony Wireless Noise Cancelling Earbuds"), "@LootRaidersTech")
        
        # Fashion keywords routing
        self.assertEqual(resolve_target_channel("Adidas Running Sneakers"), "@LootRaidersFashion")
        
        # Home keywords routing
        self.assertEqual(resolve_target_channel("Stainless steel pressure cooker"), "@LootRaidersHome")
        
        # Default fallback
        self.assertEqual(resolve_target_channel("Organic green tea"), "@LootRaidersDeals")

    def test_ab_testing(self):
        """Verify deterministic A/B variant splits."""
        from ab_testing import select_ab_template
        
        # Hashing of string IDs should yield stable parities
        var1, tag1 = select_ab_template("B0863TXGM3")
        var2, tag2 = select_ab_template("B0863TXGM3")
        
        self.assertEqual(var1, var2)
        self.assertEqual(tag1, tag2)
        self.assertTrue(var1 in ["CARD_BLOCKQUOTE", "COMPACT_LIST"])


if __name__ == "__main__":
    unittest.main()
