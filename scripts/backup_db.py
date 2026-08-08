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
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_BACKUP_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logging.warning("Telegram backup dispatch skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
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

def perform_backup() -> bool:
    """Executes online zero-downtime database backup, integrity verification, compression, and off-site dispatch."""
    if not os.path.exists(DB_PATH):
        logging.error(f"Database file not found at {DB_PATH}")
        return False
        
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
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
        
        # Prune backups older than 7 days
        prune_old_backups(days=7)
        return True
    except Exception as e:
        logging.error(f"Failed to perform database backup: {e}")
        return False

def prune_old_backups(days: int = 7):
    """Removes backup files (.db and .db.gz) older than the specified retention window."""
    cutoff = time.time() - (days * 86400)
    count = 0
    dirs_to_prune = [BACKUP_DIR]
    
    offsite_dir = os.getenv("OFFSITE_BACKUP_DIR")
    if offsite_dir and os.path.exists(offsite_dir):
        dirs_to_prune.append(offsite_dir)
        
    for target_dir in dirs_to_prune:
        if os.path.exists(target_dir):
            for fname in os.listdir(target_dir):
                if fname.startswith("loot_raiders_backup_") and (fname.endswith(".db") or fname.endswith(".db.gz")):
                    fpath = os.path.join(target_dir, fname)
                    if os.path.getmtime(fpath) < cutoff:
                        try:
                            os.remove(fpath)
                            count += 1
                        except Exception as e:
                            logging.warning(f"Could not remove old backup {fname}: {e}")
    if count > 0:
        logging.info(f"Pruned {count} database backup archives older than {days} days.")

if __name__ == "__main__":
    perform_backup()

