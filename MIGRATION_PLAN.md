# 🗺️ Migration Plan: Redesigned Deal Mirroring Engine

This document outlines the steps to migrate **Project Loot Raiders** from the legacy monolithic Telethon listener to the new modular, Redis-backed, multi-client **Deal Mirroring Engine**.

---

## 📋 Pre-requisites

### 1. Install New Dependencies
Install the required packages (`pyrogram`, `tgcrypto`, `aiolimiter`, and `rapidfuzz`):
```bash
pip install -r requirements.txt
```
*(Or install them manually: `pip install pyrogram tgcrypto aiolimiter`)*

### 2. Verify Redis Server
Ensure a local or cloud Redis instance is running. The mirroring queue relies on Redis for persistence and worker orchestration.
* By default, the engine connects to `127.0.0.1:6379`.
* If using a custom Redis configuration, set these environment variables in your `.env` file:
  ```env
  REDIS_HOST=127.0.0.1
  REDIS_PORT=6379
  REDIS_PASSWORD=your_secure_password
  ```

---

## 🗄️ Database Migrations

Database tables are automatically created at startup. No manual SQL migrations are required.
When the new mirroring engine initializes:
* The `init_db()` caller will detect and create the 5 new SQLAlchemy mirroring tables:
  1. `mirrored_messages` (Audit trail of enqueued/processed Telegram updates)
  2. `source_channels` (Dynamic list of monitored source channels)
  3. `processing_logs` (Structured pipeline logs tracing messages via correlation IDs)
  4. `system_health` (Recorded performance stats: CPU, RAM, queue size)
  5. `retry_history` (Tenacity retry logs for tracking pipeline errors)

---

## 🚀 Execution & PM2 Deployment

### Local Run Verification
To verify the engine boots and compiles correctly:
```powershell
python -c "from deal_engine.channel_mirror import start_channel_mirror; start_channel_mirror()"
```

### Production PM2 Reload
To apply the changes in production on your VPS:
1. Run the deployment script to push all updates to the VPS:
   ```powershell
   powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy_to_vps.ps1
   ```
2. PM2 will automatically restart the `loot-raiders` process, which initializes the new mirroring threads.
3. Monitor logs via:
   ```bash
   pm2 logs loot-raiders
   ```
