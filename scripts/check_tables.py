import psycopg2
conn = psycopg2.connect(dbname='dynamicpro', user='postgres', password='0100', host='127.0.0.1')
cur = conn.cursor()
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
tables = cur.fetchall()
print("Tables:", [t[0] for t in tables])
cur.close()
conn.close()