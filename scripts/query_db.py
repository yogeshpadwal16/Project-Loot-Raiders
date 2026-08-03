import sqlite3
import os

db_path = '/var/www/loot-raiders/loot_raiders.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("=== NON-PIPELINE STAGE LOGS ===")
for r in c.execute("SELECT id, correlation_id, stage, status, details, datetime(timestamp, 'unixepoch') FROM processing_logs WHERE stage != 'pipeline' ORDER BY id DESC LIMIT 50").fetchall():
    print(r)
