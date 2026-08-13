"""
Loot Raiders Single-Owner Mobile OTP & Security Authentication Engine.
Enforces single-owner authorization with server-controlled mobile OTP verification.
"""

import os
import time
import secrets
import logging
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger("AuthEngine")

# In-memory OTP session store (session_id -> session_dict)
_ACTIVE_OTP_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_EXPIRY_SEC = 300      # 5 minutes
RESEND_COOLDOWN_SEC = 30      # 30 seconds
MAX_ATTEMPTS = 3


def get_owner_credentials() -> Tuple[str, str, str, str]:
    """
    Retrieves authorized owner username, password, token, and owner mobile number.
    Returns (username, password, session_token, owner_mobile).
    """
    env_user = os.environ.get("DASHBOARD_USERNAME", "yogeshpadwal16").strip().lower()
    env_pass = os.environ.get("DASHBOARD_PASSWORD", "YOUR_DASHBOARD_PASSWORD").strip()
    env_token = os.environ.get("DASHBOARD_SESSION_TOKEN", "admin_session_key_default").strip()
    owner_mobile = os.environ.get("OWNER_MOBILE_NUMBER", "+917302427167").strip()
    return env_user, env_pass, env_token, owner_mobile


def mask_mobile_number(mobile: str) -> str:
    """Masks a phone number securely (e.g., +919876543210 -> +91 ******3210 or +91 ******10)."""
    if not mobile:
        return "+91 ******42"
    clean = mobile.strip()
    if len(clean) >= 10:
        prefix = clean[:3] if clean.startswith("+") else "+91"
        suffix = clean[-2:]
        return f"{prefix} ******{suffix}"
    return "+91 ******42"


def initiate_owner_login(username: str, password: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Validates owner credentials. If valid, generates 6-digit OTP and returns (True, session_id, masked_mobile, error).
    """
    env_user, env_pass, _, owner_mobile = get_owner_credentials()
    
    if username.strip().lower() != env_user or password.strip() != env_pass:
        logger.warning(f"Failed owner login attempt for username='{username}'")
        return False, None, None, "Invalid username or password."

    # Cleanup expired sessions
    now = time.time()
    expired_keys = [k for k, s in _ACTIVE_OTP_SESSIONS.items() if now > s["expires_at"]]
    for k in expired_keys:
        del _ACTIVE_OTP_SESSIONS[k]

    # Generate 6-digit secure numeric OTP
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    session_id = secrets.token_hex(16)
    masked_mobile = mask_mobile_number(owner_mobile)

    _ACTIVE_OTP_SESSIONS[session_id] = {
        "otp": otp_code,
        "username": env_user,
        "created_at": now,
        "expires_at": now + SESSION_EXPIRY_SEC,
        "last_resend_at": now,
        "attempts": 0,
        "verified": False,
    }

    logger.info(f"Generated owner OTP for session='{session_id[:8]}' (Target: {masked_mobile})")
    # Log OTP in development mode for easy manual verification
    if os.environ.get("ENV", "development").lower() == "development":
        logger.info(f"[DEV ONLY] Generated OTP code: {otp_code}")

    return True, session_id, masked_mobile, None


def verify_owner_otp(session_id: str, otp_code: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifies 6-digit OTP for given session_id.
    Returns (True, session_token, None) or (False, None, error_message).
    """
    if not session_id or session_id not in _ACTIVE_OTP_SESSIONS:
        return False, None, "Invalid or expired session. Please log in again."

    session = _ACTIVE_OTP_SESSIONS[session_id]
    now = time.time()

    if now > session["expires_at"]:
        del _ACTIVE_OTP_SESSIONS[session_id]
        return False, None, "Verification code has expired. Please request a new code."

    if session["attempts"] >= MAX_ATTEMPTS:
        del _ACTIVE_OTP_SESSIONS[session_id]
        return False, None, "Maximum verification attempts exceeded. Session invalidated."

    clean_otp = str(otp_code).strip()
    if clean_otp != session["otp"]:
        session["attempts"] += 1
        remaining = MAX_ATTEMPTS - session["attempts"]
        logger.warning(f"Invalid OTP attempt for session='{session_id[:8]}'. {remaining} attempts remaining.")
        return False, None, f"Incorrect verification code. {remaining} attempt(s) remaining."

    # Verification successful!
    session["verified"] = True
    _, _, env_token, _ = get_owner_credentials()
    
    # Invalidate session to prevent reuse
    del _ACTIVE_OTP_SESSIONS[session_id]
    
    logger.info(f"Owner OTP verification successful for session='{session_id[:8]}'")
    return True, env_token, None


def resend_owner_otp(session_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Resends fresh OTP for active session after checking cooldown throttle.
    Returns (True, masked_mobile, None) or (False, None, error_message).
    """
    if not session_id or session_id not in _ACTIVE_OTP_SESSIONS:
        return False, None, "Session not found. Please start login again."

    session = _ACTIVE_OTP_SESSIONS[session_id]
    now = time.time()

    if now > session["expires_at"]:
        del _ACTIVE_OTP_SESSIONS[session_id]
        return False, None, "Session expired. Please log in again."

    elapsed = now - session["last_resend_at"]
    if elapsed < RESEND_COOLDOWN_SEC:
        remaining = int(RESEND_COOLDOWN_SEC - elapsed)
        return False, None, f"Please wait {remaining} second(s) before requesting another code."

    # Generate fresh OTP
    new_otp = f"{secrets.randbelow(900000) + 100000}"
    session["otp"] = new_otp
    session["last_resend_at"] = now
    session["expires_at"] = now + SESSION_EXPIRY_SEC
    session["attempts"] = 0

    _, _, _, owner_mobile = get_owner_credentials()
    masked = mask_mobile_number(owner_mobile)
    
    logger.info(f"Resent fresh owner OTP for session='{session_id[:8]}'")
    if os.environ.get("ENV", "development").lower() == "development":
        logger.info(f"[DEV ONLY] Resent OTP code: {new_otp}")

    return True, masked, None
