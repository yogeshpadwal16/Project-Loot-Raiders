# Repository Audit Report

This document outlines the architecture, components, database schemas, and performance optimizations audit for the **Project Loot Raiders** codebase.

---

## 1. Project Directory Layout & Modules

The repository is structured as a modular deal-intelligence and syndication engine:

*   `core/`: Contains the primary crawler loops, plugin managers, and scheduling engines (`engine.py`).
*   `deal_engine/`: 
    *   `mirroring/`: Redesigned modular Telegram channel mirroring engine (includes `listener.py`, `processor.py`, `deduplicator.py`, `queue.py`, and `schemas.py`).
    *   `notifier.py`: Syndication worker that formats and dispatches messages to Telegram, Discord, Email, and Apprise.
    *   `scorer.py`: Real-time deal scoring rules.
*   `database/`: Handles Session initialization, transaction logs, and SQLite database migration schema overrides (`db_session.py`).
*   `knowledge_base/`: Defines database models (`models.py`).
*   `web/`: Lightweight HTTP backend REST API (`server.py`) and Web dashboard client pages.
*   `utils/`: Helper utilities (Playwright wrappers, affiliate link cloakers, etc.).

---

## 2. Database Schema & Migration Review

The database uses SQLite. To support the **Publication Frequency Guard**, we audited and successfully migrated the schema to add tracking columns to the `products` table:

| Column Name | SQL Data Type | Description |
| :--- | :--- | :--- |
| `last_published_at` | `FLOAT` | UNIX timestamp of when this product was last posted to Telegram. |
| `last_published_price` | `INTEGER` | The price at which the product was last published. |
| `daily_post_count` | `INTEGER` | Total number of times this product has been posted today (resets daily). |
| `daily_post_date` | `VARCHAR(10)` | Date string (`YYYY-MM-DD`) tracking the active cap period. |

### Migration Strategy
Since SQLite does not support `IF NOT EXISTS` for `ALTER TABLE`, migrations in `db_session.py` are executed inside silent `try/except` blocks catching `OperationalError` to prevent database lockups on existing production servers.

---

## 3. Web API Audit & CORS Patch

The REST API server (`web/server.py`) runs on port `5555` to power the administrative dashboard.
*   **Audit Check:** Safe lazy-loading of scraper state to avoid circular imports.
*   **Patched Bug:** Fixed `AttributeError: 'ScraperAPIHandler' object has no attribute 'headers'` in `end_headers()`. The method now safely guards header parsing so error handling during invalid request parsing does not crash the socket threads.

---

## 4. Playwright & Performance Optimizations

To reduce memory leaks and CPU usage in resource-constrained Cloud VPS environments, the scraper adapter (`utils/playwright_adapter.py`) was optimized:
*   **Asset Blocking:** Handled via custom route interceptors aborting network requests for stylesheets (`.css`), images (`.png`/`.jpg`), media, fonts, and third-party tracking scripts (Google Analytics, DoubleClick, NewRelic, Facebook, etc.).
*   **Stealth Launching:** Stealthed via chromium arguments (`--headless=new`, `--no-sandbox`) and custom user-agents to prevent bot checks.
*   **Footprint Reduction:** Cleaned up unused heavy Python packages (such as `torch`, `sentence-transformers`, `scikit-learn`) from `requirements.txt` to reduce virtual environment size by over 1.5GB and speed up VPS synchronization.
