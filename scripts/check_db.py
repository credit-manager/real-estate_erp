import os
import psycopg2

conn = psycopg2.connect(
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", ""),
    host=os.environ.get("DB_HOST", "127.0.0.1"),
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT datname FROM pg_database")
databases = cur.fetchall()
print("Databases:", [d[0] for d in databases])
cur.close()
conn.close()
