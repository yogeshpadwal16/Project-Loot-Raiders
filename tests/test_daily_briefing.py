import unittest
import os
import sqlite3
from daily_briefing import (
    get_emoji, init_briefing_db, is_headline_posted, 
    mark_headlines_posted, build_footer_block
)

class TestDailyBriefing(unittest.TestCase):
    def test_emoji_mapping(self):
        # Education/Exam keyword
        self.assertEqual(get_emoji("नवीन परीक्षा निकाल"), "🎓")
        # Crime/Accident keyword
        self.assertEqual(get_emoji("अपघात पोलीस ठाणे"), "🚨")
        # Politics keyword
        self.assertEqual(get_emoji("मुख्यमंत्री सरकार घोषणा"), "🏛️")
        # Default emoji
        self.assertEqual(get_emoji("साधारण बातमी"), "📰")

    def test_sqlite_deduplication(self):
        # Force fresh DB initialize
        init_briefing_db()
        
        import time
        headline = f"सिंधुदुर्ग: नवीन घडामोडी {time.time()}"
        
        # Initially not posted
        self.assertFalse(is_headline_posted(headline))
        
        # Mark as posted
        mark_headlines_posted([headline])
        
        # Now must be logged as posted
        self.assertTrue(is_headline_posted(headline))

    def test_footer_rates_formatting(self):
        footer = build_footer_block(
            gold_22k="66,500",
            gold_24k="72,500",
            silver_1kg="88,000",
            petrol_rate="₹111.21",
            diesel_rate="₹97.83"
        )
        
        # Verify blank lines between items (double newlines)
        self.assertIn("Gold Rate Today", footer)
        self.assertIn("Silver Rate Today", footer)
        self.assertIn("Petrol & Diesel Rate", footer)
        self.assertEqual(footer.count("\n\n"), 3)
        
        # Verify that Devanagari words are successfully represented
        self.assertIn("दर", footer)

if __name__ == "__main__":
    unittest.main()
