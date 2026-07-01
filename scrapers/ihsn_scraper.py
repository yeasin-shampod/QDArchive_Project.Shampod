"""Scraper for IHSN catalog (catalog.ihsn.org) - v2."""

import os
import time
import json
import requests
from bs4 import BeautifulSoup
from db.database import (
    get_connection, insert_project, insert_file, insert_keyword,
    insert_person_role, insert_license, project_exists
)

BASE_URL = "https://catalog.ihsn.org"
API_URL = f"{BASE_URL}/index.php/api/catalog"
REPO_ID = 1
REPO_FOLDER = "ihsn"
DATA_DIR = os.path.join("data", REPO_FOLDER)
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB limit
REQUEST_TIMEOUT = 60
DELAY_BETWEEN_REQUESTS = 1  # seconds


def get_catalog_page(page=1, ps=15):
    """Fetch a page of catalog entries from the IHSN API."""
    params = {"page": page, "ps": ps}
    try:
        resp = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {})
    except requests.exceptions.RequestException as e:
        print(f"[IHSN] Error fetching catalog page={page}: {e}")
        return None


def get_project_metadata(catalog_id):
    """Fetch JSON metadata for a specific project."""
    url = f"{BASE_URL}/metadata/export/{catalog_id}/json"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[IHSN] Error fetching metadata for {catalog_id}: {e}")
        return None


def scrape_download_page(catalog_id):
    """Scrape the related-materials page for downloadable files."""
    url = f"{BASE_URL}/catalog/{catalog_id}/related-materials"
    files_found = []
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find all download links - match both /download/ and //catalog/.../download/
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/download/" in href:
                text = link.get_text(strip=True)
                # Normalize double slashes
                href = href.replace("//catalog/", "/catalog/")
                file_info = {"url": href, "label": text}
                files_found.append(file_info)
    except Exception as e:
        print(f"[IHSN] Error scraping downloads for {catalog_id}: {e}")
    return files_found


def download_file(url, save_path):
    """Download a file and return status."""
    try:
        if url.startswith("/"):
            url = BASE_URL + url

        # HEAD request to check size
        try:
            head = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            content_length = int(head.headers.get("content-length", 0))
            if content_length > MAX_FILE_SIZE:
                return "FAILED_TOO_LARGE"
        except Exception:
            pass

        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True)

        if resp.status_code == 401 or resp.status_code == 403:
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
        print(f"[IHSN] Unexpected download error: {e}")
        return "FAILED_SERVER_UNRESPONSIVE"


def extract_metadata(meta_json, catalog_entry):
    """Extract structured metadata from IHSN JSON export."""
    project_data = {
        "repository_id": REPO_ID,
        "repository_url": "https://ihsn.org/",
        "download_repository_folder": REPO_FOLDER,
        "download_method": "SCRAPING",
    }

    catalog_id = catalog_entry.get("id")
    project_data["project_url"] = f"{BASE_URL}/catalog/{catalog_id}"
    project_data["download_project_folder"] = str(catalog_id)
    project_data["query_string"] = "qualitative research data"
    project_data["title"] = catalog_entry.get("title", "")

    if meta_json:
        study = meta_json.get("study_desc", {})
        title_stmt = study.get("title_statement", {})
        project_data["title"] = title_stmt.get("title", project_data["title"])

        # Description / Abstract
        scope = study.get("study_info", {})
        abstract = scope.get("abstract", "")
        if isinstance(abstract, list):
            abstract = " ".join(abstract)
        project_data["description"] = abstract if abstract else catalog_entry.get("title", "")

        # Version
        version_stmt = meta_json.get("doc_desc", {}).get("version_statement", {})
        version = version_stmt.get("version", "")
        if isinstance(version, str) and len(version) > 500:
            version = version[:500]
        project_data["version"] = version

        # Language
        data_coll = study.get("data_collection", {})
        if isinstance(data_coll, list) and len(data_coll) > 0:
            data_coll = data_coll[0]
        lang = ""
        if isinstance(data_coll, dict):
            lang = data_coll.get("language", "")
        if not lang:
            study_info = study.get("study_info", {})
            if isinstance(study_info, dict):
                lang = study_info.get("language", "")
        project_data["language"] = lang if lang else None

        # DOI
        doi = title_stmt.get("doi", "")
        project_data["doi"] = doi if doi else None

        # Upload date
        prod_date = meta_json.get("doc_desc", {}).get("prod_date", "")
        project_data["upload_date"] = prod_date if prod_date else catalog_entry.get("created", "")

        project_data["download_version_folder"] = None

    return project_data, meta_json


