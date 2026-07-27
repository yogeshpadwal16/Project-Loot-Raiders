# [TEST] Deal Mirroring Engine - Pipeline Diagnostic Report

Generated at: 2026-07-25 10:40:30
Message Trace Correlation ID: `f95ac686-dc37-4c5b-b0fc-434328262479`

## Pipeline Stages Audit

| Stage | Status | Input Received | Output Produced | Processing Time | Exception | Root Cause (If Failed) |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Telegram Listener | **PASS** | TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_STRING_SESSION | Pyrogram check: FAIL. Telethon check: FAIL. Web Scraper check: PASS. (Web Scraper fallback active) | 31313.6ms | `None` | N/A |
| 2. Message Reception | **PASS** | Raw post event: 'Check this deal out! Wipro Garnet 18W LE...' | Parsed raw event text string | 0.0ms | `None` | N/A |
| 5. Message Normalization | **PASS** | Mock raw Telegram message object | Normalized Message Schema (extracted links: ['https://www.amazon.in/dp/B0DP7H7H8V']) | 0.0ms | `None` | N/A |
| 3. Queue Insertion | **FAIL** | Pydantic NormalizedMessage | Redis push failed (connection refused) | 0.0ms | `None` | Redis server not running locally |
| 4. Queue Consumption | **PASS** | worker-id, timeout | Bypassed Redis Queue (Using Inline Fallback mode) | 0.0ms | `None` | N/A |
| 6. Deal Validation | **PASS** | Store URL: https://www.amazon.in/dp/B0BMVV6693 | Scrape PASS: Title='DEVOKO 5 Pieces Patio Din...', Price=29999 | 28302.5ms | `None` | N/A |
| 7. Duplicate Detection | **PASS** | Product Title & Price | Is duplicate: False. Match ID: None. | 10.1ms | `None` | N/A |
| 8. Affiliate Link Generation | **PASS** | Store URL: https://www.amazon.in/dp/B0BMVV6693 | Affiliate link: https://www.amazon.in/dp/B0BMVV6693?tag=lootraiders-21 | 0.0ms | `None` | N/A |
| 9. Publisher | **PASS** | alert metadata dictionary | Successfully placed alert job inside notification_queue. | 0.0ms | `None` | N/A |
| 10. Telegram API Response | **PASS** | Telegram bot_token, chat_id | Telegram API post succeeded (Code 200). | 1226.5ms | `None` | N/A |
| 11. Database Updates | **PASS** | save_deal_to_db arguments | Product and PriceHistory written successfully to DB. | 1271.9ms | `None` | N/A |
| 12. Logging | **PASS** | Correlation ID: f95ac686-dc37-4c5b-b0fc-434328262479 | Trace log successfully verified for Correlation ID: f95ac686-dc37-4c5b-b0fc-434328262479 | 5.2ms | `None` | N/A |

## Diagnostic Summary

[FAIL] **1 failures detected in the pipeline!** Please review the table above.
