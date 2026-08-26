import psycopg2
# Connect without host (uses local socket)
conn = psycopg2.connect(user='postgres', password='0100')
conn.autocommit = True
cur = conn.cursor()
# Grant usage on schema
cur.execute("GRANT USAGE ON SCHEMA public TO mokawlat_user")
# Grant on sequences
cur.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO mokawlat_user")
cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO mokawlat_user")
cur.close()
conn.close()
print("Permissions granted via socket")