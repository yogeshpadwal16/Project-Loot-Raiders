# utils/shlink.py
import requests
import logging

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
        except Exception as e:
            logging.error(f"Failed to connect to Shlink redirect server: {e}")
            
        return long_url
