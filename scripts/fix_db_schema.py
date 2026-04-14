# fix_db_schema_final.py

import sqlite3

def fix_schema(db_path="qdarchive_metadata.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the old table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata_old';")
    if cursor.fetchone():
        print("⚠️  Old table detected. Dropping it.")
        cursor.execute("DROP TABLE metadata_old")

    # Rename current table
    cursor.execute("ALTER TABLE metadata RENAME TO metadata_old")

    # Create new table WITHOUT the UNIQUE constraint on source_url
    cursor.execute('''
        CREATE TABLE metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            title TEXT,
            author TEXT,
            source_name TEXT,
            source_url TEXT,  -- No UNIQUE
            doi TEXT,
            license TEXT,
            year INTEGER,
            download_date TEXT,
            description TEXT,
            file_type TEXT,
            local_dir TEXT,
            is_primary_data_included BOOLEAN
        )
    ''')

    # Copy all data
    cursor.execute('''
        INSERT INTO metadata (
            filename, title, author, source_name, source_url, doi, license, year,
            download_date, description, file_type, local_dir, is_primary_data_included
        )
        SELECT
            filename, title, author, source_name, source_url, doi, license, year,
            download_date, description, file_type, local_dir, is_primary_data_included
        FROM metadata_old
    ''')

    # Drop old table
    cursor.execute("DROP TABLE metadata_old")

    conn.commit()
    conn.close()
    print("✅ Database schema successfully updated.")

if __name__ == "__main__":
    fix_schema()