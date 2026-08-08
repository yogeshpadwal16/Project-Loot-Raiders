# [TEST] Deal Mirroring Engine - Pipeline Diagnostic Report

Generated at: 2026-08-08 13:53:16
Message Trace Correlation ID: `0be8c679-7389-4773-ac85-f8fb759fb2e4`

## Pipeline Stages Audit

| Stage | Status | Input Received | Output Produced | Processing Time | Exception | Root Cause (If Failed) |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Telegram Listener | **PASS** | TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_STRING_SESSION | Pyrogram check: FAIL. Telethon check: FAIL. Web Scraper check: PASS. (Web Scraper fallback active) | 27051.6ms | `None` | N/A |
| 2. Message Reception | **PASS** | Raw post event: 'Check this deal out! Wipro Garnet 18W LE...' | Parsed raw event text string | 0.0ms | `None` | N/A |
| 5. Message Normalization | **PASS** | Mock raw Telegram message object | Normalized Message Schema (extracted links: ['https://www.amazon.in/dp/B0DP7H7H8V']) | 0.5ms | `None` | N/A |
| 3. Queue Insertion | **PASS** | Pydantic NormalizedMessage | Message pushed successfully to key: loot_raiders:mirror_queue:pending | 0.0ms | `None` | N/A |
| 4. Queue Consumption | **PASS** | worker-id, timeout | Message popped from pending queue. Correlation ID: 0be8c679-7389-4773-ac85-f8fb759fb2e4 | 0.0ms | `None` | N/A |
| 6. Deal Validation | **PASS** | Store URL: https://www.amazon.in/dp/B0BMVV6693 | Scrape PASS: Title='DEVOKO 5 Pieces Patio Din...', Price=27899 | 2195.7ms | `None` | N/A |
| 7. Duplicate Detection | **PASS** | Product Title & Price | Is duplicate: False. Match ID: None. | 340.7ms | `None` | N/A |
| 8. Affiliate Link Generation | **PASS** | Store URL: https://www.amazon.in/dp/B0BMVV6693 | Affiliate link: https://www.amazon.in/dp/B0BMVV6693 | 0.0ms | `None` | N/A |
| 9. Publisher | **PASS** | alert metadata dictionary | Successfully placed alert job inside notification_queue. | 6.7ms | `None` | N/A |
| 10. Telegram API Response | **FAIL** | Telegram bot_token, chat_id | Telegram post request returned status code != 200 or failed | 44665.1ms | `None` | Telegram rate limits or invalid token/chat ID |
| 11. Database Updates | **PASS** | save_deal_to_db arguments | Product and PriceHistory written successfully to DB. | 75.3ms | `None` | N/A |
| 12. Logging | **PASS** | Correlation ID: 0be8c679-7389-4773-ac85-f8fb759fb2e4 | Trace log successfully verified for Correlation ID: 0be8c679-7389-4773-ac85-f8fb759fb2e4 | 4.7ms | `None` | N/A |

## Diagnostic Summary

[FAIL] **1 failures detected in the pipeline!** Please review the table above.
