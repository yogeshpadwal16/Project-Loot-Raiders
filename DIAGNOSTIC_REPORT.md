# [TEST] Deal Mirroring Engine - Pipeline Diagnostic Report

Generated at: 2026-08-03 23:27:43
Message Trace Correlation ID: `6626f17b-10f9-4b8c-ba33-7ae70e47fb97`

## Pipeline Stages Audit

| Stage | Status | Input Received | Output Produced | Processing Time | Exception | Root Cause (If Failed) |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Telegram Listener | **PASS** | TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_STRING_SESSION | Pyrogram check: FAIL. Telethon check: FAIL. Web Scraper check: PASS. (Web Scraper fallback active) | 33009.1ms | `None` | N/A |
| 2. Message Reception | **PASS** | Raw post event: 'Check this deal out! Wipro Garnet 18W LE...' | Parsed raw event text string | 0.0ms | `None` | N/A |
| 5. Message Normalization | **PASS** | Mock raw Telegram message object | Normalized Message Schema (extracted links: ['https://www.amazon.in/dp/B0DP7H7H8V']) | 0.0ms | `None` | N/A |
| 3. Queue Insertion | **PASS** | Pydantic NormalizedMessage | Message pushed successfully to key: loot_raiders:mirror_queue:pending | 0.0ms | `None` | N/A |
| 4. Queue Consumption | **PASS** | worker-id, timeout | Message popped from pending queue. Correlation ID: 6626f17b-10f9-4b8c-ba33-7ae70e47fb97 | 0.0ms | `None` | N/A |
| 6. Deal Validation | **PASS** | Store URL: https://www.amazon.in/dp/B0BMVV6693 | Scrape PASS: Title='DEVOKO 5 Pieces Patio Din...', Price=29999 | 10579.1ms | `None` | N/A |
| 7. Duplicate Detection | **PASS** | Product Title & Price | Is duplicate: False. Match ID: None. | 1250.6ms | `None` | N/A |
| 8. Affiliate Link Generation | **PASS** | Store URL: https://www.amazon.in/dp/B0BMVV6693 | Affiliate link: https://www.amazon.in/dp/B0BMVV6693 | 0.5ms | `None` | N/A |
| 9. Publisher | **PASS** | alert metadata dictionary | Successfully placed alert job inside notification_queue. | 0.0ms | `None` | N/A |
| 10. Telegram API Response | **FAIL** | Telegram bot_token, chat_id | Telegram post request returned status code != 200 or failed | 2652.5ms | `None` | Telegram rate limits or invalid token/chat ID |
| 11. Database Updates | **PASS** | save_deal_to_db arguments | Product and PriceHistory written successfully to DB. | 100.9ms | `None` | N/A |
| 12. Logging | **PASS** | Correlation ID: 6626f17b-10f9-4b8c-ba33-7ae70e47fb97 | Trace log successfully verified for Correlation ID: 6626f17b-10f9-4b8c-ba33-7ae70e47fb97 | 7.3ms | `None` | N/A |

## Diagnostic Summary

[FAIL] **1 failures detected in the pipeline!** Please review the table above.
