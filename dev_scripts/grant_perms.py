import psycopg2
conn = psycopg2.connect(user='postgres', password='0100', host='127.0.0.1')
conn.autocommit = True
cur = conn.cursor()
# Grant permissions to mokawlat_user on dynamicpro database
cur.execute("GRANT ALL PRIVILEGES ON SCHEMA public TO mokawlat_user")
cur.execute("GRANT ALL PRIVILEGES ON DATABASE dynamicpro TO mokawlat_user")
cur.close()
conn.close()
print("Permissions granted")