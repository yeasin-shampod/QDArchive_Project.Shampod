"""Main pipeline for QDArchive seeding."""

import sys
import argparse
from db.database import init_db
from scrapers.ihsn_scraper import run as run_ihsn
from scrapers.harvard_scraper import run as run_harvard


def main():
    parser = argparse.ArgumentParser(description="QDArchive Seeding Pipeline")
    parser.add_argument(
        "--repo",
        choices=["ihsn", "harvard", "all"],
        default="all",
        help="Which repository to scrape (default: all)",
    )
    parser.add_argument(
        "--max-projects",
        type=int,
        default=100,
        help="Maximum projects to process per repository (default: 100)",
    )
    parser.add_argument(
        "--init-db-only",
        action="store_true",
        help="Only initialize the database, don't scrape",
    )
    args = parser.parse_args()

    # Always initialize DB first
    print("Initializing database...")
    init_db()

    if args.init_db_only:
        print("Database initialized. Exiting.")
        return

    if args.repo in ("ihsn", "all"):
        print("\n" + "=" * 60)
        print("Starting IHSN scraper...")
        print("=" * 60)
        run_ihsn(max_projects=args.max_projects)

    if args.repo in ("harvard", "all"):
        print("\n" + "=" * 60)
        print("Starting Harvard Murray Archive scraper...")
        print("=" * 60)
        run_harvard(max_projects=args.max_projects)

    # Print stats
    print("\n")
    from export.stats import print_stats
    print_stats()


if __name__ == "__main__":
    main()