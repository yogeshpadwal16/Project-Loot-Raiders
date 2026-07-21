<![CDATA[# 🏴‍☠️ Project Loot Raiders

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Docker-blue?style=for-the-badge)
![Telegram](https://img.shields.io/badge/Telegram-@LootRaidersDeals-0088cc?style=for-the-badge&logo=telegram)

**An intelligent, AI-powered deal discovery & automation platform** that scrapes, scores, and broadcasts the best shopping deals from 7+ Indian e-commerce platforms — powered by Gemini AI.

---

## ⚡ Quick Start

```bash
# Clone the repository
git clone https://github.com/yogeshpadwal16/Project-Loot-Raiders.git
cd Project-Loot-Raiders

# Install dependencies
pip install -r requirements.txt

# Configure your API keys
cp .env.example .env
# Edit .env with your Telegram bot token, Gemini API key, etc.

# Run the scraper
python loot_scraper.py
```

The dashboard will be available at **http://127.0.0.1:5555/**

---

## 🎯 What It Does

Loot Raiders automatically discovers deals from **Amazon, Flipkart, Myntra, Ajio, Meesho, TataCliq, and JioMart**, scores them using **Gemini AI**, and broadcasts the best ones to **Telegram, Discord, and Email** — all while you sleep.

---

## ✨ Features

### 🔍 Scraping Engine
- **7-platform support**: Amazon, Flipkart, Myntra, Ajio, Meesho, TataCliq, JioMart
- **Playwright browser automation** with Akamai anti-bot bypass
- **Self-healing CSS selectors** — Gemini AI auto-repairs broken selectors
- **Multi-threaded concurrent scraping** for maximum speed
- **Redirect URL expander** for shortened/affiliate links
- **Blocklist keyword filtering** to skip junk deals

### 🤖 AI-Powered Intelligence
- **Gemini AI Deal Scoring** (DIE — Deal Intelligence Engine)
- **Cancellation risk analysis** for price-error detection
- **Historical price verification** — flags all-time lows
- **Smart deal ranking** with configurable weight scoring

### 📡 Multi-Channel Broadcasting
- **Telegram** channel broadcasting (@LootRaidersDeals)
- **Telegram bot** command listener with interactive controls
- **Discord** webhook notifications
- **Email alerts** via SMTP / SendGrid
- **WhatsApp** viral referral sharing loop

### 📊 Dashboard & Analytics
- **Public deals dashboard** — premium neo-brutalist dark UI
- **Admin control panel** — full system management
- **Crawler health telemetry** — real-time monitoring per platform
- **Click tracking & analytics** — top deals, platform distribution
- **Channel growth analytics** — subscriber telemetry
- **Price history sparkline charts** — Chart.js visualizations
- **Spotlight Deal of the Hour** widget

### 📱 Progressive Web App (PWA)
- **Installable** on mobile and desktop
- **Offline-capable** with service worker caching
- **Network-first** strategy for live data, cache-first for assets
- **App shortcuts** for quick access

### 💰 Monetization
- **Affiliate link routing** — Amazon Associates, Cuelinks, EarnKaro
- **Auto-cart link generation** for Amazon and Flipkart
- **Smart commission optimization** — routes to highest-paying network per platform
- **Click-through tracking** for revenue attribution

### 🔄 Acquisition Engines
- **Catalog monitoring** — scans deal pages on schedule
- **Competitor Telegram channel mirroring** — auto-ingests deals from rival channels
- **Supermarket deals monitor** — tracks grocery/FMCG deals

### 🛡️ Reliability & Operations
- **GitHub Actions CI/CD** — runs every 15 minutes (6 AM–2 AM IST)
- **Docker containerization** — one-command deployment
- **PM2 process management** — auto-restart, log rotation
- **VPS deployment scripts** — PowerShell & Bash
- **Dashboard API security** — Bearer token authentication
- **Zombie/stale deal cleanup** — automatic pruning
- **SQLite WAL mode** — concurrent read/write safety

---

## 📁 Project Structure

```
Project-Loot-Raiders/
│
├── core/
│   └── engine.py                 # Main scraper loop & system state
│
├── deal_engine/
│   ├── scorer.py                 # Gemini AI deal scoring (DIE engine)
│   ├── notifier.py               # Multi-channel notification engine
│   ├── bot_listener.py           # Telegram bot command listener
│   ├── channel_mirror.py         # Competitor channel mirroring
│   ├── deal_processor.py         # Deal metadata & URL processing
│   ├── catalog_monitor.py        # Catalog URL monitoring
│   └── supermarket_monitor.py    # Supermarket deals tracker
│
├── plugins/
│   ├── base_plugin.py            # Base retailer plugin interface
│   ├── amazon.py                 # Amazon scraper plugin
│   ├── flipkart.py               # Flipkart scraper plugin
│   └── generic.py                # Multi-retailer plugin (Myntra, Ajio, etc.)
│
├── dashboard/
│   ├── index.html                # Public deals dashboard (PWA)
│   ├── admin.html                # Admin control panel
│   ├── index.css                 # Premium neo-brutalist dark UI
│   ├── index.js                  # Dashboard logic & real-time updates
│   ├── manifest.json             # PWA manifest
│   └── sw.js                     # Service worker (offline support)
│
├── database/
│   ├── db_session.py             # SQLAlchemy session management
│   └── operations.py             # CRUD operations & price verification
│
├── knowledge_base/
│   └── models.py                 # SQLAlchemy models
│
├── web/
│   └── server.py                 # REST API server (50+ endpoints)
│
├── utils/
│   ├── playwright_adapter.py     # Browser automation engine
│   ├── parser.py                 # Price/URL/text parsing
│   ├── affiliate.py              # Affiliate link routing
│   ├── image_generator.py        # Deal card image generation
│   └── zombie.py                 # Stale deal cleanup
│
├── config/
│   ├── settings.py               # Settings loader
│   └── catalog_urls.json         # Monitored catalog URLs
│
├── scripts/
│   ├── loop_runner.py            # GitHub Actions loop runner
│   ├── generate_session_string.py
│   ├── migrate_json_to_db.py     # JSON to SQLite migration
│   ├── deploy_to_vps.ps1         # VPS deployment (Windows)
│   └── setup_vps.sh              # VPS setup (Linux)
│
├── tests/
│   └── test_loot_raiders.py      # Unit tests
│
├── .github/workflows/            # GitHub Actions CI/CD
├── Dockerfile                    # Docker containerization
├── ecosystem.config.js           # PM2 process manager config
├── settings.json                 # Runtime configuration
├── selectors.json                # CSS selectors for scraping
├── requirements.txt              # Python dependencies
└── README.md
```

---

## ⚙️ Configuration

### settings.json

| Setting | Description |
|---------|-------------|
| `telegram_bot_token` | Telegram Bot API token |
| `telegram_chat_id` | Telegram channel/group chat ID |
| `gemini_api_key` | Google Gemini AI API key |
| `amazon_tag` | Amazon Associates affiliate tag |
| `flipkart_affid` | Flipkart affiliate ID |
| `cuelinks_pub_id` | Cuelinks publisher ID |
| `earnkaro_pub_id` | EarnKaro publisher ID |
| `discord_webhook_url` | Discord webhook URL |
| `min_discount` | Minimum discount % threshold (default: 30%) |
| `min_deal_price` | Minimum deal price filter (default: ₹149) |
| `blocklist_keywords` | Keywords to filter out junk deals |
| `scoring_rules` | AI scoring weights and thresholds |

### Environment Variables (.env)

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token
GEMINI_API_KEY=your_gemini_key
DASHBOARD_SESSION_TOKEN=your_admin_token
```

---

## 🐳 Docker Deployment

```bash
docker build -t loot-raiders .
docker run -d --name loot-raiders -p 5555:5555 --env-file .env loot-raiders
```

---

## 🚀 VPS Deployment

```bash
# Linux VPS setup
chmod +x scripts/setup_vps.sh
./scripts/setup_vps.sh

# Or use PM2
pm2 start ecosystem.config.js
```

---

## 🧪 Testing

```bash
python -m pytest tests/ -v
```

---

## 🗺️ Roadmap

- [x] Multi-platform scraping (7 platforms)
- [x] Gemini AI deal scoring
- [x] Self-healing selectors
- [x] Telegram broadcasting & bot
- [x] Discord & Email notifications
- [x] WhatsApp viral referral loop
- [x] Price history tracking
- [x] Web dashboard with admin panel
- [x] PWA support
- [x] Affiliate link routing
- [x] Click tracking & analytics
- [x] Docker containerization
- [x] GitHub Actions CI/CD
- [x] VPS deployment scripts
- [x] Channel growth analytics
- [x] Supermarket deals monitor
- [ ] Mobile PWA polish & push notifications
- [ ] Public API for deal distribution

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Browser | Playwright |
| Database | SQLAlchemy + SQLite (WAL) |
| Telegram | Telethon (MTProto) + python-telegram-bot |
| AI | Google Gemini API |
| Dashboard | HTML5 + CSS3 + Vanilla JS |
| Charts | Chart.js |
| Typography | Google Fonts (Outfit, Fira Code) |
| Icons | Font Awesome 6 |
| CI/CD | GitHub Actions |
| Container | Docker |
| Process | PM2 |

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

## 👨‍💻 Author

**Yogesh Padwal**

GitHub: [yogeshpadwal16](https://github.com/yogeshpadwal16)

---

⭐ If you find this project useful, consider giving it a Star!
]]>