def extract_keywords(meta_json, catalog_entry):
    """Extract keywords from metadata."""
    keywords = []
    if meta_json:
        study = meta_json.get("study_desc", {})
        study_info = study.get("study_info", {})

        kw_list = study_info.get("keywords", [])
        if isinstance(kw_list, list):
            for kw in kw_list:
                if isinstance(kw, dict):
                    k = kw.get("keyword", "")
                    if k:
                        keywords.append(k)
                elif isinstance(kw, str) and kw:
                    keywords.append(kw)

        topics = study_info.get("topics", [])
        if isinstance(topics, list):
            for t in topics:
                if isinstance(t, dict):
                    topic = t.get("topic", "")
                    if topic:
                        keywords.append(topic)
                elif isinstance(t, str) and t:
                    keywords.append(t)

    return list(set(keywords))


def extract_persons(meta_json, catalog_entry):
    """Extract person-role pairs from metadata."""
    persons = []
    if meta_json:
        doc_desc = meta_json.get("doc_desc", {})
        producers = doc_desc.get("producers", [])
        if isinstance(producers, list):
            for p in producers:
                if isinstance(p, dict):
                    name = p.get("name", "")
                    if name:
                        persons.append((name, "OTHER"))

        study = meta_json.get("study_desc", {})
        auth_entities = study.get("authoring_entity", [])
        if isinstance(auth_entities, list):
            for ae in auth_entities:
                if isinstance(ae, dict):
                    name = ae.get("name", "")
                    if name:
                        persons.append((name, "AUTHOR"))
                elif isinstance(ae, str) and ae:
                    persons.append((ae, "AUTHOR"))

        auth = catalog_entry.get("authoring_entity", "")
        if auth and not any(p[0] == auth for p in persons):
            persons.append((auth, "AUTHOR"))

    elif catalog_entry:
        auth = catalog_entry.get("authoring_entity", "")
        if auth:
            persons.append((auth, "AUTHOR"))

    return persons


def extract_license(meta_json):
    """Extract license info from metadata."""
    if meta_json:
        study = meta_json.get("study_desc", {})
        dist = study.get("distribution_statement", {})
        if isinstance(dist, dict):
            lic = dist.get("license", "")
            if lic:
                return lic

        data_access = study.get("data_access", {})
        if isinstance(data_access, dict):
            conditions = data_access.get("conditions", "")
            if conditions:
                return conditions[:200]

    return None


