import psycopg2
import sys
import os

PG_SUPERUSER_PASSWORD = os.environ.get("PG_SUPERUSER_PASSWORD", "")
if not PG_SUPERUSER_PASSWORD:
    print("Error: Set PG_SUPERUSER_PASSWORD environment variable")
    sys.exit(1)

try:
    # Connect to postgres database first
    conn = psycopg2.connect(dbname='postgres', user='postgres', password=PG_SUPERUSER_PASSWORD, host='127.0.0.1')
    conn.autocommit = True
    cur = conn.cursor()
    
    # Check if dynamicpro exists, create if not
    cur.execute("SELECT datname FROM pg_database WHERE datname='dynamicpro'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE dynamicpro")
        print("Created database dynamicpro")
    
    cur.close()
    conn.close()
    
    # Now connect to dynamicpro and set permissions
    conn = psycopg2.connect(dbname='dynamicpro', user='postgres', password=PG_SUPERUSER_PASSWORD, host='127.0.0.1')
    conn.autocommit = True
    cur = conn.cursor()
    
    # Grant all necessary permissions
    cur.execute("GRANT ALL PRIVILEGES ON SCHEMA public TO mokawlat_user")
    cur.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mokawlat_user")
    cur.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mokawlat_user")
    cur.execute("GRANT ALL PRIVILEGES ON ALL ROUTINES IN SCHEMA public TO mokawlat_user")
    
    # Set sequence ownership
    cur.execute("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public'")
    sequences = cur.fetchall()
    for seq in sequences:
        try:
            cur.execute(f"ALTER SEQUENCE {seq[0]} OWNER TO mokawlat_user")
        except:
            pass
    
    cur.close()
    conn.close()
    print("Database and permissions setup complete")
    
except Exception as e:
    print("Error: " + str(e))
    import traceback
    traceback.print_exc()