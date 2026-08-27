# -*- coding: utf-8 -*-
import os
import sys
import unittest
import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deal_engine.festival_bot import (
    get_festival_for_date,
    generate_festival_poster,
    generate_local_festival_card,
    send_festival_greeting,
    check_and_run_festival_bot,
    FIXED_FESTIVALS,
    MOVABLE_FESTIVALS
)
from utils.image_extractor import resolve_best_product_image
from deal_engine.notifier import send_telegram_alert
from scripts.backup_db import push_to_telegram


class TestFestivalBotYearAware(unittest.TestCase):
    def test_fixed_festival_matching(self):
        # Republic Day: Jan 26
        dt = datetime.date(2026, 1, 26)
        fest = get_festival_for_date(dt)
        self.assertIsNotNone(fest)
        self.assertEqual(fest['name'], 'Republic Day')

        # Independence Day: Aug 15
        dt = datetime.date(2026, 8, 15)
        fest = get_festival_for_date(dt)
        self.assertIsNotNone(fest)
        self.assertEqual(fest['name'], 'Independence Day')

        # Shivaji Maharaj Jayanti: Feb 19
        dt = datetime.date(2026, 2, 19)
        fest = get_festival_for_date(dt)
        self.assertIsNotNone(fest)
        self.assertEqual(fest['name'], 'Chhatrapati Shivaji Maharaj Jayanti')

    def test_movable_festival_matching_2026(self):
        # 2026 Ganesh Chaturthi: Sept 14, 2026
        dt = datetime.date(2026, 9, 14)
        fest = get_festival_for_date(dt)
        self.assertIsNotNone(fest)
        self.assertEqual(fest['name'], 'Ganesh Chaturthi')

        # 2026 Holi: March 4, 2026
        dt = datetime.date(2026, 3, 4)
        fest = get_festival_for_date(dt)
        self.assertIsNotNone(fest)
        self.assertEqual(fest['name'], 'Holi')

        # 2026 Diwali Lakshmi Pujan: Nov 8, 2026
        dt = datetime.date(2026, 11, 8)
        fest = get_festival_for_date(dt)
        self.assertIsNotNone(fest)
        self.assertEqual(fest['name'], 'Diwali Lakshmi Pujan')

    def test_movable_festival_matching_2027(self):
        # 2027 Ganesh Chaturthi: Sept 4, 2027
        dt = datetime.date(2027, 9, 4)
        fest = get_festival_for_date(dt)
        self.assertIsNotNone(fest)
        self.assertEqual(fest['name'], 'Ganesh Chaturthi')

    def test_non_festival_date(self):
        # Normal date: Jan 10
        dt = datetime.date(2026, 1, 10)
        fest = get_festival_for_date(dt)
        self.assertIsNone(fest)


class TestFestivalFallbackHierarchy(unittest.TestCase):
    @patch('deal_engine.festival_bot.requests.post')
    def test_tier1_imagen_success(self, mock_post):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            'predictions': [{'bytesBase64Encoded': 'aGVsbG93b3JsZA=='}]
        }
        mock_post.return_value = mock_res

        with patch('config.settings.load_settings', return_value={'gemini_api_key': 'valid_key_123'}):
            poster = generate_festival_poster('Test Diwali prompt')
            self.assertIsNotNone(poster)
            self.assertEqual(poster, b'helloworld')

    @patch('deal_engine.festival_bot.requests.post')
    def test_tier1_imagen_failure_returns_none(self, mock_post):
        mock_res = MagicMock()
        mock_res.status_code = 429
        mock_res.text = 'Quota exceeded'
        mock_post.return_value = mock_res

        with patch('config.settings.load_settings', return_value={'gemini_api_key': 'valid_key_123'}):
            poster = generate_festival_poster('Test prompt')
            self.assertIsNone(poster)

    def test_tier2_local_pil_card_generation(self):
        fest_info = {
            'name': 'Diwali',
            'theme': 'gold_diya',
            'desc': 'Test Diwali description',
            'caption': 'Happy Diwali!'
        }
        card_bytes = generate_local_festival_card(fest_info)
        self.assertIsNotNone(card_bytes)
        self.assertGreater(len(card_bytes), 1000)
        self.assertTrue(card_bytes.startswith(b'\xff\xd8'))

    @patch('deal_engine.festival_bot.requests.post')
    def test_tier3_send_festival_greeting_text_fallback(self, mock_post):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_post.return_value = mock_res

        with patch('config.settings.load_settings', return_value={'telegram_bot_token': 'mock_tok', 'telegram_chat_id': '@mock_chan'}):
            res = send_festival_greeting(None, '<b>Festive Greetings!</b>')
            self.assertTrue(res)
            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            self.assertIn('sendMessage', call_url)

    @patch('deal_engine.festival_bot.requests.post')
    def test_same_day_duplicate_prevention(self, mock_post):
        import asyncio
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_post.return_value = mock_res

        settings_store = {
            'telegram_bot_token': 'mock_tok',
            'telegram_chat_id': '@mock_chan',
            'last_festival_greeting_date': ''
        }
        def mock_load():
            return dict(settings_store)
        def mock_save(s):
            settings_store.update(s)

        test_date = datetime.date(2026, 8, 15) # Independence Day

        with patch('config.settings.load_settings', side_effect=mock_load), \
             patch('config.settings.save_settings', side_effect=mock_save), \
             patch('deal_engine.festival_bot.generate_festival_poster', return_value=None):

            # First execution on festival date -> should run and post
            run1 = asyncio.run(check_and_run_festival_bot(target_date=test_date))
            self.assertTrue(run1)
            self.assertEqual(settings_store['last_festival_greeting_date'], '2026-08-15')

            # Second execution on same festival date -> must be blocked
            run2 = asyncio.run(check_and_run_festival_bot(target_date=test_date))
            self.assertFalse(run2)

    def test_notifier_worker_isolation_on_exception(self):
        import asyncio
        with patch('deal_engine.festival_bot.get_festival_for_date', side_effect=Exception('Unexpected Crash')):
            res = asyncio.run(check_and_run_festival_bot())
            self.assertFalse(res)


