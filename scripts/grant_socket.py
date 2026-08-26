import psycopg2
# Connect without host (uses local socket)
conn = psycopg2.connect(user='postgres', password='0100')
conn.autocommit = True
cur = conn.cursor()
cur.execute("GRANT ALL PRIVILEGES ON SCHEMA public TO mokawlat_user")
cur.execute("GRANT ALL ON TABLE ALL IN SCHEMA public TO mokawlat_user")
cur.close()
conn.close()
print("Permissions granted via socket")