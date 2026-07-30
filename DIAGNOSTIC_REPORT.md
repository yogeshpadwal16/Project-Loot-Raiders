# [TEST] Deal Mirroring Engine - Pipeline Diagnostic Report

Generated at: 2026-07-31 00:52:46
Message Trace Correlation ID: `e977e5ae-1607-417f-a94e-2411b1c4c0cf`

## Pipeline Stages Audit

| Stage | Status | Input Received | Output Produced | Processing Time | Exception | Root Cause (If Failed) |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Telegram Listener | **PASS** | TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_STRING_SESSION | Pyrogram check: PASS. Telethon check: FAIL. Web Scraper check: PASS. | 30785.1ms | `None` | N/A |
| 2. Message Reception | **PASS** | Raw post event: 'Check this deal out! Wipro Garnet 18W LE...' | Parsed raw event text string | 0.0ms | `None` | N/A |
| 5. Message Normalization | **PASS** | Mock raw Telegram message object | Normalized Message Schema (extracted links: ['https://www.amazon.in/dp/B0DP7H7H8V']) | 0.0ms | `None` | N/A |
| 3. Queue Insertion | **PASS** | Pydantic NormalizedMessage | Message pushed successfully to key: loot_raiders:mirror_queue:pending | 0.0ms | `None` | N/A |
| 4. Queue Consumption | **PASS** | worker-id, timeout | Message popped from pending queue. Correlation ID: e977e5ae-1607-417f-a94e-2411b1c4c0cf | 0.0ms | `None` | N/A |
| 6. Deal Validation | **PASS** | Store URL: https://www.amazon.in/dp/B0BMVV6693 | Scrape PASS: Title='DEVOKO 5 Pieces Patio Din...', Price=29999 | 9470.9ms | `None` | N/A |
| 7. Duplicate Detection | **PASS** | Product Title & Price | Is duplicate: False. Match ID: None. | 35.8ms | `None` | N/A |
| 8. Affiliate Link Generation | **PASS** | Store URL: https://www.amazon.in/dp/B0BMVV6693 | Affiliate link: https://www.amazon.in/dp/B0BMVV6693?tag=lootraiders-21 | 0.0ms | `None` | N/A |
| 9. Publisher | **PASS** | alert metadata dictionary | Successfully placed alert job inside notification_queue. | 0.0ms | `None` | N/A |
| 10. Telegram API Response | **PASS** | Telegram bot_token, chat_id | Telegram API post succeeded (Code 200). | 5406.1ms | `None` | N/A |
| 11. Database Updates | **PASS** | save_deal_to_db arguments | Product and PriceHistory written successfully to DB. | 40.1ms | `None` | N/A |
| 12. Logging | **PASS** | Correlation ID: e977e5ae-1607-417f-a94e-2411b1c4c0cf | Trace log successfully verified for Correlation ID: e977e5ae-1607-417f-a94e-2411b1c4c0cf | 5.4ms | `None` | N/A |

## Diagnostic Summary

[PASS] **All stages passed successfully!** The pipeline is functional.
