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
import threading
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
    """
    Dispatches OTP verification code STRICTLY to a private Admin User ID or mobile number.
    CRITICAL SECURITY GUARD: Never sends OTP to public channels (starting with @ or -100).
    """
    try:
        settings = load_settings()
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or settings.get("telegram_bot_token")
        
        # Only use dedicated ADMIN_TELEGRAM_USER_ID (a private individual chat ID, NOT a public channel)
        chat_id = os.environ.get("ADMIN_TELEGRAM_USER_ID") or settings.get("admin_telegram_user_id")

        # STRICT CHANNEL BLOCKER: If chat_id is a channel handle or broadcast group, BLOCK IT
        if chat_id and (str(chat_id).startswith("@") or str(chat_id).startswith("-100")):
            logger.error(f"🚨 SECURITY CRITICAL GUARD: Blocked OTP dispatch to public channel/group '{chat_id}'.")
            chat_id = None

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
                json={"chat_id": str(chat_id), "text": msg_text, "parse_mode": "Markdown"},
                timeout=5,
            )
            logger.info(f"Dispatched private OTP code to Admin user chat_id={chat_id}")
    except Exception as e:
        logger.warning(f"Could not dispatch OTP via Telegram: {e}")

    # Dispatch via Twilio WhatsApp if configured
    try:
        twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID") or settings.get("twilio_account_sid")
        twilio_token = os.environ.get("TWILIO_AUTH_TOKEN") or settings.get("twilio_auth_token")
        twilio_whatsapp_from = os.environ.get("TWILIO_WHATSAPP_FROM") or settings.get("twilio_whatsapp_from", "+14155238886")
        owner_mobile = os.environ.get("OWNER_MOBILE_NUMBER", "+917302427167").strip()

        if twilio_sid and twilio_token and "YOUR_" not in twilio_sid and owner_mobile:
            msg_text = (
                f"🔐 *Loot Raiders Owner Verification Code*\n\n"
                f"Your 6-digit OTP code is: *{otp_code}*\n"
                f"Target Number: {masked_mobile}\n"
                f"Expires in 5 minutes. Do not share this code."
            )
            from_wa = twilio_whatsapp_from if twilio_whatsapp_from.startswith("whatsapp:") else f"whatsapp:{twilio_whatsapp_from}"
            to_wa = owner_mobile if owner_mobile.startswith("whatsapp:") else f"whatsapp:{owner_mobile}"
            
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            payload = {
                "From": from_wa,
                "To": to_wa,
                "Body": msg_text
            }
            res = requests.post(url, data=payload, auth=(twilio_sid, twilio_token), timeout=8)
            if res.status_code in [200, 201]:
                logger.info(f"Dispatched OTP via Twilio WhatsApp to {masked_mobile}")
            else:
                logger.warning(f"Twilio WhatsApp dispatch failed ({res.status_code}): {res.text}")
    except Exception as tw_err:
        logger.warning(f"Twilio WhatsApp dispatch error: {tw_err}")

    # Dispatch via Mobile SMS if SMS Gateway API (Fast2SMS) is configured
    try:
        sms_api_key = os.environ.get("SMS_API_KEY") or settings.get("sms_api_key")
        owner_mobile = os.environ.get("OWNER_MOBILE_NUMBER", "+917302427167").strip()
        clean_mobile = owner_mobile.replace("+91", "").replace("+", "").strip()
        
        if sms_api_key and "YOUR_" not in sms_api_key and clean_mobile:
            sms_url = "https://www.fast2sms.com/dev/bulkV2"
            sms_payload = {
                "route": "otp",
                "variables_values": otp_code,
                "numbers": clean_mobile
            }
            sms_headers = {"authorization": sms_api_key}
            requests.post(sms_url, data=sms_payload, headers=sms_headers, timeout=5)
            logger.info(f"Dispatched OTP via SMS to registered mobile number: {masked_mobile}")
    except Exception as sms_err:
        logger.warning(f"SMS Gateway dispatch skipped/failed: {sms_err}")


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

    # Log OTP session creation securely without leaking secrets to stdout
    logger.info(f"🔑 [OWNER SECURITY OTP]: Session created for Target: {masked_mobile}, Session: {session_id[:8]}")

    # Dispatch to Telegram/SMS asynchronously in background thread to prevent HTTP response blocking
    threading.Thread(target=dispatch_telegram_otp, args=(otp_code, masked_mobile), daemon=True).start()

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
        if session["attempts"] >= MAX_ATTEMPTS:
            del _ACTIVE_OTP_SESSIONS[session_id]
            logger.warning(f"Maximum verification attempts exceeded for session='{session_id[:8]}'. Session invalidated.")
            return False, None, "Maximum verification attempts exceeded. Session invalidated."
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
    
    logger.info(f"🔑 [RESENT OWNER SECURITY OTP]: Generated for Target: {masked}, Session: {session_id[:8]}")

    # Dispatch to Telegram/SMS asynchronously in background thread to prevent HTTP response blocking
    threading.Thread(target=dispatch_telegram_otp, args=(new_otp, masked), daemon=True).start()

    return True, masked, new_otp, None
