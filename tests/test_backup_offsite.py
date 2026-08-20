"""
Unit tests for the database backup, integrity verification, compression, and off-site dispatch engine.
"""
import os
import sys
import unittest
import tempfile
import sqlite3
import shutil
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.backup_db import (
    verify_backup_integrity,
    compress_backup,
    push_to_telegram,
    push_to_secondary_directory,
    push_to_webhook,
    dispatch_offsite_backup,
    perform_backup,
    prune_old_backups
)

class TestOffsiteBackupEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_loot.db")
        
        # Create a sample valid SQLite DB
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT);")
        cursor.execute("INSERT INTO test_table (name) VALUES ('Loot Deal 1');")
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_verify_backup_integrity_valid(self):
        self.assertTrue(verify_backup_integrity(self.db_path))

    def test_verify_backup_integrity_corrupt_or_nonexistent(self):
        fake_path = os.path.join(self.test_dir, "nonexistent.db")
        self.assertFalse(verify_backup_integrity(fake_path))
        
        corrupt_path = os.path.join(self.test_dir, "corrupt.db")
        with open(corrupt_path, "w") as f:
            f.write("THIS IS NOT A SQLITE DATABASE")
        self.assertFalse(verify_backup_integrity(corrupt_path))

    def test_compress_backup(self):
        gz_path = compress_backup(self.db_path)
        self.assertTrue(os.path.exists(gz_path))
        self.assertTrue(gz_path.endswith(".gz"))
        self.assertGreater(os.path.getsize(gz_path), 0)

    @patch("requests.post")
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_BACKUP_CHAT_ID": "@mock_backup_channel"})
    def test_push_to_telegram_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        res = push_to_telegram(self.db_path, caption="Test Backup")
        self.assertTrue(res)
        mock_post.assert_called_once()

    def test_push_to_secondary_directory(self):
        secondary_dir = os.path.join(self.test_dir, "secondary_offsite")
        with patch.dict(os.environ, {"OFFSITE_BACKUP_DIR": secondary_dir}):
            res = push_to_secondary_directory(self.db_path)
            self.assertTrue(res)
            copied_file = os.path.join(secondary_dir, os.path.basename(self.db_path))
            self.assertTrue(os.path.exists(copied_file))

    @patch("requests.post")
    def test_push_to_webhook(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"OFFSITE_BACKUP_WEBHOOK_URL": "https://example.com/upload"}):
            res = push_to_webhook(self.db_path)
            self.assertTrue(res)
            mock_post.assert_called_once()

    @patch("scripts.backup_db.DB_PATH")
    @patch("scripts.backup_db.BACKUP_DIR")
    def test_perform_backup_end_to_end(self, mock_backup_dir, mock_db_path):
        backup_dir = os.path.join(self.test_dir, "backups")
        mock_backup_dir.__fspath__ = lambda self: backup_dir
        mock_backup_dir.__str__ = lambda self: backup_dir
        mock_db_path.__fspath__ = lambda self: self.db_path
        mock_db_path.__str__ = lambda self: self.db_path
        
        with patch("scripts.backup_db.DB_PATH", self.db_path), \
             patch("scripts.backup_db.BACKUP_DIR", backup_dir):
            success = perform_backup()
            self.assertTrue(success)
            self.assertTrue(os.path.exists(backup_dir))
            files = os.listdir(backup_dir)
            self.assertTrue(any(f.endswith(".db") for f in files))
            self.assertTrue(any(f.endswith(".db.gz") for f in files))

if __name__ == "__main__":
    unittest.main()
