# Deal Deduplication & Validation Skill

This skill defines mandatory rules for deal deduplication in **Project Loot Raiders** (`utils/deduplicator.py`, `utils/semantic_dedup.py`).

---

## 1. Core Deduplication Gates

1. **In-Flight Lock**: Prevent race conditions when duplicate deals are ingested concurrently across threads or background workers.
2. **Exact Product ID Matching**: Match identical ASINs/PIDs directly in SQLite database (`Product` model) and Redis keys.
3. **Semantic Similarity (ChromaDB + FastEmbed)**: Perform cosine similarity checks on product titles (default threshold: `0.85`).
4. **Legitimate Price Drops**: Allow re-posting if a previously published product drops by more than `10%` below its historical minimum.

---

## 2. Testing Requirements

- Run `python -m unittest tests/test_semantic_dedup.py`
- Verify duplicate deals are rejected cleanly while genuine price drops pass validation.
