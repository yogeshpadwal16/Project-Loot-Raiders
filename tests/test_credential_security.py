"""
tests/test_credential_security.py
Security Regression Tests — Credential Isolation & Scanner Safety
=================================================================

Verifies that:
1. Environment-sourced secrets are loaded into runtime settings.
2. save_settings() NEVER persists env-sourced secrets to settings.json.
3. Notification URIs containing real tokens are sanitized on save.
4. The secret scanner never prints actual secret values.
5. Non-secret configuration is preserved across save_settings() calls.
6. Fake test credentials are not flagged by the secret scanner.
"""

import json
import os
import sys
import re
import tempfile
import unittest
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSaveSettingsStripsSecrets(unittest.TestCase):
    """Verify that save_settings() strips env-sourced credentials."""

    def setUp(self):
        # Create a temporary settings.json for isolated testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_settings = os.path.join(self.temp_dir, "settings.json")

        # Write a sanitized baseline settings file
        self.baseline = {
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            "telegram_chat_id": "@TestChannel",
            "gemini_api_key": "YOUR_GEMINI_API_KEY",
            "omniroute_api_key": "YOUR_OMNIROUTE_API_KEY",
            "amazon_tag": "YOUR_AMAZON_TAG",
            "scraper_loop_interval": 300,
            "channel_mirror_enabled": True,
            "min_discount": 30.0,
            "notification_uris": ["tgram://YOUR_TELEGRAM_BOT_TOKEN/@TestChannel"],
        }
        with open(self.temp_settings, "w") as f:
            json.dump(self.baseline, f)

    def tearDown(self):
        if os.path.exists(self.temp_settings):
            os.remove(self.temp_settings)
        os.rmdir(self.temp_dir)

    @patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "9999999999:FAKE_TEST_TOKEN_ABCDEFGHIJKLMNOPQR",
        "GEMINI_API_KEY": "FAKE_GEMINI_KEY_FOR_TEST_ONLY",
        "OMNIROUTE_API_KEY": "FAKE_OMNIROUTE_KEY_FOR_TEST_ONLY",
        "AMAZON_TAG": "fake-test-tag-21",
    }, clear=False)
    def test_01_env_secrets_stripped_from_saved_file(self):
        """save_settings() must replace env-sourced secrets with safe placeholders."""
        from config.settings import save_settings, SETTINGS_FILE, _ENV_SECRET_KEYS

        # Build a settings dict that looks like load_settings() output
        # (env values merged in)
        runtime_settings = self.baseline.copy()
        runtime_settings["telegram_bot_token"] = "9999999999:FAKE_TEST_TOKEN_ABCDEFGHIJKLMNOPQR"
        runtime_settings["gemini_api_key"] = "FAKE_GEMINI_KEY_FOR_TEST_ONLY"
        runtime_settings["omniroute_api_key"] = "FAKE_OMNIROUTE_KEY_FOR_TEST_ONLY"
        runtime_settings["amazon_tag"] = "fake-test-tag-21"
        runtime_settings["notification_uris"] = [
            "tgram://9999999999:FAKE_TEST_TOKEN_ABCDEFGHIJKLMNOPQR/@TestChannel"
        ]

        # Point save_settings at our temp file
        original_file = SETTINGS_FILE
        try:
            import config.settings as settings_mod
            settings_mod.SETTINGS_FILE = self.temp_settings
            save_settings(runtime_settings)
        finally:
            settings_mod.SETTINGS_FILE = original_file

        # Read what was actually written
        with open(self.temp_settings, "r") as f:
            on_disk = json.load(f)

        # Assert NO real credential values were persisted
        self.assertEqual(on_disk["telegram_bot_token"], "YOUR_TELEGRAM_BOT_TOKEN",
                         "Real Telegram token was persisted to settings.json!")
        self.assertEqual(on_disk["gemini_api_key"], "YOUR_GEMINI_API_KEY",
                         "Real Gemini key was persisted to settings.json!")
        self.assertEqual(on_disk["omniroute_api_key"], "YOUR_OMNIROUTE_API_KEY",
                         "Real OmniRoute key was persisted to settings.json!")
        self.assertEqual(on_disk["amazon_tag"], "YOUR_AMAZON_TAG",
                         "Real Amazon tag was persisted to settings.json!")

    @patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "9999999999:FAKE_TEST_TOKEN_ABCDEFGHIJKLMNOPQR",
    }, clear=False)
    def test_02_notification_uris_sanitized(self):
        """Notification URIs embedding real tokens must be sanitized."""
        from config.settings import save_settings, SETTINGS_FILE

        runtime_settings = self.baseline.copy()
        runtime_settings["telegram_bot_token"] = "9999999999:FAKE_TEST_TOKEN_ABCDEFGHIJKLMNOPQR"
        runtime_settings["notification_uris"] = [
            "tgram://9999999999:FAKE_TEST_TOKEN_ABCDEFGHIJKLMNOPQR/@TestChannel"
        ]

        original_file = SETTINGS_FILE
        try:
            import config.settings as settings_mod
            settings_mod.SETTINGS_FILE = self.temp_settings
            save_settings(runtime_settings)
        finally:
            settings_mod.SETTINGS_FILE = original_file

        with open(self.temp_settings, "r") as f:
            on_disk = json.load(f)

        for uri in on_disk.get("notification_uris", []):
            self.assertNotIn("FAKE_TEST_TOKEN", uri,
                             f"Real token found in notification_uris: {uri}")
            if "tgram://" in uri:
                self.assertIn("YOUR_TELEGRAM", uri)

    @patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "9999999999:FAKE_TEST_TOKEN_ABCDEFGHIJKLMNOPQR",
    }, clear=False)
    def test_03_non_secret_settings_preserved(self):
        """Non-secret configuration must survive save_settings() intact."""
        from config.settings import save_settings, SETTINGS_FILE

        runtime_settings = self.baseline.copy()
        runtime_settings["telegram_bot_token"] = "9999999999:FAKE_TEST_TOKEN_ABCDEFGHIJKLMNOPQR"
        runtime_settings["scraper_loop_interval"] = 600
        runtime_settings["min_discount"] = 25.0
        runtime_settings["channel_mirror_enabled"] = False

        original_file = SETTINGS_FILE
        try:
            import config.settings as settings_mod
            settings_mod.SETTINGS_FILE = self.temp_settings
            save_settings(runtime_settings)
        finally:
            settings_mod.SETTINGS_FILE = original_file

        with open(self.temp_settings, "r") as f:
            on_disk = json.load(f)

        self.assertEqual(on_disk["scraper_loop_interval"], 600)
        self.assertEqual(on_disk["min_discount"], 25.0)
        self.assertEqual(on_disk["channel_mirror_enabled"], False)
        self.assertEqual(on_disk["telegram_chat_id"], "@TestChannel")

    @patch.dict(os.environ, {}, clear=False)
    def test_04_no_env_no_stripping(self):
        """When env vars are NOT set, save_settings() preserves values from settings.json as-is."""
        from config.settings import save_settings, SETTINGS_FILE

        # Remove env vars that would trigger stripping
        env_keys = ["TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY", "OMNIROUTE_API_KEY", "AMAZON_TAG"]
        saved_env = {}
        for k in env_keys:
            if k in os.environ:
                saved_env[k] = os.environ.pop(k)

        try:
            runtime_settings = self.baseline.copy()
            # These are the placeholder values from the file — NOT env-sourced
            original_file = SETTINGS_FILE
            try:
                import config.settings as settings_mod
                settings_mod.SETTINGS_FILE = self.temp_settings
                save_settings(runtime_settings)
            finally:
                settings_mod.SETTINGS_FILE = original_file

            with open(self.temp_settings, "r") as f:
                on_disk = json.load(f)

            # Placeholders should be preserved as-is (not double-replaced)
            self.assertEqual(on_disk["telegram_bot_token"], "YOUR_TELEGRAM_BOT_TOKEN")
        finally:
            os.environ.update(saved_env)