def process_project(catalog_entry, conn):
    """Process a single IHSN catalog entry."""
    catalog_id = catalog_entry["id"]
    project_url = f"{BASE_URL}/catalog/{catalog_id}"

    existing = project_exists(conn, REPO_ID, project_url)
    if existing:
        print(f"[IHSN] Skipping already processed: {catalog_id}")
        return

    print(f"[IHSN] Processing project {catalog_id}: {catalog_entry.get('title', '')[:60]}")

    time.sleep(DELAY_BETWEEN_REQUESTS)
    meta_json = get_project_metadata(catalog_id)

    project_data, meta = extract_metadata(meta_json, catalog_entry)
    project_id = insert_project(conn, project_data)

    keywords = extract_keywords(meta_json, catalog_entry)
    for kw in keywords:
        insert_keyword(conn, project_id, kw)

    persons = extract_persons(meta_json, catalog_entry)
    for name, role in persons:
        insert_person_role(conn, project_id, name, role)

    license_str = extract_license(meta_json)
    if license_str:
        insert_license(conn, project_id, license_str)

    project_dir = os.path.join(DATA_DIR, str(catalog_id))
    os.makedirs(project_dir, exist_ok=True)

    # ---- 1. Always download metadata JSON ----
    if meta_json:
        meta_path = os.path.join(project_dir, "metadata.json")
        if not os.path.exists(meta_path):
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_json, f, indent=2, ensure_ascii=False)
        insert_file(conn, project_id, "metadata.json", "json", "SUCCEEDED")
        print(f"[IHSN]   Saved: metadata.json")

    # ---- 2. Download DDI/XML metadata ----
    ddi_url = f"/metadata/export/{catalog_id}/ddi"
    ddi_file = "metadata_ddi.xml"
    ddi_path = os.path.join(project_dir, ddi_file)
    if not os.path.exists(ddi_path):
        time.sleep(DELAY_BETWEEN_REQUESTS)
        status = download_file(ddi_url, ddi_path)
    else:
        status = "SUCCEEDED"
    insert_file(conn, project_id, ddi_file, "xml", status)
    print(f"[IHSN]   DDI/XML: {status}")

    # ---- 3. Download PDF documentation if available ----
    pdf_url = f"{BASE_URL}/catalog/{catalog_id}/pdf-documentation"
    pdf_file = "documentation.pdf"
    pdf_path = os.path.join(project_dir, pdf_file)
    if not os.path.exists(pdf_path):
        time.sleep(DELAY_BETWEEN_REQUESTS)
        try:
            resp = requests.head(pdf_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            content_type = resp.headers.get("content-type", "")
            if "pdf" in content_type or resp.status_code == 200:
                status = download_file(pdf_url, pdf_path)
                # Check if we actually got a PDF (not an HTML error page)
                if status == "SUCCEEDED" and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        header = f.read(5)
                    if header != b"%PDF-":
                        os.remove(pdf_path)
                        status = "FAILED_LOGIN_REQUIRED"
            else:
                status = "FAILED_SERVER_UNRESPONSIVE"
        except Exception:
            status = "FAILED_SERVER_UNRESPONSIVE"
    else:
        status = "SUCCEEDED"
    insert_file(conn, project_id, pdf_file, "pdf", status)
    print(f"[IHSN]   PDF doc: {status}")

    # ---- 4. Scrape related-materials page for additional downloads ----
    time.sleep(DELAY_BETWEEN_REQUESTS)
    download_links = scrape_download_page(catalog_id)

    if download_links:
        print(f"[IHSN]   Found {len(download_links)} downloadable resources")
        for dl in download_links:
            url = dl["url"]
            label = dl.get("label", "")

            # Extract resource ID from URL
            resource_id = url.split("/")[-1]

            # Determine extension from label
            ext = ".pdf"
            label_lower = label.lower()
            if "doc" in label_lower and "pdf" not in label_lower:
                ext = ".doc"
            elif "xls" in label_lower:
                ext = ".xls"
            elif "csv" in label_lower:
                ext = ".csv"
            elif "zip" in label_lower:
                ext = ".zip"

            file_name = f"resource_{resource_id}{ext}"
            file_type = ext.lstrip(".")
            save_path = os.path.join(project_dir, file_name)

            if os.path.exists(save_path):
                print(f"[IHSN]   Already exists: {file_name}")
                insert_file(conn, project_id, file_name, file_type, "SUCCEEDED")
                continue

            print(f"[IHSN]   Downloading: {file_name}")
            time.sleep(DELAY_BETWEEN_REQUESTS)
            status = download_file(url, save_path)
            insert_file(conn, project_id, file_name, file_type, status)
            print(f"[IHSN]   -> {status}")
    else:
        # No related materials - check if microdata is remote/restricted
        form_model = catalog_entry.get("form_model", "")
        if form_model == "remote":
            insert_file(conn, project_id, "microdata", "data", "FAILED_LOGIN_REQUIRED")
            print(f"[IHSN]   Microdata: external/login required")

    conn.commit()


def run(max_projects=100):
    """Run the IHSN scraper."""
    print(f"[IHSN] Starting scraper (max_projects={max_projects})")
    conn = get_connection()
    os.makedirs(DATA_DIR, exist_ok=True)

    page = 1
    ps = 15
    limit = 50
    processed = 0

    while processed < max_projects:
        result = get_catalog_page(page=page, ps=ps)
        if not result:
            print("[IHSN] Failed to fetch catalog page, stopping.")
            break

        rows = result.get("rows", [])
        if not rows:
            print("[IHSN] No more entries.")
            break

        for entry in rows:
            if processed >= max_projects:
                break
            try:
                process_project(entry, conn)
                processed += 1
            except Exception as e:
                print(f"[IHSN] Error processing {entry.get('id')}: {e}")
                conn.rollback()
                continue

        page += 1
        print(f"[IHSN] Processed {processed} projects so far...")

    conn.close()
    print(f"[IHSN] Done. Processed {processed} projects.")
