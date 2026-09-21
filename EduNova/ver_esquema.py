import sqlite3
conn = sqlite3.connect('db.sqlite3')
cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
for name, sql in cursor.fetchall():
    print(f"\n-- Tabla: {name} --")
    print(sql)
conn.close()