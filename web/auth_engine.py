"""
Loot Raiders Single-Owner Mobile OTP & Security Authentication Engine.
Enforces single-owner authorization with server-controlled mobile OTP verification.
Dispatches OTP via Twilio WhatsApp, Twilio SMS, Telegram Admin, and Fast2SMS.
"""

import os
import re
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


def format_e164_phone(phone: Optional[str]) -> str:
    """
    Enforces strict E.164 phone formatting.
    Normalizes Indian mobile numbers (10 digits) to +91XXXXXXXXXX.
    """
    if not phone or not isinstance(phone, str):
        return "+917302427167"

    clean = re.sub(r'[\s\-\(\)\.]', '', phone.strip())

    # Handle Indian mobile numbers without country code or with leading 0
    if len(clean) == 10 and clean.isdigit() and clean[0] in '6789':
        return f"+91{clean}"
    if len(clean) == 11 and clean.startswith("0") and clean[1:].isdigit():
        return f"+91{clean[1:]}"
    if len(clean) == 12 and clean.startswith("91") and clean[2:].isdigit():
        return f"+{clean}"
    if clean.startswith("+") and clean[1:].isdigit() and 7 <= len(clean) <= 16:
        return clean
    if clean.isdigit() and 10 <= len(clean) <= 15:
        return f"+{clean}"

    return "+917302427167"


def get_owner_credentials() -> Tuple[str, str, str, str]:
    """
    Retrieves authorized owner username, password, token, and owner mobile number in E.164 format.
    Returns (username, password, session_token, owner_mobile).
    """
    settings = load_settings()
    env_user = (os.environ.get("DASHBOARD_USERNAME") or settings.get("dashboard_username") or "yogeshpadwal16").strip().lower()
    env_pass = (os.environ.get("DASHBOARD_PASSWORD") or settings.get("dashboard_password") or "Vihan@143").strip()
    env_token = (os.environ.get("DASHBOARD_SESSION_TOKEN") or settings.get("dashboard_session_token") or "admin_session_key_default").strip()
    raw_mobile = (os.environ.get("OWNER_MOBILE_NUMBER") or settings.get("owner_mobile_number") or "+917302427167").strip()
    owner_mobile = format_e164_phone(raw_mobile)
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


def dispatch_twilio_otp(otp_code: str, formatted_mobile: str, masked_mobile: str) -> bool:
    """
    Dispatches OTP via Twilio Programmable Messaging (WhatsApp and/or SMS).
    Includes comprehensive error handling, exact error codes, and DLT guidance.
    """
    settings = load_settings()
    twilio_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or settings.get("twilio_account_sid", "")).strip()
    twilio_token = (os.environ.get("TWILIO_AUTH_TOKEN") or settings.get("twilio_auth_token", "")).strip()
    twilio_whatsapp_from = (os.environ.get("TWILIO_WHATSAPP_FROM") or settings.get("twilio_whatsapp_from", "+14155238886")).strip()
    twilio_sms_from = (os.environ.get("TWILIO_PHONE_NUMBER") or settings.get("twilio_phone_number", "")).strip()

    if not twilio_sid or not twilio_token or "YOUR_" in twilio_sid:
        logger.info("[Twilio] Credentials not configured or using default placeholders. Skipping Twilio dispatch.")
        return False

    delivered = False
    otp_msg_body = (
        f"🔐 Loot Raiders Owner Verification Code\n\n"
        f"Your 6-digit OTP code is: *{otp_code}*\n"
        f"Target Number: {masked_mobile}\n"
        f"Expires in 5 minutes. Do not share this code."
    )

    url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"

    # 1. Dispatch via Twilio WhatsApp
    if twilio_whatsapp_from:
        try:
            from_wa = twilio_whatsapp_from if twilio_whatsapp_from.startswith("whatsapp:") else f"whatsapp:{twilio_whatsapp_from}"
            to_wa = formatted_mobile if formatted_mobile.startswith("whatsapp:") else f"whatsapp:{formatted_mobile}"
            
            payload = {
                "From": from_wa,
                "To": to_wa,
                "Body": otp_msg_body
            }
            res = requests.post(url, data=payload, auth=(twilio_sid, twilio_token), timeout=8)
            res_data = {}
            try:
                res_data = res.json()
            except Exception:
                pass

            if res.status_code in [200, 201]:
                sid = res_data.get("sid", "N/A")
                logger.info(f"✅ [Twilio WhatsApp] OTP dispatched successfully to {masked_mobile} (Message SID: {sid})")
                delivered = True
            else:
                err_code = res_data.get("code", "UNKNOWN")
                err_msg = res_data.get("message", res.text)
                err_status = res_data.get("status", res.status_code)
                more_info = res_data.get("more_info", "")
                logger.warning(
                    f"❌ [Twilio WhatsApp Error] Status={err_status}, Code={err_code}: {err_msg} | Ref: {more_info}"
                )
                if err_code == 63016:
                    logger.info(
                        "💡 [Twilio Sandbox Note]: For WhatsApp Sandbox, recipient must join by sending 'join <sandbox-keyword>' to +1 415 523 8886."
                    )
        except Exception as tw_wa_err:
            logger.error(f"[Twilio WhatsApp Exception]: {tw_wa_err}")

    # 2. Dispatch via Twilio Programmable SMS
    if twilio_sms_from:
        try:
            from_sms = twilio_sms_from.replace("whatsapp:", "").strip()
            to_sms = formatted_mobile.replace("whatsapp:", "").strip()

            payload = {
                "From": from_sms,
                "To": to_sms,
                "Body": f"Loot Raiders Security Code: {otp_code}. Valid for 5 minutes. Do not share."
            }
            res = requests.post(url, data=payload, auth=(twilio_sid, twilio_token), timeout=8)
            res_data = {}
            try:
                res_data = res.json()
            except Exception:
                pass

            if res.status_code in [200, 201]:
                sid = res_data.get("sid", "N/A")
                logger.info(f"✅ [Twilio SMS] OTP SMS dispatched successfully to {masked_mobile} (Message SID: {sid})")
                delivered = True
            else:
                err_code = res_data.get("code", "UNKNOWN")
                err_msg = res_data.get("message", res.text)
                err_status = res_data.get("status", res.status_code)
                more_info = res_data.get("more_info", "")
                logger.warning(
                    f"❌ [Twilio SMS Error] Status={err_status}, Code={err_code}: {err_msg} | Ref: {more_info}"
                )
                if formatted_mobile.startswith("+91"):
                    logger.warning(
                        "⚠️ [Twilio India SMS / DLT Notice]: International A2P SMS to Indian mobile numbers (+91) "
                        "requires Indian TRAI DLT Principal Entity & Template Registration. "
                        "Also ensure Twilio SMS Geographic Permissions for 'India' are enabled at "
                        "https://console.twilio.com/us1/develop/sms/settings/geo-permissions"
                    )
        except Exception as tw_sms_err:
            logger.error(f"[Twilio SMS Exception]: {tw_sms_err}")

    return delivered


