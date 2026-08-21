#!/bin/bash
# start_loot_scraper.sh - Starts the Loot Raiders scraper inside a virtual framebuffer (Xvfb)
# Required because Meesho needs headed Chromium (headless=False) to pass anti-bot checks.

export DISPLAY=:99
xvfb-run --server-args="-screen 0 1280x720x24" /var/www/loot-raiders/venv/bin/python loot_scraper.py
