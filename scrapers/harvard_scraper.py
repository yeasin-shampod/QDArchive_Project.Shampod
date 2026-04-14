"""Scraper for Harvard Murray Research Archive via Dataverse API."""

import os
import time
import requests
from db.database import (
    get_connection, insert_project, insert_file, insert_keyword,
    insert_person_role, insert_license, project_exists
)

BASE_API = "https://dataverse.harvard.edu/api"
REPO_ID = 2
REPO_FOLDER = "harvard-murray-archive"
DATA_DIR = os.path.join("data", REPO_FOLDER)
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
REQUEST_TIMEOUT = 120
DELAY_BETWEEN_REQUESTS = 1


def get_dataverse_contents(dataverse_id="mra"):
    """Get all datasets and sub-dataverses from a dataverse."""
    url = f"{BASE_API}/dataverses/{dataverse_id}/contents"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        print(f"[HARVARD] Error fetching dataverse {dataverse_id}: {e}")
        return []


def get_all_datasets():
    """Recursively get all datasets from MRA and sub-dataverses."""
    datasets = []
    sub_dataverses = []

    # Get main MRA contents
    contents = get_dataverse_contents("mra")
    for item in contents:
        if item.get("type") == "dataset":
            datasets.append(item)
        elif item.get("type") == "dataverse":
            sub_dataverses.append(item["id"])

    # Get sub-dataverse contents (Original Murray Collection and its children)
    for dv_id in sub_dataverses:
        time.sleep(DELAY_BETWEEN_REQUESTS)
        sub_contents = get_dataverse_contents(dv_id)
        for item in sub_contents:
            if item.get("type") == "dataset":
                datasets.append(item)
            elif item.get("type") == "dataverse":
                # Go one more level deep
                time.sleep(DELAY_BETWEEN_REQUESTS)
                sub_sub = get_dataverse_contents(item["id"])
                for sub_item in sub_sub:
                    if sub_item.get("type") == "dataset":
                        datasets.append(sub_item)

    return datasets


def get_dataset_metadata(persistent_id):
    """Get full metadata for a dataset."""
    url = f"{BASE_API}/datasets/:persistentId"
    params = {"persistentId": persistent_id}
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception as e:
        print(f"[HARVARD] Error fetching metadata for {persistent_id}: {e}")
        return None


def get_dataset_files(persistent_id):
    """Get file list for a dataset."""
    url = f"{BASE_API}/datasets/:persistentId"
    params = {"persistentId": persistent_id}
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        latest = data.get("latestVersion", {})
        return latest.get("files", [])
    except Exception as e:
        print(f"[HARVARD] Error fetching files for {persistent_id}: {e}")
        return []


def download_file(file_id, save_path):
    """Download a file from Harvard Dataverse."""
    url = f"{BASE_API}/access/datafile/{file_id}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True)

        if resp.status_code in (401, 403):
            return "FAILED_LOGIN_REQUIRED"
        if resp.status_code >= 500:
            return "FAILED_SERVER_UNRESPONSIVE"

        resp.raise_for_status()

        content_length = int(resp.headers.get("content-length", 0))
        if content_length > MAX_FILE_SIZE:
            return "FAILED_TOO_LARGE"

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > MAX_FILE_SIZE:
                    f.close()
                    os.remove(save_path)
                    return "FAILED_TOO_LARGE"

        return "SUCCEEDED"

    except requests.exceptions.ConnectionError:
        return "FAILED_SERVER_UNRESPONSIVE"
    except requests.exceptions.Timeout:
        return "FAILED_SERVER_UNRESPONSIVE"
    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            if e.response.status_code in (401, 403):
                return "FAILED_LOGIN_REQUIRED"
            if e.response.status_code >= 500:
                return "FAILED_SERVER_UNRESPONSIVE"
        return "FAILED_SERVER_UNRESPONSIVE"
    except Exception as e:
        print(f"[HARVARD] Unexpected download error: {e}")
        return "FAILED_SERVER_UNRESPONSIVE"


