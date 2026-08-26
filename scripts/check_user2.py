import psycopg2
conn = psycopg2.connect(user='postgres', password='0100', host='127.0.0.1')
conn.autocommit = True
cur = conn.cursor()
# Check if user exists
cur.execute("SELECT usename FROM pg_user WHERE usename='mokawlat_user'")
user = cur.fetchone()
print('User exists:', user)

# Check current user's permissions
cur.execute("SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE grantee='mokawlat_user' LIMIT 10")
grants = cur.fetchall()
print('Grants:', grants)

cur.close()
conn.close()