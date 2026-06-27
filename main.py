"""Main pipeline for QDArchive seeding."""

import sys
import argparse
from db.database import init_db
from scrapers.ihsn_scraper import run as run_ihsn
from scrapers.harvard_scraper import run as run_harvard
from scripts.classify_projects import classify_projects
from export.classification_report import generate_classification_report


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
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Run classification for existing projects after scraping",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate a classification report after scraping",
    )
    parser.add_argument(
        "--part2",
        action="store_true",
        help="Run the full Part 2 data-classification workflow "
             "(PROJECT_TYPE + ISIC Rev. 5 + XLSX + PDF report)",
    )
    args = parser.parse_args()

    if args.part2:
        from run_classification import main as run_part2
        run_part2()
        return

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

    if args.classify:
        print("\n" + "=" * 60)
        print("Running classification for seeded projects...")
        print("=" * 60)
        classify_projects(force=False)

    if args.report:
        print("\n" + "=" * 60)
        print("Generating classification report...")
        print("=" * 60)
        generate_classification_report()

    # Print stats
    print("\n")
    from export.stats import print_stats
    print_stats()


if __name__ == "__main__":
    main()