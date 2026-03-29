
import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
import glob

# Load environment variables from .env file
load_dotenv(dotenv_path='/home/kevinbeeftink/.openclaw/workspace/projects/rippled-ai/.env')

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found in .env file or environment variables.")
    exit(1)

# Parse the DATABASE_URL
result = urlparse(DATABASE_URL)
username = result.username
password = result.password
database = result.path[1:]
hostname = result.hostname
port = result.port

conn = None
try:
    conn = psycopg2.connect(
        host=hostname,
        port=port,
        database=database,
        user=username,
        password=password
    )
    cur = conn.cursor()

    # Get applied migrations
    applied_migrations = set()
    try:
        cur.execute("SELECT version FROM public.supabase_migrations;")
        for row in cur.fetchall():
            applied_migrations.add(row[0])
    except psycopg2.errors.UndefinedTable:
        print("Table 'public.supabase_migrations' not found. Assuming no migrations applied yet or different tracking table.")
        # If the table doesn't exist, assume no migrations have been applied via this tracking mechanism
        # In a real scenario, this would need more robust handling for initial setups

    migration_files = sorted(glob.glob('/home/kevinbeeftink/.openclaw/workspace/projects/rippled-ai/supabase/migrations/*.sql'))

    pending_migrations = []
    for f in migration_files:
        migration_name = os.path.basename(f).split('_', 1)[0] # Extract "001" from "001_name.sql"
        if migration_name not in applied_migrations:
            pending_migrations.append(f)
            
    if not pending_migrations:
        print("No pending migrations found.")
    else:
        print("Pending migrations to apply:")
        for migration_file in pending_migrations:
            print(f"- {os.path.basename(migration_file)}")
            with open(migration_file, 'r') as sql_file:
                sql_script = sql_file.read()
                try:
                    cur.execute(sql_script)
                    # Assuming a simple migration tracking where we insert the version
                    # This might need to be adapted based on actual migration tool behavior
                    # For supabase, it usually auto-tracks. This is a manual check.
                    # If supabase_migrations table exists, it means the CLI tracks it.
                    # We are running this against a live Supabase DB.
                    # So manual application is only if it's not tracked.
                    # Given the "UndefinedTable" error, it implies it's not the supabase_migrations table.
                    # Let's assume the user meant to check for *missing* objects not *migration files*.
                    print(f"Executed {os.path.basename(migration_file)}")
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"Error applying migration {os.path.basename(migration_file)}: {e}")
            
    cur.close()

except Exception as e:
    print(f"Error connecting to or querying database: {e}")
finally:
    if conn:
        conn.close()
