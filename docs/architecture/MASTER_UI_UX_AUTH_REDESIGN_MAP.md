# LOOT RAIDERS — MASTER UI/UX, AUTHENTICATION & DASHBOARD REDESIGN BLUEPRINT
**Document ID:** `docs/architecture/MASTER_UI_UX_AUTH_REDESIGN_MAP.md`  
**Status:** Authoritative Architectural Blueprint & Implementation Specification  
**Target Environment:** Project Loot Raiders (Vite + React 18 + TS + Python ThreadingHTTPServer API)  

---

## 1. ARCHITECTURE DEPENDENCY & PRESERVATION MAP

The redesign upgrades the presentation layer and authentication subsystem while preserving 100% of existing backend scraping, deal evaluation, affiliate link generation, and Telegram publishing pipelines.

```
+----------------------------------------------------------------------------------------------------+
|                                 LOOT RAIDERS PRESENTATION LAYER                                    |
+----------------------------------------------------------------------------------------------------+
|  1. Brand Crest & Identity    : BrandLogo.tsx (LR Monogram + Shield + Crown + Compass + Sword)      |
|  2. Theme Provider            : ThemeContext.tsx (Dark / Light Mode, localStorage, zero flash)     |
|  3. Auth & OTP Verification   : AuthScreen.tsx, OTPVerification.tsx (Single Owner, No Mobile Input)|
|  4. Navigation & Header       : Header.tsx, CommandPalette.tsx (Cmd+K), MobileNav.tsx              |
|  5. Command Center Dashboard  : LootRadar.tsx, BentoSummary.tsx, TopLootCard.tsx, LiveDealsGrid.tsx|
|  6. Intelligence Views        : AIBrainPanel.tsx, DealMirrorPanel.tsx, PriceHistoryModal.tsx       |
|  7. Telemetry & Operations    : TelemetryCard.tsx, HealthMonitor.tsx, ScraperStatusPanel.tsx       |
+----------------------------------------------------------------------------------------------------+
                                                |
                                    REST / SSE HTTP API (JSON)
                                                v
+----------------------------------------------------------------------------------------------------+
|                                  LOOT RAIDERS BACKEND PIPELINE                                     |
+----------------------------------------------------------------------------------------------------+
|  - Web Server & API Router    : web/server.py (BaseHTTPRequestHandler + CORS + Auth Guards)        |
|  - Single-Owner Mobile OTP    : web/auth_engine.py (Server-side OTP generation, session token)   |
|  - Scraper Engine             : core/engine.py (Scrapling + Playwright + curl-cffi)                |
|  - Product Identity & Rerank  : utils/deduplicator.py, loot_brain/hf_ai/ (FastEmbed + CrossEncoder) |
|  - Deal Scoring & Glitch      : deal_engine/scorer.py (Deterministic AI Scorer + Price History)   |
|  - Deal Mirror & Event Bus    : deal_engine/mirroring/ (Pyrogram + Dragonfly Redis Queue)          |
|  - Affiliate Transformation   : utils/affiliate.py (lootraiders-21, Cuelinks, EarnKaro)            |
|  - Telegram Distribution      : deal_engine/notifier.py (Channel Router + ASCI Footers)           |
|  - Database Storage           : database/ (SQLAlchemy models: Product, PriceHistory, ClickLog)     |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. AUTHENTICATION & SINGLE-OWNER MOBILE OTP SPECIFICATION

### Security Guarantees
1. **Single Owner Only**: Exactly one owner identity authorized. Public signup/registration is strictly disabled.
2. **NO Mobile Input Field**: The user is NEVER prompted to enter a phone number. The OTP target is determined exclusively server-side from `OWNER_MOBILE_NUMBER` (environment variable or configuration secret).
3. **Masked Phone Preview**: The frontend receives only a masked string (e.g. `+91 ******42`).
4. **Video-Style OTP Interaction**:
   - 6 individual digit input boxes with automatic focus advancement, backspace navigation, and full OTP paste handling.
   - Smooth active/focus border animation, countdown timer (60s), resend throttling, loading state, error shake/red indicator, and success checkmark transition.
   - OTP Expiry: 300 seconds (5 minutes). Max 3 incorrect verification attempts before session invalidation.

### API Flow
- `POST /api/login`: Accepts `username` + `password`. Returns `{ "status": "otp_required", "session_id": "...", "masked_mobile": "+91 ******42" }` or `401 Unauthorized`.
- `POST /api/verify-otp`: Accepts `session_id` + `otp`. Validates server-side OTP. Returns `{ "status": "success", "token": "<DASHBOARD_SESSION_TOKEN>", "name": "Yogesh Padwal" }` or `400 Bad Request`.
- `POST /api/resend-otp`: Accepts `session_id`. Enforces 60s cooldown, generates fresh OTP, and dispatches SMS/Telegram backup message.

---

## 3. COLOR SYSTEM & BRAND DESIGN TOKENS

### Dark Mode (Command Center Navy & Orange)
- **Background**: `#070B14` (Deep Space Navy)
- **Surface Level 1**: `#0F172A` (Slate Navy Card Surface)
- **Surface Level 2**: `#1E293B` (Elevated Panel)
- **Primary Accent**: `#FF6B00` (Loot Raiders Vibrant Orange)
- **Secondary Accent**: `#FFD700` (Gold Crest Highlight)
- **Success / Warning / Danger**: `#10B981` (Emerald), `#F59E0B` (Amber), `#EF4444` (Ruby)
- **Text Primary / Muted**: `#F8FAFC`, `#94A3B8`