def normalize_license(license_text):
    """Normalize license string to short form."""
    if not license_text:
        return None

    text = license_text.lower().strip()

    license_map = {
        "cc0": "CC0",
        "cc-0": "CC0",
        "creative commons zero": "CC0",
        "public domain": "CC0",
        "cc by 4.0": "CC BY 4.0",
        "cc by": "CC BY",
        "cc by-sa": "CC BY-SA",
        "cc by-nc": "CC BY-NC",
        "cc by-nd": "CC BY-ND",
        "cc by-nc-nd": "CC BY-NC-ND",
        "cc by-nc-sa": "CC BY-NC-SA",
        "odbl": "ODbL",
        "odc-by": "ODC-By",
        "pddl": "PDDL",
    }

    for key, val in license_map.items():
        if key in text:
            return val

    # Return original if no match (truncated)
    return license_text[:200] if len(license_text) > 200 else license_text


def extract_citation_fields(metadata):
    """Extract fields from citation metadata block."""
    latest = metadata.get("latestVersion", {})
    meta_blocks = latest.get("metadataBlocks", {})
    citation = meta_blocks.get("citation", {})
    fields = citation.get("fields", [])

    field_map = {}
    for f in fields:
        field_map[f["typeName"]] = f.get("value")

    return field_map


def process_dataset(dataset_entry, conn):
    """Process a single Harvard Dataverse dataset."""
    identifier = dataset_entry.get("identifier", "")
    persistent_url = dataset_entry.get("persistentUrl", "")
    persistent_id = f"doi:10.7910/{identifier}"
    dataset_id = dataset_entry.get("id")

    project_url = persistent_url
    project_folder = identifier.replace("/", "_")  # e.g., DVN_8T3WOR

    # Check if already processed
    existing = project_exists(conn, REPO_ID, project_url)
    if existing:
        print(f"[HARVARD] Skipping already processed: {identifier}")
        return

    print(f"[HARVARD] Processing dataset {identifier}")

    # Get full metadata
    time.sleep(DELAY_BETWEEN_REQUESTS)
    metadata = get_dataset_metadata(persistent_id)
    if not metadata:
        print(f"[HARVARD] Could not fetch metadata for {identifier}, skipping.")
        return

    field_map = extract_citation_fields(metadata)
    latest = metadata.get("latestVersion", {})

    # Build project data
    title = field_map.get("title", "")
    if isinstance(title, list):
        title = title[0] if title else ""

    # Description
    descriptions = field_map.get("dsDescription", [])
    description = ""
    if isinstance(descriptions, list) and descriptions:
        for d in descriptions:
            if isinstance(d, dict):
                val = d.get("dsDescriptionValue", {})
                if isinstance(val, dict):
                    description = val.get("value", "")
                elif isinstance(val, str):
                    description = val
                break

    # Authors
    authors = field_map.get("author", [])
    person_list = []
    if isinstance(authors, list):
        for a in authors:
            if isinstance(a, dict):
                name_field = a.get("authorName", {})
                if isinstance(name_field, dict):
                    name = name_field.get("value", "")
                elif isinstance(name_field, str):
                    name = name_field
                else:
                    name = ""
                if name:
                    person_list.append((name, "AUTHOR"))

    # Keywords
    keywords_raw = field_map.get("keyword", [])
    keywords = []
    if isinstance(keywords_raw, list):
        for k in keywords_raw:
            if isinstance(k, dict):
                kv = k.get("keywordValue", {})
                if isinstance(kv, dict):
                    kw = kv.get("value", "")
                elif isinstance(kv, str):
                    kw = kv
                else:
                    kw = ""
                if kw:
                    keywords.append(kw)

    # Subject as keywords too
    subjects = field_map.get("subject", [])
    if isinstance(subjects, list):
        for s in subjects:
            if isinstance(s, str) and s:
                keywords.append(s)

    # DOI
    doi = persistent_id.replace("doi:", "")

    # Upload date
    pub_date = dataset_entry.get("publicationDate", "")

    # Version
    version_num = latest.get("versionNumber", "")
    version_minor = latest.get("versionMinorNumber", "")
    version = f"{version_num}.{version_minor}" if version_num else None

    # License / Terms of Use
    terms = latest.get("termsOfUse", "")
    license_str = latest.get("license", {})
    if isinstance(license_str, dict):
        license_str = license_str.get("name", "")
    if not license_str and terms:
        license_str = "Custom Terms of Use"

    project_data = {
        "query_string": "qualitative research data",
        "repository_id": REPO_ID,
        "repository_url": "https://www.murray.harvard.edu/",
        "project_url": project_url,
        "version": version,
        "title": title,
        "description": description[:5000] if description else None,
        "language": "English",
        "doi": doi,
        "upload_date": pub_date,
        "download_repository_folder": REPO_FOLDER,
        "download_project_folder": project_folder,
        "download_version_folder": None,
        "download_method": "API-CALL",
    }

    project_id = insert_project(conn, project_data)

    # Insert keywords
    for kw in set(keywords):
        insert_keyword(conn, project_id, kw)

    # Insert persons
    for name, role in person_list:
        insert_person_role(conn, project_id, name, role)

    # Depositor
    depositor = field_map.get("depositor", "")
    if depositor:
        insert_person_role(conn, project_id, depositor, "UPLOADER")

    # Insert license
    if license_str:
        normalized = normalize_license(license_str)
        insert_license(conn, project_id, normalized)

    # Download files
    files = latest.get("files", [])
    project_dir = os.path.join(DATA_DIR, project_folder)
    os.makedirs(project_dir, exist_ok=True)

    if not files:
        print(f"[HARVARD] No files listed for {identifier}")

    for file_entry in files:
        data_file = file_entry.get("dataFile", {})
        file_id = data_file.get("id")
        file_name = data_file.get("filename", f"file_{file_id}")
        content_type = data_file.get("contentType", "")
        file_size = data_file.get("filesize", 0)

        # Determine file type from extension
        ext = os.path.splitext(file_name)[1].lstrip(".")
        if not ext:
            ext = content_type.split("/")[-1] if content_type else "unknown"
        file_type = ext

        # Check if restricted
        restricted = file_entry.get("restricted", False)
        if restricted:
            print(f"[HARVARD]   Restricted: {file_name}")
            insert_file(conn, project_id, file_name, file_type, "FAILED_LOGIN_REQUIRED")
            continue

        # Check file size
        if file_size > MAX_FILE_SIZE:
            print(f"[HARVARD]   Too large: {file_name} ({file_size} bytes)")
            insert_file(conn, project_id, file_name, file_type, "FAILED_TOO_LARGE")
            continue

        save_path = os.path.join(project_dir, file_name)

        if os.path.exists(save_path):
            print(f"[HARVARD]   Already exists: {file_name}")
            insert_file(conn, project_id, file_name, file_type, "SUCCEEDED")
            continue

        print(f"[HARVARD]   Downloading: {file_name} ({file_size} bytes)")
        time.sleep(DELAY_BETWEEN_REQUESTS)
        status = download_file(file_id, save_path)
        insert_file(conn, project_id, file_name, file_type, status)
        print(f"[HARVARD]   -> {status}")

    conn.commit()


def run(max_projects=200):
    """Run the Harvard Murray scraper."""
    print(f"[HARVARD] Starting scraper (max_projects={max_projects})")
    conn = get_connection()
    os.makedirs(DATA_DIR, exist_ok=True)

    # Get all datasets recursively
    print("[HARVARD] Fetching dataset list from MRA dataverse...")
    datasets = get_all_datasets()
    print(f"[HARVARD] Found {len(datasets)} datasets total")

    processed = 0
    for ds in datasets:
        if processed >= max_projects:
            break
        if ds.get("type") != "dataset":
            continue
        try:
            process_dataset(ds, conn)
            processed += 1
        except Exception as e:
            print(f"[HARVARD] Error processing {ds.get('identifier')}: {e}")
            conn.rollback()
            continue

    conn.close()
    print(f"[HARVARD] Done. Processed {processed} datasets.")