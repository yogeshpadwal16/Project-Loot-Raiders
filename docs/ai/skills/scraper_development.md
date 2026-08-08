# Scraper Development & Maintenance Skill

This skill defines instructions for extending, debugging, and maintaining e-commerce page scrapers in **Project Loot Raiders** (`plugins/amazon.py`, `plugins/flipkart.py`, `plugins/generic.py`).

---

## 1. Core Principles & Constraints

1. **Preserve Existing Scrapers**: Do NOT rewrite or replace Playwright/BeautifulSoup scrapers with third-party wrappers.
2. **Canonical URL Normalization**: Always extract canonical product URLs and strip tracking parameters (`ref=`, `tag=`, `qid=`, `sr=`) before passing URLs to deduplication.
3. **Product ID Isolation**:
   - **Amazon**: Extract 10-character alphanumeric ASIN (e.g. `B09XS7JWHH`).
   - **Flipkart**: Extract 16-character alphanumeric PID (e.g. `LSTMOB...`).

---

## 2. Dynamic Selector Resilience

- Maintain CSS selectors in `database/operations.py` or `selectors.json`.
- When e-commerce platforms alter DOM structures, update selector matrices without changing parser logic.
- Always include fallback extractions for title, price, MRP, and primary product image.

---

## 3. Testing & Verification

Before merging scraper changes:
1. Run `python -m unittest tests/test_plugins.py`
2. Ensure price extraction returns valid numerical floats (`price > 0`, `mrp >= price`).
