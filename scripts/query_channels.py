import sqlite3
db_path = '/var/www/loot-raiders/loot_raiders.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
print("Source channels:")
for r in c.execute("SELECT id, username_or_invite, chat_id, is_active FROM source_channels").fetchall():
    print(r)