### Light Mode (Warm White & Deep Navy)
- **Background**: `#F8FAFC` (Clean Warm Neutral)
- **Surface Level 1**: `#FFFFFF` (Pure White Card Surface)
- **Surface Level 2**: `#F1F5F9` (Soft Gray Elevated Panel)
- **Primary Accent**: `#FF6B00` (Loot Raiders Vibrant Orange)
- **Secondary Accent**: `#0F172A` (Deep Navy Contrast)
- **Text Primary / Muted**: `#0F172A`, `#64748B`

---

## 4. DASHBOARD & INFORMATION ARCHITECTURE (RAFFLE EXCLUDED)

### Navigation Structure
- **Discover**: Live Deals, Hot Loot, Loot Map
- **Intelligence**: AI Brain, Price Intelligence, Deal History
- **Operations**: Deal Mirror, Telegram, Affiliate, Scrapers
- **System**: Telemetry, Settings

> **CRITICAL RULE**: Raffle functionality is completely removed from all user-facing navigation, sidebars, header metrics, and dashboard cards.

### Main Dashboard Layout
1. **Header & Command Bar**: Brand Crest, Live System Status Indicator, Search/Filter Trigger, Theme Toggle (Dark/Light), User Profile & Logout.
2. **Loot Radar**: High-impact top metric cards (Hot Deals, Historical Lows, Price Crashes, Avg Loot Score, Qualified Deals, Verified Savings, Scraper Health, Telegram Status).
3. **Bento Intelligence Summary**: Data-dense grid showing real-time deal pipeline statistics.
4. **Top Loot Hero Feature Card**: Featured spotlight on the single highest-scoring active deal.
5. **Live Deals Matrix**: Filterable, sortable grid of deal cards with score gauges (0-100), merchant badges, price deltas, auto-cart links, and density controls (`Compact`, `Comfortable`, `Expanded`).
6. **AI Brain Panel**: Real-time signal analysis (price crashes, historical low verifications).
7. **Telemetry & System Health**: Live scraper health, pipeline latency, and background worker monitors.

---

## 5. QUALITY GATE & COMPATIBILITY CONTRACT

1. **Unit Test Verification**: Run `python scripts/quality_gate.py` to confirm all 144+ unit tests pass.
2. **Backward Compatibility**: All existing REST API routes (`/api/deals`, `/api/status`, `/api/selectors`, `/api/config`) remain fully functional.
3. **Secret Protection**: Zero hardcoded bot tokens or mobile numbers in source code.