class TestProductImageIntegrity(unittest.TestCase):
    def test_preserve_and_upscale_valid_amazon_image(self):
        raw = 'https://m.media-amazon.com/images/I/71abc123._AC_UL320_.jpg'
        resolved = resolve_best_product_image(
            raw_img_url=raw,
            product_url='https://www.amazon.in/dp/B0H4KM58CR',
            platform='amazon',
            unique_id='B0H4KM58CR'
        )
        self.assertIsNotNone(resolved)
        self.assertIn('m.media-amazon.com', resolved)
        self.assertIn('_AC_SL1500_', resolved)
        self.assertNotIn('/images/P/', resolved)

    def test_preserve_and_upscale_flipkart_image(self):
        raw = 'https://rukminim2.flixcart.com/image/128/128/xif0q/phone/xyz.jpeg'
        resolved = resolve_best_product_image(
            raw_img_url=raw,
            product_url='https://www.flipkart.com/p/123',
            platform='flipkart',
            unique_id='flip_123'
        )
        self.assertEqual(resolved, 'https://rukminim2.flixcart.com/image/832/832/xif0q/phone/xyz.jpeg')

    def test_fallback_to_asin_only_when_raw_missing(self):
        resolved = resolve_best_product_image(
            raw_img_url='',
            product_url='https://www.amazon.in/dp/B09G9BL5CP',
            platform='amazon',
            unique_id='B09G9BL5CP'
        )
        self.assertIsNotNone(resolved)
        self.assertIn('B09G9BL5CP', resolved)

    @patch('deal_engine.notifier.requests.get')
    @patch('deal_engine.notifier.requests.post')
    @patch('utils.image_generator.generate_deal_image')
    def test_reject_1x1_gif_placeholder_and_trigger_card_generator(self, mock_gen_card, mock_post, mock_get):
        # Simulate Amazon 43-byte 1x1 GIF
        mock_dl_res = MagicMock()
        mock_dl_res.status_code = 200
        mock_dl_res.content = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        mock_dl_res.headers = {'content-type': 'image/gif'}
        mock_get.return_value = mock_dl_res

        # Card generator mock returning a valid fake path
        mock_gen_card.return_value = None

        # Telegram post response
        mock_tg_res = MagicMock()
        mock_tg_res.status_code = 200
        mock_tg_res.json.return_value = {'ok': True, 'result': {'message_id': 12345}}
        mock_post.return_value = mock_tg_res

        with patch('config.settings.load_settings', return_value={'telegram_bot_token': 'mock_tok', 'telegram_chat_id': '@LootRaidersDeals'}):
            send_telegram_alert(
                bot_token='mock_tok',
                chat_id='@LootRaidersDeals',
                platform='amazon',
                title='Deal with 1x1 GIF placeholder',
                price=499,
                mrp=999,
                discount=50.0,
                img_url='https://images-eu.ssl-images-amazon.com/images/P/B0H4KM58CR.01._SCLZZZZZZZ_.jpg',
                final_url='https://www.amazon.in/dp/B0H4KM58CR',
                is_verified_low=True,
                deal_score=88.0,
                unique_id='test_gif_deal'
            )
            # Verify card generator was invoked because 1x1 GIF was rejected
            mock_gen_card.assert_called_once()


class TestBackupSecurityAndArtifactFirewall(unittest.TestCase):
    def test_push_to_telegram_blocks_public_channel(self):
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'mock_tok',
            'TELEGRAM_BACKUP_CHAT_ID': '@LootRaidersDeals'
        }):
            with patch('config.settings.load_settings', return_value={'telegram_chat_id': '@LootRaidersDeals'}):
                res = push_to_telegram('fake_backup.db.gz', caption='Backup')
                self.assertFalse(res)

    def test_deal_alert_rejects_backup_db_gz(self):
        # Attempt to publish a database archive as a deal
        res = send_telegram_alert(
            bot_token='mock_tok',
            chat_id='@LootRaidersDeals',
            platform='amazon',
            title='loot_raiders_backup_20260827.db.gz',
            price=0,
            mrp=100,
            discount=100.0,
            img_url='https://example.com/loot_raiders.db.gz',
            final_url='https://example.com/backup.db.gz',
            is_verified_low=True,
            deal_score=99.0,
            unique_id='leak_123'
        )
        self.assertFalse(res)


if __name__ == '__main__':
    unittest.main()
