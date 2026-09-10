import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'backups.db')

if not os.path.exists(db_path):
    print("DB not found at", db_path)
    exit(0)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(backup)")
columns = [col[1] for col in cur.fetchall()]

if 'destination_type' not in columns:
    cur.execute("ALTER TABLE backup ADD COLUMN destination_type TEXT DEFAULT 'dropbox'")
    print("Added column destination_type")

if 'destination_path' not in columns:
    cur.execute("ALTER TABLE backup ADD COLUMN destination_path TEXT DEFAULT ''")
    print("Added column destination_path")

cur.execute("UPDATE backup SET destination_type='dropbox', destination_path=dropbox_path WHERE destination_type IS NULL OR destination_path = ''")
print(f"Migrated {cur.rowcount} existing backups to destination_type='dropbox'")

conn.commit()
conn.close()
print("Migration done")
