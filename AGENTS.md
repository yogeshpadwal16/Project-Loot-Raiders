# AGENTS.md - System Engineering Rules & Operating Contract

This document specifies authoritative system boundaries, development lifecycles, and code quality contracts for AI assistants working on **Project Loot Raiders**.

---

## 1. Non-Negotiable Core Boundaries

1. **Source of Truth**: Loot Raiders' existing architecture (`plugins/`, `core/`, `deal_engine/`, `database/`, `knowledge_base/`, `utils/`, `web/`, `loot_brain/`) is authoritative. Upstream toolboxes are strictly supplementary.
2. **No Re-Architecture**: Do NOT redesign, rewrite, migrate, or restructure Loot Raiders to accommodate new tooling.
3. **Do Not Duplicate**: Inspect the codebase first. Reuse or extend existing linters, test setups, hooks, scripts, or adapters before adding new files.
4. **Business Logic Lock**: Do NOT alter scraper behavior, deal scoring rules, deduplication logic, mirror pipelines, or affiliate link routing unless fixing a verified bug covered by empirical unit tests.

---

## 2. Development Lifecycle & Quality Standards

All changes MUST adhere to this sequential execution flow:
`PLAN -> INSPECT -> SMALLEST SAFE CHANGE -> TARGETED TESTS -> REGRESSION TESTS -> SIMPLIFY REVIEW -> SECURITY CHECK -> DIFF REVIEW -> COMMIT/DEPLOY`

### Simplification & Clean Code Rules (`simplify`)
- **YAGNI (You Aren't Gonna Need It)**: Eliminate speculative abstractions, unused parameter options, and redundant helper wrappers.
- **Code Reuse**: Leverage existing utilities in `utils/` and `database/operations.py` instead of rewriting duplicate functions.
- **Python Standard Idioms**: Use explicit exception handling, clean function boundaries, type annotations where appropriate, and deterministic test assertions.

---

## 3. Security & Data Protection Rules

- **Zero Secret Leaks**: NEVER commit API keys, Telegram bot tokens (`\d+:[A-Za-z0-9_-]{35}`), SSH keys, cookies, or `.env` credential files.
- **Log Sanitization**: Ensure all loggers pass output through `InputSanitizer` or equivalent token masking utilities before writing to disk.
- **Database Integrity**: Never commit or overwrite SQLite database files (`*.db`, `knowledge_base.db`) during routine commits or deployments.

---

## 4. Quality Gate Verification Contract

Before declaring any task completed or pushing code to Git/VPS, the changes MUST pass the project Quality Gate (`python scripts/quality_gate.py`):
1. **Syntax Integrity**: `python -m compileall .`
2. **Unit Test Suite**: `python -m unittest discover -s tests -p "test_*.py"` (All tests MUST pass).
3. **Security Audit**: Zero hardcoded bot tokens or secret keys in source files.
