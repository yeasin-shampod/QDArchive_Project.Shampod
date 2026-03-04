import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse
import requests

from zenodo_config import (
    ZENODO_API_BASE,
    ZENODO_QUERY,
    ZENODO_ACCESS_RIGHT,
    ZENODO_PAGE_SIZE,
    QDA_EXTENSIONS,
    PRIMARY_EXTENSIONS,
    OPEN_LICENSE_KEYS,
    LOCAL_ROOT,
    DB_PATH,
)


def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def db_connect():
    return sqlite3.connect(DB_PATH)


def is_open_license(license_str: str | None) -> bool:
    if not license_str:
        return False
    ls = license_str.lower()
    return any(key in ls for key in OPEN_LICENSE_KEYS)


def classify_file_type(filename: str) -> str:
    fname = filename.lower()
    for ext in QDA_EXTENSIONS:
        if fname.endswith(ext):
            return "analysis_qda"
    for ext in PRIMARY_EXTENSIONS:
        if fname.endswith(ext):
            return "primary_data"
    return "other"


def normalize_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    base = os.path.basename(path)
    return base or "downloaded_file"


def download_file(file_url: str, local_dir: str, filename: str | None = None) -> str | None:
    ensure_dir(local_dir)
    if not filename:
        filename = normalize_filename_from_url(file_url)

    local_path = os.path.join(local_dir, filename)

    # Avoid re-downloading
    if os.path.exists(local_path):
        print(f"[SKIP] Already downloaded: {local_path}")
        return local_path

    print(f"[DL] {file_url} → {local_path}")
    try:
        r = requests.get(file_url, timeout=60)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(r.content)
        return local_path
    except Exception as e:
        print(f"[ERR] Download failed for {file_url}: {e}")
        return None


def log_file_to_db(
    conn,
    *,
    filename: str,
    title: str | None,
    author: str | None,
    source_name: str,
    source_url: str,
    doi: str | None,
    license_str: str | None,
    year: int | None,
    description: str | None,
    file_type: str,
    local_dir: str,
    is_primary_data_included: bool | None,
):
    cursor = conn.cursor()
    download_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO metadata (
            filename, title, author, source_name, source_url, doi, license, year,
            download_date, description, file_type, local_dir, is_primary_data_included
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            filename,
            title,
            author,
            source_name,
            source_url,
            doi,
            license_str,
            year,
            download_date,
            description,
            file_type,
            local_dir,
            1 if is_primary_data_included else 0,
        ),
    )
    conn.commit()


def fetch_zenodo_page(page: int) -> dict | None:
    params = {
        "q": ZENODO_QUERY,
        "access_right": ZENODO_ACCESS_RIGHT,
        "page": page,
        "size": ZENODO_PAGE_SIZE,
    }
    print(f"[API] Fetching page {page}…")
    r = requests.get(ZENODO_API_BASE, params=params, timeout=60)
    if r.status_code != 200:
        print(f"[ERR] Zenodo API error: {r.status_code} {r.text[:200]}")
        return None
    return r.json()


def process_record(conn, record: dict):
    metadata = record.get("metadata", {}) or {}
    title = metadata.get("title")
    creators = metadata.get("creators") or []
    author = ", ".join(c.get("name", "") for c in creators if c.get("name")) or None
    description = metadata.get("description")
    year = None
    if "publication_date" in metadata:
        try:
            year = int(str(metadata["publication_date"])[:4])
        except Exception:
            pass
    doi = metadata.get("doi")
    license_str = (metadata.get("license") or {}).get("id") or metadata.get("license")

    if not is_open_license(license_str):
        print(f"[SKIP] Non-open license: {license_str} (title: {title})")
        return

    source_url = record.get("links", {}).get("html") or record.get("links", {}).get("self")
    if not source_url:
        print("[WARN] No source URL; skipping record")
        return

    record_id = record.get("id")
    if not record_id:
        print("[WARN] No record ID; skipping")
        return

    project_dir = os.path.join(LOCAL_ROOT, f"zenodo_record_{record_id}")
    ensure_dir(project_dir)

    files = record.get("files") or []
    if not files:
        print("[INFO] No files in this record, skipping downloads")
        return

    any_primary = False
    for f in files:
        file_name = f.get("key") or f.get("filename") or "file"
        file_url = f.get("links", {}).get("self") or f.get("links", {}).get("download")
        if not file_url:
            continue

        local_path = download_file(file_url, project_dir, file_name)
        if not local_path:
            continue

        file_type = classify_file_type(file_name)
        if file_type == "primary_data":
            any_primary = True

        log_file_to_db(
            conn,
            filename=file_name,
            title=title,
            author=author,
            source_name="Zenodo",
            source_url=source_url,
            doi=doi,
            license_str=license_str,
            year=year,
            description=description,
            file_type=file_type,
            local_dir=project_dir,
            is_primary_data_included=any_primary,
        )


def run_zenodo_scraper(max_pages: int = 3):
    conn = db_connect()
    try:
        for page in range(1, max_pages + 1):
            data = fetch_zenodo_page(page)
            if not data:
                break

            hits = data.get("hits", {})
            records = hits.get("hits", [])
            if not records:
                print("[INFO] No more records.")
                break

            for record in records:
                process_record(conn, record)
    finally:
        conn.close()


if __name__ == "__main__":
    run_zenodo_scraper(max_pages=3)
