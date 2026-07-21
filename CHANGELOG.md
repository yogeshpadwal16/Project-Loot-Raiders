<![CDATA[# 📋 Changelog

All notable changes to Project Loot Raiders are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [3.0.0] — 2026-07-21

### ✨ Added
- **PWA Support** — installable app with service worker, offline caching, app manifest, and 192/512px icons
- **Supermarket deals monitor** — tracks grocery and FMCG deals
- **Docker containerization** — Dockerfile for one-command deployment
- **VPS deployment scripts** — PowerShell (Windows) and Bash (Linux) deploy automation
- **PM2 ecosystem config** — process management with auto-restart
- **Expanded test suite** — comprehensive unit tests for parser, scorer, affiliate, and auto-cart
- **PWA install banner** — prompts users to install the app on mobile/desktop

### 🔄 Changed
- **Dashboard UI overhaul** — neo-brutalist premium dark theme with liquid blob animations
- **Enhanced notification engine** — 300+ lines of improvements to multi-channel broadcasting
- **Bot listener upgrades** — 200+ lines of Telegram bot improvements
- **Improved Playwright adapter** — better URL resolution and driver management

### 🐛 Fixed
- Gemini API model upgraded to `gemini-3.5-flash` with 25s timeouts
- Resolved relative href/src URL resolution in Playwright adapter
- Fixed scraper deadlock by reusing driver in `scrape_product_details`
- Fixed NULL username values in UserScore database table
- Resolved `SessionLocal` UnboundLocalError and 401 redirect loop
- Removed duplicate Telegram card widget from user page sidebar

---

## [2.5.0] — 2026-07-18

### ✨ Added
- **Premium indicators** — forecasting, offline mode, cashback, cancel risk, auto-cart badges
- **Gamification widgets** — scratch cards, loot map, interactive rewards
- **Next-gen APIs** — scraper health metrics, live lootmap events, Chrome extension matcher
- **Price error cancel risk analysis** — predicts deal cancellation probability
- **Forecasting & EPC analytics** — predictive deal performance metrics
- **Geo-targeted maps** — location-based deal discovery

### 🔄 Changed
- Upgraded frontend rendering for premium indicators and gamification widgets

---

## [2.4.0] — 2026-07-17

### ✨ Added
- **Yield maximizer** — optimizes affiliate revenue per click
- **Auto-cart links** — one-click add-to-cart for Amazon and Flipkart
- **Link cloaker** — clean branded redirect URLs
- **Gamification & referral loops** — viral growth mechanics
- **Pre-sale checklists** — deal verification before publishing
- **Supermarket tracker backend** — grocery deal monitoring infrastructure
- **Cloud Telethon authentication** — string session support for GitHub Actions
- **Cuelinks & EarnKaro publisher ID** settings exposed in Admin Dashboard

### 🔄 Changed
- GitHub Actions upgraded to 2-minute loop runner with concurrency overlap control

---

## [2.3.0] — 2026-07-17

### ✨ Added
- **Self-healing selector fallback** — Gemini AI auto-repairs broken CSS selectors
- **Dashboard API security** — Bearer token authorization for admin endpoints
- **Affiliate Link Router** — intelligent routing to Cuelinks and EarnKaro
- **Crawler health telemetry widget** — real-time platform monitoring on dashboard
- **WhatsApp viral marketing loop** — share buttons on deal cards

### 🔄 Changed
- Modularized relative product URL resolution in affiliate pipeline
- Updated TODO.md roadmap with Co-Founder Growth Initiatives

---

## [2.2.0] — 2026-07-17

### ✨ Added
- **Gemini AI deal ranking** — DIE (Deal Intelligence Engine) scoring system
- **Single-run mirroring mode** — one-shot competitor channel scan
- **Ajio Akamai bypass** — `curl-cffi` direct API crawler
- **Spotlight Deal of the Hour widget** — featured deal on dashboard
- **Telegram channel buttons** — direct join buttons on every deal card

### 🔄 Changed
- Replaced redundant Telegram promo widget with dynamic Spotlight Deal widget
- Renamed Telegram Discussion Group widget to Telegram Channel

---

## [2.1.0] — 2026-07-17

### ✨ Added
- **Dynamic price history charts** — interactive Chart.js sparklines
- **Playwright browser engine** — replaced Selenium for faster, more reliable scraping
- **Competitor Telegram channel mirroring** — auto-ingests deals from rival channels
- **GitHub Actions CI/CD** — automated runs every 15 minutes (6 AM–2 AM IST)
- **Multi-platform metadata scraper** — unified scraping across all retailers

### 🔄 Changed
- Complete separation of public `index.html` from `admin.html`
- SQLite upgraded to WAL mode for concurrent read/write safety
- Modularized codebase into `core/`, `deal_engine/`, `plugins/`, `utils/`

---

## [2.0.0] — 2026-07-16

### ✨ Added
- **Telegram notifications** — channel broadcasting and bot listener
- **Discord webhooks** — real-time deal alerts
- **Email alerts** — SMTP and SendGrid integration
- **Price history tracking** — SQLite storage with line charts
- **Click tracking & analytics** — per-deal and per-platform metrics
- **Referral loop tracking** — click-through rate analysis from WhatsApp shares
- **Channel growth analytics** — subscriber growth telemetry

### 🔄 Changed
- Multi-threaded scraping for faster execution
- Automatic Chrome update detection
- Improved retry logic for failed requests
- Enhanced logging system

---

## [1.1.0]

### 🔄 Changed
- Improved CSS selectors for better deal extraction
- Better execution logging

---

## [1.0.0]

### ✨ Added
- Initial release
- Basic web scraper for deal aggregation
- Dashboard for viewing collected deals
- Click tracking system
- JSON-based deal history storage
- Configurable CSS selectors via `selectors.json`
]]>