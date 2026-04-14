import os
import shutil

BASE_DIR = os.getcwd()

def safe_move(src, dst):
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            shutil.move(src, dst)
            print(f"Moved: {src} → {dst}")
        else:
            print(f"Skipped (exists): {dst}")

def create_dirs():
    dirs = [
        "src/db",
        "src/scrapers",
        "src/pipeline",
        "src/utils",
        "scripts",
        "data",
        "databases",
        "output/downloads",
        "output/export",
        "logs",
        "tests"
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def move_files():
    # DB files
    safe_move("23080363-seeding.db", "databases/seeding.db")
    safe_move("qd_archive.db", "databases/qdarchive.db")
    safe_move("qdarchive_metadata.db", "databases/metadata.db")

    # DB logic
    safe_move("db/database.py", "src/db/database.py")
    safe_move("db/schema.sql", "src/db/schema.sql")

    # Scrapers
    safe_move("scrapers/ihsn_scraper.py", "src/scrapers/ihsn_scraper.py")
    safe_move("scrapers/harvard_scraper.py", "src/scrapers/harvard_scraper.py")
    safe_move("db/ihsn_scraper (v2)", "src/scrapers/ihsn_scraper_v2.py")

    # Scripts
    safe_move("scripts/retry_failed.py", "scripts/retry_failed.py")
    safe_move("fix_db_schema.py", "scripts/fix_db_schema.py")

    # Output folders
    safe_move("downloads", "output/downloads")
    safe_move("export", "output/export")

    # Pipeline
    safe_move("pipeline", "src/pipeline")

def cleanup():
    # Optional: remove empty folders
    for folder in ["db", "scrapers", "pipeline"]:
        if os.path.exists(folder) and not os.listdir(folder):
            os.rmdir(folder)
            print(f"Removed empty folder: {folder}")

if __name__ == "__main__":
    print("🚀 Restructuring project...")
    create_dirs()
    move_files()
    cleanup()
    print("✅ Done!")