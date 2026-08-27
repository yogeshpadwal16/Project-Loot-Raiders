#!/usr/bin/env python3
"""
Automated Database Backup & Maintenance Engine for Project Loot Raiders.
Performs zero-downtime online SQLite backups, runs PRAGMA optimization,
and prunes backups older than 7 days.
"""
import os
import sys
import sqlite3
import time
import logging
import gzip
import shutil
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "loot_raiders.db"))
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backups"))

def verify_backup_integrity(backup_file: str) -> bool:
    """Verifies that the generated SQLite backup file is uncorrupted using PRAGMA quick_check."""
    if not os.path.exists(backup_file):
        return False
    try:
        conn = sqlite3.connect(backup_file)
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check;")
        res = cursor.fetchone()
        conn.close()
        return res and res[0] == "ok"
    except Exception as e:
        logging.error(f"Backup integrity verification failed for {backup_file}: {e}")
        return False

def compress_backup(backup_file: str) -> str:
    """Compresses the SQLite database backup using gzip to reduce off-site transfer footprint."""
    gz_path = f"{backup_file}.gz"
    try:
        with open(backup_file, 'rb') as f_in:
            with gzip.open(gz_path, 'wb', compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
        orig_mb = os.path.getsize(backup_file) / (1024 * 1024)
        gz_mb = os.path.getsize(gz_path) / (1024 * 1024)
        logging.info(f"Compressed backup: {orig_mb:.2f}MB -> {gz_mb:.2f}MB ({gz_path})")
        return gz_path
    except Exception as e:
        logging.error(f"Failed to compress backup file {backup_file}: {e}")
        return backup_file

def push_to_telegram(file_path: str, caption: str = "") -> bool:
    """Dispatches the database backup document off-site to Telegram admin channel or chat."""
    try:
        from config.settings import load_settings
        settings = load_settings()
    except Exception:
        settings = {}

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or settings.get("telegram_bot_token")
    chat_id = os.getenv("TELEGRAM_BACKUP_CHAT_ID")

    public_chat_id = (settings.get("telegram_chat_id") or "").strip().lower()
    env_public_chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip().lower()

    if not bot_token or not chat_id or not chat_id.strip():
        logging.warning("Telegram backup dispatch skipped: TELEGRAM_BACKUP_CHAT_ID is not configured.")
        return False

    chat_id_clean = chat_id.strip().lower()

    # HARD SAFETY BLOCK: Never send backup files to public channel
    forbidden_channels = {
        "@lootraidersdeals",
        "-100lootraidersdeals",
        "lootraidersdeals",
        public_chat_id,
        env_public_chat_id
    }
    forbidden_channels.discard("")  # remove empty strings

    if chat_id_clean in forbidden_channels:
        logging.error(f"CRITICAL SAFETY VIOLATION: TELEGRAM_BACKUP_CHAT_ID ({chat_id}) matches public deal channel ({public_chat_id}). Refusing to upload backup archive.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, 'rb') as doc:
            response = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"document": doc},
                timeout=60
            )
        if response.status_code == 200:
            logging.info(f"Off-site Telegram backup successfully dispatched to {chat_id}")
            return True
        else:
            logging.error(f"Telegram backup dispatch failed ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logging.error(f"Exception during Telegram off-site backup dispatch: {e}")
        return False

def push_to_secondary_directory(file_path: str) -> bool:
    """Copies the backup file to a secondary off-site directory path if configured."""
    offsite_dir = os.getenv("OFFSITE_BACKUP_DIR")
    if not offsite_dir:
        return False
    try:
        os.makedirs(offsite_dir, exist_ok=True)
        dst_path = os.path.join(offsite_dir, os.path.basename(file_path))
        shutil.copy2(file_path, dst_path)
        logging.info(f"Off-site backup copied to secondary directory: {dst_path}")
        return True
    except Exception as e:
        logging.error(f"Failed copying backup to secondary directory {offsite_dir}: {e}")
        return False

def push_to_webhook(file_path: str) -> bool:
    """Uploads the backup file to a custom off-site HTTP webhook endpoint if configured."""
    webhook_url = os.getenv("OFFSITE_BACKUP_WEBHOOK_URL")
    if not webhook_url:
        return False
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(webhook_url, files={"file": f}, timeout=60)
        if response.status_code in (200, 201, 202):
            logging.info(f"Off-site backup uploaded successfully to webhook: {webhook_url}")
            return True
        else:
            logging.error(f"Off-site webhook upload failed ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logging.error(f"Exception pushing off-site backup to webhook: {e}")
        return False

def dispatch_offsite_backup(backup_file: str) -> dict:
    """Orchestrates all configured off-site backup dispatch methods."""
    results = {"telegram": False, "secondary_dir": False, "webhook": False}
    
    # Generate compressed backup for bandwidth efficiency
    gz_file = compress_backup(backup_file)
    target_file = gz_file if os.path.exists(gz_file) else backup_file
    
    size_mb = os.path.getsize(target_file) / (1024 * 1024)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caption = f"💾 *Loot Raiders DB Off-site Backup*\n📅 Date: `{timestamp}`\n📦 File: `{os.path.basename(target_file)}`\n📊 Size: `{size_mb:.2f} MB`\n✅ Integrity: `VERIFIED`"

    # 1. Telegram document dispatch
    results["telegram"] = push_to_telegram(target_file, caption=caption)

    # 2. Secondary local/cloud mount directory copy
    results["secondary_dir"] = push_to_secondary_directory(target_file)
    
    # 3. HTTP Webhook upload
    results["webhook"] = push_to_webhook(target_file)
    
    return results

def check_disk_space(target_dir: str, min_free_mb: int = 500) -> bool:
    """
    Checks available disk space on the partition hosting target_dir.
    If available space is below min_free_mb, logs a warning and triggers emergency pruning.
    """
    try:
        total, used, free = shutil.disk_usage(target_dir)
        free_mb = free / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        pct_used = (used / total) * 100

        logging.info(f"Disk space check on {target_dir}: {free_mb:.1f} MB free / {total_mb:.1f} MB total ({pct_used:.1f}% used)")

        if free_mb < min_free_mb or pct_used > 92.0:
            logging.warning(f"Low disk space warning! Free: {free_mb:.1f}MB, Usage: {pct_used:.1f}%. Triggering emergency pruning...")
            prune_old_backups(days=2, max_files=6)

            # Re-check after emergency pruning
            _, _, free_after = shutil.disk_usage(target_dir)
            if (free_after / (1024 * 1024)) < (min_free_mb / 2):
                logging.error("CRITICAL: Disk space critically exhausted even after emergency pruning.")
                return False
        return True
    except Exception as e:
        logging.warning(f"Could not evaluate disk space for {target_dir}: {e}")
        return True

def perform_backup(cleanup_raw: bool = False) -> bool:
    """Executes online zero-downtime database backup, integrity verification, compression, and off-site dispatch."""
    if not os.path.exists(DB_PATH):
        logging.error(f"Database file not found at {DB_PATH}")
        return False

    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Pre-backup disk space safety guard
    if not check_disk_space(BACKUP_DIR, min_free_mb=300):
        logging.error("Aborting backup to protect host system stability from disk exhaustion.")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"loot_raiders_backup_{timestamp}.db")
    
    logging.info(f"Starting online backup of {DB_PATH} -> {backup_file}")
    
    try:
        # Zero-downtime online backup using SQLite backup API
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(backup_file)
        
        with dst_conn:
            src_conn.backup(dst_conn, pages=100, sleep=0.01)
            
        dst_conn.close()
        
        # Optimize source database
        src_conn.execute("PRAGMA optimize;")
        src_conn.close()
        
        # Integrity verification
        if not verify_backup_integrity(backup_file):
            logging.error(f"Backup file failed integrity check: {backup_file}")
            return False
            
        size_mb = os.path.getsize(backup_file) / (1024 * 1024)
        logging.info(f"Local backup created and verified: {backup_file} ({size_mb:.2f} MB)")
        
        # Off-site dispatch
        offsite_res = dispatch_offsite_backup(backup_file)
        logging.info(f"Off-site backup dispatch complete: {offsite_res}")
        
        # Optional raw .db cleanup after successful gzip compression
        if cleanup_raw and os.path.exists(f"{backup_file}.gz"):
            try:
                os.remove(backup_file)
            except Exception:
                pass

        # Prune backups older than 7 days or exceeding max 14 archives
        prune_old_backups(days=7, max_files=14)
        return True
    except Exception as e:
        logging.error(f"Failed to perform database backup: {e}")
        return False

def prune_old_backups(days: int = 7, max_files: int = 14):
    """
    Removes backup files (.db and .db.gz) older than the specified retention window,
    and enforces an absolute ceiling on total backup archives to prevent unbounded growth.
    """
    cutoff = time.time() - (days * 86400)
    count = 0
    dirs_to_prune = [BACKUP_DIR]
    
    offsite_dir = os.getenv("OFFSITE_BACKUP_DIR")
    if offsite_dir and os.path.exists(offsite_dir):
        dirs_to_prune.append(offsite_dir)
        
    for target_dir in dirs_to_prune:
        if os.path.exists(target_dir):
            valid_backups = []
            for fname in os.listdir(target_dir):
                if fname.startswith("loot_raiders_backup_") and (fname.endswith(".db") or fname.endswith(".db.gz")):
                    fpath = os.path.join(target_dir, fname)
                    mtime = os.path.getmtime(fpath)
                    if mtime < cutoff:
                        try:
                            os.remove(fpath)
                            count += 1
                        except Exception as e:
                            logging.warning(f"Could not remove old backup {fname}: {e}")
                    else:
                        valid_backups.append((mtime, fpath))

            # Enforce max_files limit by removing oldest if exceeding count
            if len(valid_backups) > max_files:
                valid_backups.sort(key=lambda x: x[0])  # Oldest first
                excess = len(valid_backups) - max_files
                for i in range(excess):
                    try:
                        os.remove(valid_backups[i][1])
                        count += 1
                    except Exception as e:
                        logging.warning(f"Could not remove excess backup {valid_backups[i][1]}: {e}")

    if count > 0:
        logging.info(f"Pruned {count} database backup archives (retention={days}d, max_files={max_files}).")

if __name__ == "__main__":
    perform_backup()

