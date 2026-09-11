import os
import psycopg2

conn = psycopg2.connect(
    dbname=os.environ.get("DB_NAME", "dynamicpro"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", ""),
    host=os.environ.get("DB_HOST", "127.0.0.1"),
)
cur = conn.cursor()
cur.execute("SELECT id, username, role, password_hash FROM users WHERE username='admin'")
user = cur.fetchone()
print("Admin user:", user)
cur.close()
conn.close()
