import psycopg2
conn = psycopg2.connect(user='postgres', password='0100', host='127.0.0.1')
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT datname FROM pg_database")
databases = cur.fetchall()
print("Databases:", [d[0] for d in databases])
cur.close()
conn.close()