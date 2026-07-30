# Definition of Done (DoD) Checklist

This document establishes the official engineering criteria required for any feature, patch, or release in Project Loot Raiders to be declared complete.

---

## 1. Code Quality & Formatting
- [ ] No syntax errors or import check failures.
- [ ] Circular dependencies avoided by utilizing dynamic/lazy imports inside functions.
- [ ] No hardcoded tokens, hashes, or credentials. All secrets are resolved via environment variables (`.env`) or standard config files.
- [ ] Documentation and comments are maintained. Unrelated files are not modified.

---

## 2. Database & Schema Safety
- [ ] Alterations to the SQLite schema utilize safe migration blocks (silent catching of `OperationalError` on `ALTER TABLE` to support existing production databases).
- [ ] Database connections and sessions are strictly closed using `finally` blocks to prevent thread-level transaction deadlocks.

---

## 3. End-to-End Local Validation
- [ ] The module is validated via dedicated E2E unit tests in the local environment.
- [ ] Local tests execute successfully in under 1 second without depending on heavy third-party mock interfaces unless necessary.
- [ ] No display server or graphics hardware dependencies (must run headlessly).

---

## 4. Production Deployment & Audit
- [ ] The codebase is synchronized with `origin/main` on GitHub.
- [ ] Tar package packaging is validated to ensure new modules are correctly archived.
- [ ] Deploy script (`deploy_to_vps.ps1`) runs without errors.
- [ ] PM2 processes on the production server successfully restart and show `online` status.
- [ ] Production logs (`pm2 logs`) are monitored for at least 3 minutes to verify:
    *   No unhandled exceptions or error tracebacks are logged.
    *   Telegram API dispatches respond with HTTP `200 OK`.
    *   Competitor channel sessions resolve online.
