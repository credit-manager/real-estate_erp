import os
import psycopg2

conn = psycopg2.connect(
    dbname=os.environ.get("DB_NAME", "dynamicpro"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", ""),
    host=os.environ.get("DB_HOST", "127.0.0.1"),
)
cur = conn.cursor()
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
tables = cur.fetchall()
print("Tables:", [t[0] for t in tables])
cur.close()
conn.close()
