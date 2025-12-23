import sqlite3
import os

DB_FILE = '/app/data/decentgit_index.db'

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    """Sets up the database schema."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Stores the latest processed block index
    c.execute('''
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value INTEGER
        )
    ''')
    
    # Stores the derived state (DRS) for each repository ref
    c.execute('''
        CREATE TABLE IF NOT EXISTS refs (
            repo_id TEXT,
            ref_name TEXT,
            commit_hash TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (repo_id, ref_name)
        )
    ''')
    
    # Insert a default value for the last processed block
    c.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('last_processed_block', 0)")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    print(f"Setting up database at {DB_FILE}...")
    setup_database()
    print("Database setup complete.")

