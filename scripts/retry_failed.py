"""Retry failed downloads."""

import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_connection, get_failed_files, update_file_status

BASE_URLS = {
    1: "https://catalog.ihsn.org",
    2: "https://dataverse.harvard.edu/api",
}

REPO_FOLDERS = {
    1: "ihsn",
    2: "harvard-murray-archive",
}

MAX_FILE_SIZE = 500 * 1024 * 1024
REQUEST_TIMEOUT = 120


def retry_download(file_row):
    """Retry downloading a failed file."""
    repo_id = file_row["repository_id"]
    repo_folder = file_row["download_repository_folder"]
    project_folder = file_row["download_project_folder"]
    file_name = file_row["file_name"]

    save_dir = os.path.join("data", repo_folder, project_folder)
    save_path = os.path.join(save_dir, file_name)

    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
        return "SUCCEEDED"

    # Skip files that can't be retried
    if file_row["status"] == "FAILED_LOGIN_REQUIRED":
        print(f"  Skipping (login required): {file_name}")
        return None  # Don't change status

    if file_row["status"] == "FAILED_TOO_LARGE":
        print(f"  Skipping (too large): {file_name}")
        return None

    # Only retry server unresponsive
    if file_row["status"] != "FAILED_SERVER_UNRESPONSIVE":
        return None

    print(f"  Retrying: {file_name}")

    # Reconstruct download URL based on repo
    if repo_id == 1:
        # IHSN - extract resource_id from filename
        resource_id = file_name.replace("resource_", "").rsplit(".", 1)[0]
        # We need the catalog_id from project_folder
        catalog_id = project_folder
        url = f"https://catalog.ihsn.org/catalog/{catalog_id}/download/{resource_id}"
    elif repo_id == 2:
        # Harvard - we'd need the file_id, which we don't have stored
        # For now, skip Harvard retries (would need to re-query API)
        print(f"  Cannot retry Harvard files without file_id")
        return None
    else:
        return None

    try:
        os.makedirs(save_dir, exist_ok=True)
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True)

        if resp.status_code in (401, 403):
            return "FAILED_LOGIN_REQUIRED"
        if resp.status_code >= 500:
            return "FAILED_SERVER_UNRESPONSIVE"

        resp.raise_for_status()

        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > MAX_FILE_SIZE:
                    os.remove(save_path)
                    return "FAILED_TOO_LARGE"

        return "SUCCEEDED"

    except requests.exceptions.Timeout:
        return "FAILED_SERVER_UNRESPONSIVE"
    except requests.exceptions.ConnectionError:
        return "FAILED_SERVER_UNRESPONSIVE"
    except Exception as e:
        print(f"  Error: {e}")
        return "FAILED_SERVER_UNRESPONSIVE"


def main():
    conn = get_connection()
    failed = get_failed_files(conn)
    print(f"Found {len(failed)} failed files")

    retried = 0
    succeeded = 0

    for row in failed:
        new_status = retry_download(row)
        if new_status:
            update_file_status(conn, row["id"], new_status)
            retried += 1
            if new_status == "SUCCEEDED":
                succeeded += 1
        time.sleep(1)

    conn.commit()
    conn.close()
    print(f"\nRetried: {retried}, Succeeded: {succeeded}")


if __name__ == "__main__":
    main()