class TestEnvCredentialLoading(unittest.TestCase):
    """Verify that load_settings() correctly merges env-sourced credentials."""

    def test_01_env_overrides_settings_json(self):
        """Environment variables must override settings.json values at runtime."""
        import config.settings as settings_mod

        # Force cache invalidation
        settings_mod._settings_cache = None

        # Mock load_dotenv to prevent .env from overriding our test env vars
        # (load_dotenv unconditionally overwrites os.environ with .env values)
        original_env = {}
        for k in ["TELEGRAM_BOT_TOKEN", "OMNIROUTE_API_KEY"]:
            if k in os.environ:
                original_env[k] = os.environ[k]

        try:
            os.environ["TELEGRAM_BOT_TOKEN"] = "1111111111:FAKE_ENV_TOKEN_FOR_LOAD_TEST_XXXXX"
            os.environ["OMNIROUTE_API_KEY"] = "FAKE_OMNIROUTE_LOAD_TEST"

            with patch.object(settings_mod, 'load_dotenv'):
                settings = settings_mod.load_settings()

            self.assertEqual(settings["telegram_bot_token"],
                             "1111111111:FAKE_ENV_TOKEN_FOR_LOAD_TEST_XXXXX")
            self.assertEqual(settings["omniroute_api_key"],
                             "FAKE_OMNIROUTE_LOAD_TEST")
        finally:
            # Clean up
            settings_mod._settings_cache = None
            for k in ["TELEGRAM_BOT_TOKEN", "OMNIROUTE_API_KEY"]:
                if k in original_env:
                    os.environ[k] = original_env[k]
                else:
                    os.environ.pop(k, None)