def dispatch_telegram_otp(otp_code: str, masked_mobile: str) -> None:
    """
    Dispatches OTP verification code STRICTLY to a private Admin User ID or mobile number.
    CRITICAL SECURITY GUARD: Never sends OTP to public channels (starting with @ or -100).
    """
    settings = load_settings()
    owner_mobile = format_e164_phone(os.environ.get("OWNER_MOBILE_NUMBER") or settings.get("owner_mobile_number"))

    # Local Dev / Debug Mode Banner
    debug_mode = os.environ.get("DEBUG_OTP", "").lower() in ["true", "1", "yes"] or settings.get("debug_otp", False)
    if debug_mode:
        logger.info(
            f"\n"
            f"======================================================================\n"
            f"🔐 [DEBUG_OTP ACTIVE] Owner Security Code: {otp_code} | Target: {masked_mobile}\n"
            f"======================================================================"
        )

    # 1. Dispatch via Twilio (WhatsApp & SMS)
    try:
        dispatch_twilio_otp(otp_code, owner_mobile, masked_mobile)
    except Exception as e:
        logger.warning(f"Twilio dispatch pipeline error: {e}")

    # 2. Dispatch via Private Telegram Admin Chat
    try:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or settings.get("telegram_bot_token")
        chat_id = os.environ.get("ADMIN_TELEGRAM_USER_ID") or settings.get("admin_telegram_user_id")

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

    # 3. Dispatch via Fast2SMS Gateway (if configured)
    try:
        sms_api_key = os.environ.get("SMS_API_KEY") or settings.get("sms_api_key")
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
            logger.info(f"Dispatched OTP via Fast2SMS to registered mobile number: {masked_mobile}")
    except Exception as sms_err:
        logger.warning(f"Fast2SMS dispatch skipped/failed: {sms_err}")


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

    # Log OTP session creation
    logger.info(f"🔑 [OWNER SECURITY OTP]: Session created for Target: {masked_mobile}, Session: {session_id[:8]}")

    # Dispatch to Twilio/Telegram/SMS asynchronously in background thread
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

    # Dispatch to Twilio/Telegram/SMS asynchronously in background thread
    threading.Thread(target=dispatch_telegram_otp, args=(new_otp, masked), daemon=True).start()

    return True, masked, new_otp, None
