"""Export statistics about the seeding database."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_connection


def print_stats():
    conn = get_connection()

    # Repository counts
    repos = conn.execute("SELECT * FROM REPOSITORIES").fetchall()
    print("=" * 60)
    print("QDArchive Seeding - Database Statistics")
    print("=" * 60)

    print(f"\nRepositories: {len(repos)}")
    for r in repos:
        print(f"  [{r['id']}] {r['name']} - {r['url']}")

    # Project counts per repo
    print("\nProjects per repository:")
    for r in repos:
        count = conn.execute(
            "SELECT COUNT(*) as c FROM PROJECTS WHERE repository_id = ?", (r["id"],)
        ).fetchone()["c"]
        print(f"  {r['name']}: {count}")

    total_projects = conn.execute("SELECT COUNT(*) as c FROM PROJECTS").fetchone()["c"]
    print(f"  Total: {total_projects}")

    # File status breakdown
    print("\nFile status breakdown:")
    statuses = conn.execute(
        "SELECT status, COUNT(*) as c FROM FILES GROUP BY status ORDER BY c DESC"
    ).fetchall()
    for s in statuses:
        print(f"  {s['status']}: {s['c']}")

    total_files = conn.execute("SELECT COUNT(*) as c FROM FILES").fetchone()["c"]
    print(f"  Total files: {total_files}")

    # Files per repo
    print("\nFiles per repository:")
    for r in repos:
        count = conn.execute(
            """SELECT COUNT(*) as c FROM FILES f 
               JOIN PROJECTS p ON f.project_id = p.id 
               WHERE p.repository_id = ?""",
            (r["id"],),
        ).fetchone()["c"]
        succeeded = conn.execute(
            """SELECT COUNT(*) as c FROM FILES f 
               JOIN PROJECTS p ON f.project_id = p.id 
               WHERE p.repository_id = ? AND f.status = 'SUCCEEDED'""",
            (r["id"],),
        ).fetchone()["c"]
        print(f"  {r['name']}: {count} total, {succeeded} succeeded")

    # Keywords
    kw_count = conn.execute("SELECT COUNT(*) as c FROM KEYWORDS").fetchone()["c"]
    print(f"\nTotal keywords: {kw_count}")

    # Person roles
    pr_count = conn.execute("SELECT COUNT(*) as c FROM PERSON_ROLE").fetchone()["c"]
    print(f"Total person-role entries: {pr_count}")

    role_breakdown = conn.execute(
        "SELECT role, COUNT(*) as c FROM PERSON_ROLE GROUP BY role"
    ).fetchall()
    for rb in role_breakdown:
        print(f"  {rb['role']}: {rb['c']}")

    # Licenses
    lic_count = conn.execute("SELECT COUNT(*) as c FROM LICENSES").fetchone()["c"]
    print(f"\nTotal license entries: {lic_count}")

    # Download methods
    print("\nDownload methods:")
    methods = conn.execute(
        "SELECT download_method, COUNT(*) as c FROM PROJECTS GROUP BY download_method"
    ).fetchall()
    for m in methods:
        print(f"  {m['download_method']}: {m['c']}")

    # Disk usage
    print("\nDisk usage:")
    for r in repos:
        folder = os.path.join("data", r["name"])
        if os.path.exists(folder):
            total_size = 0
            file_count = 0
            for dirpath, dirnames, filenames in os.walk(folder):
                for fn in filenames:
                    fp = os.path.join(dirpath, fn)
                    total_size += os.path.getsize(fp)
                    file_count += 1
            print(f"  {r['name']}: {file_count} files, {total_size / (1024*1024):.1f} MB")

    print("=" * 60)
    conn.close()


if __name__ == "__main__":
    print_stats()