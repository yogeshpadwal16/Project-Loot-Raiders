# utils/shlink.py
import requests
import logging

_shlink_offline_logged = False

class ShlinkClient:
    """
    Enterprise API client wrapper for self-hosted Shlink URL Shortener.
    Provides automated trackable link generation with tags and custom slugs.
    """
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
    def shorten_url(self, long_url: str, custom_slug: str = None, tags: list = None) -> str:
        """
        Submits a long link to Shlink to create a trackable slug.
        Falls back to the original URL if Shlink is unreachable.
        """
        global _shlink_offline_logged
        endpoint = f"{self.base_url}/rest/v3/short-urls"
        payload = {
            "longUrl": long_url,
            "findIfExists": True,
            "validateUrl": False
        }
        if custom_slug:
            payload["customSlug"] = custom_slug
        if tags:
            payload["tags"] = tags
            
        try:
            res = requests.post(endpoint, json=payload, headers=self.headers, timeout=8)
            if res.status_code in [200, 201]:
                return res.json().get("shortUrl", long_url)
            else:
                logging.error(f"Shlink API shortening failed ({res.status_code}): {res.text}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as conn_err:
            if not _shlink_offline_logged:
                logging.info("[INFO] Shlink shortener offline - using direct URL")
                _shlink_offline_logged = True
        except Exception as e:
            if not _shlink_offline_logged:
                logging.info("[INFO] Shlink shortener offline - using direct URL")
                _shlink_offline_logged = True
            
        return long_url

    def get_visits_velocity(self, short_code: str, minutes: int = 10) -> int:
        """
        Retrieves the number of visits to a short URL in the last X minutes.
        """
        from datetime import datetime, timedelta, timezone
        start_date = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        
        # Shlink v3 visits endpoint with startDate filter
        endpoint = f"{self.base_url}/rest/v3/short-urls/{short_code}/visits"
        params = {"startDate": start_date}
        
        try:
            res = requests.get(endpoint, headers=self.headers, params=params, timeout=4)
            if res.status_code == 200:
                data = res.json()
                visits_obj = data.get("visits") or {}
                total = visits_obj.get("pagination", {}).get("totalItems")
                if total is None:
                    total = visits_obj.get("total")
                if total is None:
                    total = len(visits_obj.get("data", []))
                return int(total)
        except Exception as e:
            global _shlink_offline_logged
            if not _shlink_offline_logged:
                logging.info("[INFO] Shlink shortener offline - using direct URL")
                _shlink_offline_logged = True
        return 0


def check_loot_velocity(short_code: str) -> str | None:
    """Checks click velocity in the past 10 minutes to generate social proof badges."""
    from config.settings import load_settings
    settings = load_settings()
    shlink_url = settings.get("shlink_api_url", "").strip()
    shlink_key = settings.get("shlink_api_key", "").strip()

    if not shlink_url or not shlink_key or "YOUR_SHLINK" in shlink_key:
        return None

    client = ShlinkClient(shlink_url, shlink_key)
    total_clicks = client.get_visits_velocity(short_code, minutes=10)
    if total_clicks >= 50:
        return f"🔥 <b>High Demand:</b> {total_clicks} users clicked this deal in the last 10 mins!"
    return None

