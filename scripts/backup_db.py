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
from datetime import datetime, timedelta

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "loot_raiders.db"))
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backups"))

def perform_backup():
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
        
        size_mb = os.path.getsize(backup_file) / (1024 * 1024)
        logging.info(f"Backup created successfully: {backup_file} ({size_mb:.2f} MB)")
        
        # Prune backups older than 7 days
        prune_old_backups(days=7)
        return True
    except Exception as e:
        logging.error(f"Failed to perform database backup: {e}")
        return False

def prune_old_backups(days=7):
    cutoff = time.time() - (days * 86400)
    count = 0
    if os.path.exists(BACKUP_DIR):
        for fname in os.listdir(BACKUP_DIR):
            if fname.startswith("loot_raiders_backup_") and fname.endswith(".db"):
                fpath = os.path.join(BACKUP_DIR, fname)
                if os.path.getmtime(fpath) < cutoff:
                    try:
                        os.remove(fpath)
                        count += 1
                    except Exception as e:
                        logging.warning(f"Could not remove old backup {fname}: {e}")
    if count > 0:
        logging.info(f"Pruned {count} database backups older than {days} days.")

if __name__ == "__main__":
    perform_backup()
