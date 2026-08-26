import psycopg2
try:
    conn = psycopg2.connect(dbname='dynamicpro', user='postgres', password='0100', host='127.0.0.1')
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, password_hash FROM users WHERE username='admin'")
    user = cur.fetchone()
    print('Admin user:', user)
    cur.close()
    conn.close()
except Exception as e:
    print('Error:', e)