"""
scripts/audit_live_db.py
Database and channel metrics audit script for live VPS.
Scans all database files and outputs table counts and schema details.
"""

import os
import sqlite3
import time

base_dir = "/var/www/loot-raiders"
if not os.path.exists(base_dir):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("==========================================================================")
print("  LIVE VPS DATABASE & PIPELINE METRICS AUDIT")
print("==========================================================================")

db_files = [f for f in os.listdir(base_dir) if f.endswith(".db")]
print(f"Discovered SQLite database files: {db_files}\n")

for db_name in db_files:
    db_path = os.path.join(base_dir, db_name)
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"📁 Database: {db_name} (Size: {os.path.getsize(db_path) / 1024:.1f} KB)")
        print(f"   Tables: {tables}")
        for t in tables:
            try:
                cnt = c.execute(f"SELECT count(*) FROM `{t}`").fetchone()[0]
                print(f"    - Table '{t}': {cnt:,} records")
            except Exception as e:
                print(f"    - Table '{t}': {e}")
        conn.close()
        print()
    except Exception as err:
        print(f"Error inspecting {db_name}: {err}\n")

print("==========================================================================")
