import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'loot_raiders.db')
print(f"Checking database at {db_path}...")
if not os.path.exists(db_path):
    print("Database file does not exist!")
else:
    print("Database file size:", os.path.getsize(db_path), "bytes")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        print("Products count:", c.execute('SELECT count(*) FROM products').fetchone()[0])
        print("PriceHistory count:", c.execute('SELECT count(*) FROM price_history').fetchone()[0])
        print("Recent 5 products:")
        for r in c.execute('SELECT p.id, p.title, ph.price FROM products p LEFT JOIN price_history ph ON p.id = ph.product_id GROUP BY p.id ORDER BY ph.timestamp DESC LIMIT 5').fetchall():
            print(r)
    except Exception as e:
        print("Error querying database:", e)
