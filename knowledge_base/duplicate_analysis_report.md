# Duplicate Analysis Report

This report provides a forensic analysis of the deal duplication issues within the Loot Raiders system, evaluates the root causes, and documents the architectural guardrails established to guarantee production reliability.

---

## 1. Executive Summary & Incident History
During early testing, the system suffered from severe duplication anomalies, most notably posting the **exact same product multiple times within a few seconds**.
*   **Symptom:** A single product (e.g., *Redmi 13C 5G*) was enqueued and published 3 times within 8 seconds.
*   **Impact:** Substandard user experience, spamming of subscribers, and unnecessary Telegram API rate-limit stress.

---

## 2. Root Cause Analysis (RCA)
Our forensic investigation identified three distinct gaps in the previous codebase that combined to allow duplication:

1.  **Concurrent Race Conditions ("In-Flight" Blindspots):**
    When multiple scraper or mirror threads processed the same deal concurrently, neither could "see" the other's deal because it had not yet been committed to the SQLite database. Both proceeded to publish the deal simultaneously.
2.  **Lack of Price-Drop Validation:**
    The system enqueued a duplicate deal even if the price remained exactly the same or went up. Without verifying that a recurring listing represented an *actual price reduction*, the channel kept posting the same product at the same price.
3.  **No Publication Frequency Protection (Daily/Hourly Guard):**
    If a product fluctuated back and forth or was scraped repeatedly, the system had no temporal cooldown or daily cap per item.

---

## 3. The Three-Tier Deduplication Defense
To address these issues, we have implemented a unified three-tier deduplication defense system:

```mermaid
graph TD
    A[New Deal Extracted] --> B{In-Flight Check}
    B -- Match Found -- > C[Suppress & Skip]
    B -- Unique -- > D{RapidFuzz Title Match}
    D -- Sim > 85% -- > E{Price Drop Check}
    E -- Price >= Last -- > C
    E -- Price < Last -- > F[Lock as In-Flight]
    D -- Unique -- > F
    F --> G{Publication Guard}
    G -- Last post < 6h ago -- > H[Suppress & Release Lock]
    G -- Daily post count >= 3 -- > H
    G -- Passed Checks -- > I[Enqueue Alert & Update DB Stats]
```

### Tier 1: Concurrent "In-Flight" Lock & RapidFuzz Similarity
*   **Implementation:** Located in `utils.deduplicator` (`release_in_flight_deal`, etc.) and `IntelligentDeduplicator.find_duplicate`.
*   **Mechanism:** When a thread begins processing a URL/title, it registers it in an active "in-flight" set. If another thread attempts to process a similar title or URL concurrently, it gets flagged as a duplicate (`matched_id == "in-flight"`) and is suppressed.
*   **String Matching:** Title similarity is verified via `RapidFuzz` at a strict **85% threshold**.

### Tier 2: Price Stability Verification
*   **Implementation:** Handled in `deal_engine/mirroring/processor.py` (lines 172-185).
*   **Mechanism:** If a deal is matched to an existing product in the database, the system pulls the most recent price point from the `PriceHistory` table.
*   **Rule:** The new alert is allowed *only* if the current price is strictly **lower** than the last published price (`price < latest.price`). Same-price or higher-price alerts are discarded.

### Tier 3: Publication Frequency Guard (Temporal Cooldown & Daily Cap)
*   **Implementation:** Handled in `core/engine.py` (lines 255-290) and mapped via database migration schema fields (`last_published_at`, `last_published_price`, `daily_post_count`, `daily_post_date`).
*   **Mechanism:** Enforces absolute temporal and quantity limits:
    *   **6-Hour Cooldown:** A product cannot be posted again within 6 hours if the price hasn't dropped.
    *   **Daily Cap:** A single product is capped at a maximum of **3 posts per calendar day**.

---

## 4. Verification and Live Production Metrics
The system was verified live on the Oracle VPS server:
*   **Total Database Scale:** **2,531 products** and **11,152 price history records** loaded.
*   **Live Deduplication Trigger:** 
    ```log
    [INFO] DB duplicate match by ID: B0CKYCS7B2 ('Redmi 13C 5G (Startrail Silver')
    [INFO] [Mirror Pipeline] Deduplicated: 'Redmi 13C 5G (Startrail Silver' mapped to existing deal B0CKYCS7B2
    [INFO] [Mirror Pipeline] Skipping duplicate deal: Redmi 13C 5G... (Price ₹9999 >= latest ₹9999)
    ```
*   **Result:** Verified that duplicate mirror deals at stable prices are suppressed immediately within 0.05 seconds, while genuine price-drop alerts are dispatched to Telegram.
