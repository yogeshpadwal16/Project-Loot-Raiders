import os
import logging
import requests
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("loot_raiders.social_proof")


def check_loot_velocity(short_code: str, minutes: int = 10) -> str | None:
    """
    Checks the click velocity in the past X minutes from Shlink redirect logs
    to output high-demand social proof tags.
    """
    shlink_url = os.environ.get("SHLINK_API_URL", "").strip()
    shlink_key = os.environ.get("SHLINK_API_KEY", "").strip()

    if not shlink_url or not shlink_key or "example" in shlink_url.lower():
        return None

    # Calculate startDate 10 minutes ago in ISO 8601
    start_date = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    endpoint = f"{shlink_url.rstrip('/')}/rest/v3/short-urls/{short_code}/visits"
    params = {"startDate": start_date}
    headers = {"X-Api-Key": shlink_key}

    try:
        res = requests.get(endpoint, headers=headers, params=params, timeout=4)
        if res.status_code == 200:
            data = res.json()
            visits_obj = data.get("visits", {})
            total = visits_obj.get("pagination", {}).get("totalItems")
            if total is None:
                total = visits_obj.get("total")
            if total is None:
                total = len(visits_obj.get("data", []))

            total_clicks = int(total)
            if total_clicks >= 50:
                return f"🔥 <b>High Demand:</b> {total_clicks} users clicked this deal in the last 10 mins!"
    except Exception as e:
        logger.warning(f"[SOCIAL_PROOF] Visits check failed for {short_code}: {e}")

    return None
