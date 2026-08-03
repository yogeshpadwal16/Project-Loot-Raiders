import unittest
import time
import os
import shutil
from utils.semantic_dedup import add_deal_vector, find_semantic_duplicate, get_chroma_collection

class TestSemanticDeduplication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        try:
            from utils.semantic_dedup import get_chroma_collection
            collection = get_chroma_collection()
            if collection.count() > 0:
                collection.delete(ids=collection.get()["ids"])
        except Exception:
            pass

    def test_semantic_duplicate_detection(self):
        product_id = "test_asin_123"
        title_1 = "Samsung Galaxy S24 Ultra Flagship 5G Smartphone"
        price = 99999
        
        # 1. Index original product
        add_deal_vector(product_id=product_id, title=title_1, price=price)
        
        # 2. Check identical match
        dup_id = find_semantic_duplicate(title=title_1, price=price, threshold=0.85)
        self.assertEqual(dup_id, product_id)
        
        # 3. Check semantic variation match (different words, same meaning)
        title_2 = "Samsung S24 Ultra premium 5G phone"
        dup_id_variation = find_semantic_duplicate(title=title_2, price=price, threshold=0.75)
        self.assertEqual(dup_id_variation, product_id)
        
        # 4. Check different price mismatch
        dup_id_diff_price = find_semantic_duplicate(title=title_1, price=105000, threshold=0.85)
        self.assertIsNone(dup_id_diff_price)
        
        # 5. Check different semantic text mismatch
        title_3 = "Apple iPhone 15 Pro Max Smartphone"
        dup_id_diff_text = find_semantic_duplicate(title=title_3, price=price, threshold=0.85)
        self.assertIsNone(dup_id_diff_text)

if __name__ == "__main__":
    unittest.main()
