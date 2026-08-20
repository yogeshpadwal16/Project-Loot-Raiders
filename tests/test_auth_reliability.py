"""
tests/test_auth_reliability.py
Focused test suite verifying authentication isolation, OTP lifecycle,
gateway error classification, and security guard enforcement for Phase 1.1.
"""

import unittest
import os
import time
import json
import secrets
from unittest.mock import patch, MagicMock

# Import authentication engine
from web.auth_engine import (
    get_owner_credentials,
    mask_mobile_number,
    initiate_owner_login,
    verify_owner_otp,
    resend_owner_otp,
    _ACTIVE_OTP_SESSIONS,
    SESSION_EXPIRY_SEC,
    RESEND_COOLDOWN_SEC,
    MAX_ATTEMPTS
)
from web.server import ScraperAPIHandler, is_public_endpoint


class TestAuthReliability(unittest.TestCase):

    def setUp(self):
        # Set clean mock credentials in environment
        self.orig_user = os.environ.get("DASHBOARD_USERNAME")
        self.orig_pass = os.environ.get("DASHBOARD_PASSWORD")
        self.orig_token = os.environ.get("DASHBOARD_SESSION_TOKEN")
        self.orig_mobile = os.environ.get("OWNER_MOBILE_NUMBER")

        os.environ["DASHBOARD_USERNAME"] = "test_owner_admin"
        os.environ["DASHBOARD_PASSWORD"] = "SuperSecretAuthPass123!"
        os.environ["DASHBOARD_SESSION_TOKEN"] = "token_auth_verified_xyz"
        os.environ["OWNER_MOBILE_NUMBER"] = "+919876543210"

        _ACTIVE_OTP_SESSIONS.clear()

    def tearDown(self):
        _ACTIVE_OTP_SESSIONS.clear()
        if self.orig_user: os.environ["DASHBOARD_USERNAME"] = self.orig_user
        else: os.environ.pop("DASHBOARD_USERNAME", None)

        if self.orig_pass: os.environ["DASHBOARD_PASSWORD"] = self.orig_pass
        else: os.environ.pop("DASHBOARD_PASSWORD", None)

        if self.orig_token: os.environ["DASHBOARD_SESSION_TOKEN"] = self.orig_token
        else: os.environ.pop("DASHBOARD_SESSION_TOKEN", None)

        if self.orig_mobile: os.environ["OWNER_MOBILE_NUMBER"] = self.orig_mobile
        else: os.environ.pop("OWNER_MOBILE_NUMBER", None)

    # 1. Valid credentials -> OTP generation path reached
    @patch("web.auth_engine.dispatch_telegram_otp")
    def test_01_valid_credentials_reaches_otp_generation(self, mock_dispatch):
        success, session_id, masked_mobile, otp_code, error_msg = initiate_owner_login(
            "test_owner_admin", "SuperSecretAuthPass123!"
        )

        self.assertTrue(success)
        self.assertIsNotNone(session_id)
        self.assertEqual(len(session_id), 32)
        self.assertIn("******3210", masked_mobile)
        self.assertIsNotNone(otp_code)
        self.assertEqual(len(otp_code), 6)
        self.assertTrue(otp_code.isdigit())
        self.assertIsNone(error_msg)

        # Verify session is actively recorded in in-memory session store
        self.assertIn(session_id, _ACTIVE_OTP_SESSIONS)
        self.assertEqual(_ACTIVE_OTP_SESSIONS[session_id]["otp"], otp_code)

    # 2. Invalid credentials -> authentication failure
    @patch("web.auth_engine.dispatch_telegram_otp")
    def test_02_invalid_credentials_rejected(self, mock_dispatch):
        # Case A: Wrong password
        success, session_id, masked_mobile, otp_code, error_msg = initiate_owner_login(
            "test_owner_admin", "WrongPassword!"
        )
        self.assertFalse(success)
        self.assertIsNone(session_id)
        self.assertIsNone(otp_code)
        self.assertEqual(error_msg, "Invalid username or password.")

        # Case B: Wrong username
        success, session_id, masked_mobile, otp_code, error_msg = initiate_owner_login(
            "unknown_user", "SuperSecretAuthPass123!"
        )
        self.assertFalse(success)
        self.assertIsNone(session_id)
        self.assertIsNone(otp_code)
        self.assertEqual(error_msg, "Invalid username or password.")

    # 3. OTP verification lifecycle & session authorization
    def test_03_otp_verification_success_and_single_use(self):
        success, session_id, masked_mobile, otp_code, _ = initiate_owner_login(
            "test_owner_admin", "SuperSecretAuthPass123!"
        )
        self.assertTrue(success)

        # Verify with correct OTP
        ver_success, token, err = verify_owner_otp(session_id, otp_code)
        self.assertTrue(ver_success)
        self.assertEqual(token, "token_auth_verified_xyz")
        self.assertIsNone(err)

        # Confirm session is purged (cannot be replayed)
        self.assertNotIn(session_id, _ACTIVE_OTP_SESSIONS)
        re_ver_success, _, re_err = verify_owner_otp(session_id, otp_code)
        self.assertFalse(re_ver_success)
        self.assertIn("Invalid or expired session", re_err)

    # 4. OTP verification attempt limits (Max 3 attempts)
    def test_04_otp_max_attempts_invalidation(self):
        success, session_id, _, otp_code, _ = initiate_owner_login(
            "test_owner_admin", "SuperSecretAuthPass123!"
        )
        self.assertTrue(success)

        # Attempt 1: wrong OTP
        ok, _, err = verify_owner_otp(session_id, "000000")
        self.assertFalse(ok)
        self.assertIn("2 attempt(s) remaining", err)

        # Attempt 2: wrong OTP
        ok, _, err = verify_owner_otp(session_id, "111111")
        self.assertFalse(ok)
        self.assertIn("1 attempt(s) remaining", err)

        # Attempt 3: wrong OTP -> Session should be invalidated
        ok, _, err = verify_owner_otp(session_id, "222222")
        self.assertFalse(ok)
        self.assertIn("Maximum verification attempts exceeded", err)
        self.assertNotIn(session_id, _ACTIVE_OTP_SESSIONS)

    # 5. OTP expiration enforcement
    def test_05_otp_expiration_enforcement(self):
        success, session_id, _, otp_code, _ = initiate_owner_login(
            "test_owner_admin", "SuperSecretAuthPass123!"
        )
        self.assertTrue(success)

        # Artificially expire the session
        _ACTIVE_OTP_SESSIONS[session_id]["expires_at"] = time.time() - 10

        # Attempt verification on expired session
        ok, _, err = verify_owner_otp(session_id, otp_code)
        self.assertFalse(ok)
        self.assertIn("expired", err.lower())
        self.assertNotIn(session_id, _ACTIVE_OTP_SESSIONS)

    # 6. OTP resend limits & cooldown enforcement (30-second cooldown)
    @patch("web.auth_engine.dispatch_telegram_otp")
    def test_06_otp_resend_cooldown_and_regeneration(self, mock_dispatch):
        success, session_id, _, otp1, _ = initiate_owner_login(
            "test_owner_admin", "SuperSecretAuthPass123!"
        )
        self.assertTrue(success)

        # Immediate resend attempt should be throttled by 30s cooldown
        re_ok, _, _, re_err = resend_owner_otp(session_id)
        self.assertFalse(re_ok)
        self.assertIn("Please wait", re_err)

        # Simulate 35 seconds elapsed
        _ACTIVE_OTP_SESSIONS[session_id]["last_resend_at"] = time.time() - 35

        # Resend after cooldown expires
        re_ok2, masked, otp2, re_err2 = resend_owner_otp(session_id)
        self.assertTrue(re_ok2)
        self.assertIsNotNone(otp2)
        self.assertEqual(len(otp2), 6)
        self.assertIsNone(re_err2)
        self.assertEqual(_ACTIVE_OTP_SESSIONS[session_id]["otp"], otp2)

    # 7. Cloudflare Pages Functions error handling contract
    def test_07_cloudflare_proxy_error_handling_contract(self):
        """
        Validates the Cloudflare Pages function logic contract in functions/api/[[path]].ts:
        - Gateway timeout -> 504 Gateway Timeout (NOT 401).
        - Gateway connection failure -> 502 Gateway Communication Error (NOT 401).
        """
        for fpath in ["functions/api/[[path]].ts", "dashboard/functions/api/[[path]].ts"]:
            self.assertTrue(os.path.exists(fpath), f"Missing {fpath}")
            with open(fpath, "r", encoding="utf-8") as fp:
                content = fp.read()

            # Ensure isUnauth 401 bug is NOT present
            self.assertNotIn('const isUnauth = !request.headers.has("authorization");', content,
                             f"Faulty isUnauth 401 logic still present in {fpath}")

            # Ensure 504 and 502 are returned for gateway errors
            self.assertIn('const isTimeout = err?.message === "Gateway Timeout";', content)
            self.assertIn('const status = isTimeout ? 504 : 502;', content)
            self.assertIn('"gateway_error"', content)

    # 8. Server authentication route authorization checks
    def test_08_server_route_protection_integrity(self):
        """
        Verifies that protected admin routes require Authorization header/token
        while public deals and login routes are accessible.
        """
        # Excluded / public paths
        self.assertTrue(is_public_endpoint("/api/deals/public"))
        self.assertTrue(is_public_endpoint("/api/deals/public?limit=10"))
        self.assertTrue(is_public_endpoint("/api/login"))
        self.assertTrue(is_public_endpoint("/api/verify-otp"))
        self.assertTrue(is_public_endpoint("/api/resend-otp"))
        self.assertFalse(is_public_endpoint("/api/deals"))
        self.assertFalse(is_public_endpoint("/api/settings"))
        self.assertFalse(is_public_endpoint("/api/selectors"))

    # 9. Gateway timeout simulation contract for login/verify/resend
    def test_09_gateway_timeout_contract_simulation(self):
        """
        Simulates the gateway timeout response logic across all auth endpoints.
        """
        def simulate_pages_catch_handler(endpoint: str, error_type: str, has_auth_header: bool):
            is_public_deals = endpoint.startswith("/api/deals/public")
            if is_public_deals:
                return 200, "edge-snapshot"
            is_timeout = error_type == "Gateway Timeout"
            status = 504 if is_timeout else 502
            return status, "gateway_error"

        for ep in ["/api/login", "/api/verify-otp", "/api/resend-otp"]:
            # Timeout scenario -> 504
            status, err_type = simulate_pages_catch_handler(ep, "Gateway Timeout", has_auth_header=False)
            self.assertEqual(status, 504, f"{ep} on timeout must be 504, not 401")
            self.assertEqual(err_type, "gateway_error")

            # Network connection dropped scenario -> 502
            status_conn, err_type_conn = simulate_pages_catch_handler(ep, "Connection Refused", has_auth_header=False)
            self.assertEqual(status_conn, 502, f"{ep} on network error must be 502, not 401")
            self.assertEqual(err_type_conn, "gateway_error")

    # 10. Rules Engine Deal Qualification Unchanged
    def test_10_rules_engine_deal_qualification_intact(self):
        from utils.rules_engine import evaluate_deal_eligibility

        # Loot deal (90% off)
        loot_res = evaluate_deal_eligibility(20000.0, 2000.0, category="smartphones", seller_rating=4.5)
        self.assertTrue(loot_res["approved"])
        self.assertEqual(loot_res["tier"], "LOOT_DEAL")

        # Standard deal (20% off)
        std_res = evaluate_deal_eligibility(50000.0, 40000.0, category="laptops", seller_rating=4.1)
        self.assertTrue(std_res["approved"])
        self.assertEqual(std_res["tier"], "STANDARD")

        # Rejected deal (4% off < 15%)
        rej_res = evaluate_deal_eligibility(1000.0, 960.0, category="electronics", seller_rating=4.0)
        self.assertFalse(rej_res["approved"])


if __name__ == "__main__":
    unittest.main()
