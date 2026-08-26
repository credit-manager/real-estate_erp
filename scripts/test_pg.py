import psycopg2
try:
    # Connect to postgres database first (system database)
    conn = psycopg2.connect(dbname='postgres', user='postgres', password='0100', host='127.0.0.1')
    print('✅ Connected to PostgreSQL server (postgres db)')
    cur = conn.cursor()
    
    # Check if dynamicpro database exists
    cur.execute("SELECT datname FROM pg_database WHERE datname='dynamicpro'")
    exists = cur.fetchone()
    
    if exists:
        print('✅ Database dynamicpro already exists')
    else:
        cur.execute('CREATE DATABASE dynamicpro')
        print('✅ Created database dynamicpro')
    
    cur.close()
    conn.close()
    
    # Now connect to dynamicpro
    conn = psycopg2.connect(dbname='dynamicpro', user='postgres', password='0100', host='127.0.0.1')
    cur = conn.cursor()
    
    # Check license table
    try:
        cur.execute("SELECT COUNT(*) FROM license")
        count = cur.fetchone()[0]
        print(f'License table has {count} rows')
    except Exception as e:
        print('License table not found (expected on fresh setup)')
    
    # Check tables
    cur.execute("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY tablename
    """)
    tables = cur.fetchall()
    print(f'Tables in dynamicpro: {[t[0] for t in tables]}')
    
    cur.close()
    conn.close()
    print('\\n✅ PostgreSQL is working correctly with dynamicpro database!')
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()