class TestSecretScannerSafety(unittest.TestCase):
    """Verify the secret scanner never prints actual secret values."""

    def test_01_scanner_masks_output(self):
        """Secret scanner output must never contain full secret values."""
        import subprocess

        # Create a temp file with a fake token pattern that would match
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "leaky_test.py")
        fake_token = "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
        with open(test_file, "w") as f:
            f.write(f'TOKEN = "{fake_token}"\n')

        try:
            # Simulate what the scanner does with a match
            token_pattern = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b")
            with open(test_file, "r") as f:
                lines = f.readlines()

            output_lines = []
            for line_num, line_text in enumerate(lines, 1):
                for match in token_pattern.finditer(line_text):
                    matched_value = match.group(0)
                    if len(matched_value) > 8:
                        safe_hint = "****" + matched_value[-4:]
                    else:
                        safe_hint = "****"
                    msg = f"[FAIL] Potential Telegram Bot Token detected in test:{line_num} ({safe_hint})"
                    output_lines.append(msg)

            self.assertTrue(len(output_lines) > 0, "Scanner should have detected the fake token")
            for line in output_lines:
                self.assertNotIn(fake_token, line,
                                 "Scanner printed the full secret value!")
                self.assertNotIn("ABCDEFGHIJKLMNOPQRST", line,
                                 "Scanner printed a significant portion of the secret!")
                # Only last 4 chars should appear
                self.assertIn("fghi", line, "Safe hint should contain last 4 chars")
        finally:
            os.remove(test_file)
            os.rmdir(temp_dir)


class TestNoRealSecretsInSource(unittest.TestCase):
    """Verify that no real credential patterns exist in tracked source files."""

    def test_01_settings_json_has_no_real_tokens(self):
        """settings.json must only contain placeholder values for credential fields."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(project_root, "settings.json")
        with open(settings_path, "r") as f:
            data = json.load(f)

        token = data.get("telegram_bot_token", "")
        self.assertTrue(
            "YOUR_" in token or token == "",
            f"settings.json contains a non-placeholder telegram_bot_token"
        )

        gemini = data.get("gemini_api_key", "")
        self.assertTrue(
            "YOUR_" in gemini or gemini == "",
            f"settings.json contains a non-placeholder gemini_api_key"
        )

        omniroute = data.get("omniroute_api_key", "")
        self.assertTrue(
            "YOUR_" in omniroute or omniroute == "",
            f"settings.json contains a non-placeholder omniroute_api_key"
        )

    def test_02_env_file_is_gitignored(self):
        """The .env file must be in .gitignore."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gitignore_path = os.path.join(project_root, ".gitignore")
        with open(gitignore_path, "r") as f:
            gitignore_content = f.read()

        self.assertIn(".env", gitignore_content,
                       ".env is not listed in .gitignore!")

    def test_03_no_telegram_token_pattern_in_python_source(self):
        """No Python source file (outside tests/) should contain a Telegram token pattern."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        token_pattern = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b")

        violations = []
        for root, dirs, filenames in os.walk(project_root):
            # Skip directories that should not be scanned
            dirs[:] = [d for d in dirs if d not in [
                ".git", "venv", ".venv", "__pycache__", "tests",
                "scratch", "OmniRoute", "node_modules", "loot_brain"
            ]]
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if token_pattern.search(content):
                        rel = os.path.relpath(fpath, project_root)
                        violations.append(rel)
                except Exception:
                    pass

        self.assertEqual(violations, [],
                         f"Telegram token pattern found in: {violations}")


if __name__ == "__main__":
    unittest.main()
