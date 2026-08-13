"""
Loot Raiders Single-Owner Mobile OTP & Security Authentication Engine.
Enforces single-owner authorization with server-controlled mobile OTP verification.
Dispatches OTP to Telegram Bot / Server Logs for instant receipt.
"""

import os
import time
import secrets
import logging
import requests
from typing import Dict, Optional, Tuple, Any
from config.settings import load_settings

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
    """Masks a phone number securely (e.g., +917302427167 -> +91 ******7167)."""
    if not mobile:
        return "+91 ******7167"
    clean = mobile.strip()
    if len(clean) >= 10:
        prefix = clean[:3] if clean.startswith("+") else "+91"
        suffix = clean[-4:]
        return f"{prefix} ******{suffix}"
    return "+91 ******7167"


def dispatch_telegram_otp(otp_code: str, masked_mobile: str) -> None:
    """Dispatches OTP verification code to configured Telegram bot/chat for instant receipt."""
    try:
        settings = load_settings()
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or settings.get("telegram_bot_token")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID") or settings.get("telegram_chat_id")

        if bot_token and chat_id and "YOUR_TELEGRAM" not in bot_token:
            msg_text = (
                f"🔐 *Loot Raiders Owner Verification Code*\n\n"
                f"Your 6-digit OTP code is: `{otp_code}`\n"
                f"Target Number: {masked_mobile}\n"
                f"Expires in 5 minutes. Do not share this code."
            )
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            requests.post(
                url,
                json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown"},
                timeout=5,
            )
            logger.info(f"Dispatched OTP code to Telegram chat_id={chat_id}")
    except Exception as e:
        logger.warning(f"Could not dispatch OTP via Telegram: {e}")


def initiate_owner_login(username: str, password: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Validates owner credentials. If valid, generates 6-digit OTP and returns (True, session_id, masked_mobile, otp_code, error).
    """
    env_user, env_pass, _, owner_mobile = get_owner_credentials()
    
    if username.strip().lower() != env_user or password.strip() != env_pass:
        logger.warning(f"Failed owner login attempt for username='{username}'")
        return False, None, None, None, "Invalid username or password."

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

    # Log OTP prominently in application execution log
    logger.info(f"🔑 [OWNER SECURITY OTP CODE]: {otp_code} (Target: {masked_mobile}, Session: {session_id[:8]})")
    print(f"\n======================================================\n🔑 [LOOT RAIDERS OWNER OTP CODE]: {otp_code}\n======================================================\n")

    # Dispatch to Telegram bot if available
    dispatch_telegram_otp(otp_code, masked_mobile)

    return True, session_id, masked_mobile, otp_code, None


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


def resend_owner_otp(session_id: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Resends fresh OTP for active session after checking cooldown throttle.
    Returns (True, masked_mobile, otp_code, None) or (False, None, None, error_message).
    """
    if not session_id or session_id not in _ACTIVE_OTP_SESSIONS:
        return False, None, None, "Session not found. Please start login again."

    session = _ACTIVE_OTP_SESSIONS[session_id]
    now = time.time()

    if now > session["expires_at"]:
        del _ACTIVE_OTP_SESSIONS[session_id]
        return False, None, None, "Session expired. Please log in again."

    elapsed = now - session["last_resend_at"]
    if elapsed < RESEND_COOLDOWN_SEC:
        remaining = int(RESEND_COOLDOWN_SEC - elapsed)
        return False, None, None, f"Please wait {remaining} second(s) before requesting another code."

    # Generate fresh OTP
    new_otp = f"{secrets.randbelow(900000) + 100000}"
    session["otp"] = new_otp
    session["last_resend_at"] = now
    session["expires_at"] = now + SESSION_EXPIRY_SEC
    session["attempts"] = 0

    _, _, _, owner_mobile = get_owner_credentials()
    masked = mask_mobile_number(owner_mobile)
    
    logger.info(f"🔑 [RESENT OWNER SECURITY OTP CODE]: {new_otp} (Target: {masked}, Session: {session_id[:8]})")
    print(f"\n======================================================\n🔑 [LOOT RAIDERS RESENT OTP CODE]: {new_otp}\n======================================================\n")

    dispatch_telegram_otp(new_otp, masked)

    return True, masked, new_otp, None
