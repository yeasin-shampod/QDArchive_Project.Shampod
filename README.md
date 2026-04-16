# QDArchive Seeding Project — Part 1: Data Acquisition

**Student:** Yeasin Arafat Shampod  
**Matriculation ID:** 23080363  
**Supervisor:** Professor Dirk Riehle  
**University:** Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)  
**GitHub Repository:** [QDArchive_Project.Shampod](https://github.com/yeasin-shampod/QDArchive_Project.Shampod)

---

### What This Project Does

This project collects qualitative research data from two online repositories and stores everything in a structured SQLite database. The goal is to build a "seed" archive — downloading as many research files as possible (metadata, documentation, transcripts, datasets) while carefully recording what worked and what didn't.

I was assigned two repositories:

1. **IHSN** (International Household Survey Network) — [https://ihsn.org/](https://ihsn.org/)
2. **Harvard Murray Research Archive** — [https://www.murray.harvard.edu/](https://www.murray.harvard.edu/)

---

### How It Works

The pipeline runs in two stages — one scraper per repository. Both scrapers write into the same SQLite database (`23080363-seeding.db`) and download files to a local `data/` folder.

#### IHSN Scraper (`scrapers/ihsn_scraper.py`)

IHSN runs on the NADA open-source catalog platform. I used a combination of their catalog API and web scraping:

- **Catalog listing:** The NADA API (`/index.php/api/catalog`) returns a paginated list of all projects. I use the `page` and `ps` (page size) parameters to iterate through entries.
- **Metadata download:** For each project, I download the full metadata in JSON format (`/metadata/export/{id}/json`) and DDI/XML format (`/metadata/export/{id}/ddi`).
- **PDF documentation:** Many projects have a PDF documentation bundle available at `/catalog/{id}/pdf-documentation`.
- **Additional resources:** I scrape each project's "Related Materials" page (`/catalog/{id}/related-materials`) using BeautifulSoup to find extra downloadable files like questionnaires, reports, and technical documents.
- **Download method:** `SCRAPING` — because even though I use the API for listing, the actual file discovery and downloads require parsing HTML pages.

#### Harvard Murray Archive Scraper (`scrapers/harvard_scraper.py`)

The Murray Research Archive is hosted on Harvard Dataverse, which has a well-documented REST API:

- **Dataset discovery:** I start from the MRA dataverse (`/api/dataverses/mra/contents`) and recursively explore all sub-dataverses (like the "Original Murray Collection") to find every dataset.
- **Metadata retrieval:** Each dataset's full metadata is fetched via `/api/datasets/:persistentId`.
- **File downloads:** Individual files are downloaded through `/api/access/datafile/{fileId}`.
- **Download method:** `API-CALL` — the entire workflow uses the Dataverse API without any HTML scraping.

#### Running the Pipeline

```bash
# Install dependencies
pip install -r requirements.txt

# Run both scrapers (default: 500 projects for IHSN, all 386 for Harvard Murray)
python3 main.py --max-projects 500

# Run only one repository
python3 -c "from scrapers.ihsn_scraper import run; run(max_projects=200)"
python3 -c "from scrapers.harvard_scraper import run; run(max_projects=200)"

# View statistics
python3 export/stats.py

# Retry failed downloads
python3 scripts/retry_failed.py
```

---

### Database Schema

The SQLite database (`23080363-seeding.db`) is located in the root of this repository and contains six tables:

| Table | Purpose |
|-------|---------|
| `REPOSITORIES` | The two source repositories (IHSN and Harvard Murray) |
| `PROJECTS` | One row per research project/dataset, with title, description, DOI, language, and download metadata |
| `FILES` | Every file we attempted to download, with its status (succeeded or why it failed) |
| `KEYWORDS` | Subject keywords and topics extracted from project metadata |
| `PERSON_ROLE` | People associated with each project (authors, uploaders, etc.) |
| `LICENSES` | License information for each project |

**File status values:**
- `SUCCEEDED` — file was downloaded successfully
- `FAILED_LOGIN_REQUIRED` — file exists but requires authentication or a special access request
- `FAILED_SERVER_UNRESPONSIVE` — the server didn't respond or returned an error
- `FAILED_TOO_LARGE` — file exceeded the 500 MB size limit

---

### Final Statistics

| | IHSN | Harvard Murray | Total |
|---|---|---|---|
| **Projects** | 500 | 386 | 886 |
| **Total files recorded** | 3,858 | 11,978 | 15,836 |
| **Successfully downloaded** | 3,439 | 2,281 | 5,720 |
| **Failed (login required)** | — | 9,769 | 9,769 |
| **Failed (server issues)** | 347 | — | 347 |
| **Keywords extracted** | 6,093 | — | 6,093 |
| **Person-role entries** | — | — | 3,020 |
| **Disk usage** | 3.0 GB | 4.6 GB | ~7.6 GB |

---

### Folder Structure

```
QDArchive_Project.Shampod/
├── 23080363-seeding.db          # SQLite database (in repo root)
├── main.py                      # Main entry point
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── db/
│   ├── schema.sql               # Database schema definition
│   └── database.py              # Database helper functions
├── scrapers/
│   ├── ihsn_scraper.py          # IHSN catalog scraper
│   └── harvard_scraper.py       # Harvard Dataverse scraper
├── scripts/
│   └── retry_failed.py          # Retry failed downloads
├── export/
│   └── stats.py                 # Print database statistics
└── data/                        # Downloaded files (not in Git — uploaded separately)
    ├── ihsn/
    │   ├── 13286/
    │   │   ├── metadata.json
    │   │   ├── metadata_ddi.xml
    │   │   ├── documentation.pdf
    │   │   └── resource_*.pdf
    │   └── ...
    └── harvard-murray-archive/
        ├── DVN_8T3WOR/
        │   └── AJPS2005_replication.tab
        └── ...
```

---

### Technical Challenges

This section describes the real-world data challenges I ran into while building this pipeline. These are not programming bugs — they are problems that come from working with messy, inconsistent, and sometimes uncooperative data sources.

#### 1. IHSN's Broken API Pagination

The IHSN catalog API claims to have 12,826 entries, but the `offset` parameter simply does not work. No matter what offset value you pass, the API returns the same 15 entries every single time. I discovered this after multiple failed attempts and had to switch to using the `page` and `ps` (page size) parameters instead, which correctly paginate through the catalog. This is not documented anywhere — I found it through trial and error.

#### 2. Most IHSN Microdata Is Not Directly Downloadable

IHSN is primarily a metadata catalog, not a data hosting platform. The vast majority of actual research microdata is hosted on external repositories (like IPUMS International) and requires separate registration and approval. The catalog entry says "Data available from external repository" but provides no direct download link. I recorded these as `FAILED_LOGIN_REQUIRED` in the database and focused on downloading what was actually available: metadata files (JSON, DDI/XML), PDF documentation, questionnaires, and technical reports.

#### 3. Harvard Dataverse — Massive Number of Restricted Files

The Murray Research Archive contains a lot of sensitive social science data (psychological studies, longitudinal surveys, clinical research). Out of 4,260 files across 200 datasets, nearly 70% (2,979 files) are restricted and require a formal access request through Harvard Dataverse. There is no way to download these programmatically — you have to apply for access through the web interface and wait for approval. This is by design, not a bug. I logged every restricted file with `FAILED_LOGIN_REQUIRED` so the database accurately reflects what exists even if we couldn't download it.

#### 4. Inconsistent Metadata Across Repositories

The two repositories structure their metadata very differently:

- **IHSN** uses the DDI (Data Documentation Initiative) standard with deeply nested XML/JSON. Author information might be under `study_desc.authoring_entity`, or `doc_desc.producers`, or sometimes just a plain text string. Keywords could be in `study_info.keywords` or `study_info.topics` — and sometimes both fields contain different things.
- **Harvard Dataverse** uses its own JSON schema where authors are in `latestVersion.metadataBlocks.citation.fields`, buried several levels deep in a list of typed metadata fields. You have to iterate through the fields and match by `typeName` to find what you need.

I had to write separate extraction logic for each repository and handle many edge cases where fields were missing, empty, or in unexpected formats.

#### 5. License Information Is All Over the Place

IHSN projects rarely have a clean "license" field. Sometimes the license is buried in the `distribution_statement`, sometimes in `data_access.conditions`, and sometimes it's a full paragraph of legal text rather than a simple identifier like "CC BY 4.0". Harvard Dataverse is slightly better but still inconsistent — some datasets use standard Creative Commons identifiers while others have custom terms of use that are just free-text paragraphs. I normalize common licenses (CC0, CC BY, etc.) to short strings where possible and store the original text otherwise.

#### 6. PDF Documentation That Isn't Actually PDF

Some IHSN projects advertise a "PDF documentation" download, but when you actually fetch the URL, the server returns an HTML page (like a login form or an error page) with a 200 status code instead of a proper error. I had to add a check that reads the first few bytes of every downloaded "PDF" to verify it actually starts with `%PDF-`. If it doesn't, I delete the file and mark it as `FAILED_LOGIN_REQUIRED`.

#### 7. Duplicate Resource Links on IHSN

When scraping the "Related Materials" page on IHSN, some projects list the same downloadable resource twice (once in the main section and once in a sidebar or related section). Without deduplication, this would create duplicate entries in the FILES table. I handle this by checking if a file already exists on disk before downloading it again.

#### 8. Rate Limiting and Server Stability

Both repositories occasionally return 500 errors or simply time out, especially during peak hours. I added a 1-second delay between requests to be respectful to the servers and implemented retry logic for transient failures. Files that failed due to server issues are recorded as `FAILED_SERVER_UNRESPONSIVE` and can be retried later using the `scripts/retry_failed.py` script.

#### 9. File Size Concerns

Some datasets on Harvard Dataverse contain very large files (hundreds of megabytes each). To keep the download manageable and avoid filling up disk space, I set a 500 MB per-file limit. Files exceeding this limit are recorded as `FAILED_TOO_LARGE` in the database. In practice, no files hit this limit during our 200-project run, but the safeguard is there.

#### 10. No Standard Way to Identify "Qualitative" Data

Neither repository has a reliable filter for "qualitative research" specifically. IHSN is mostly survey/census data (quantitative), and the Murray Archive mixes qualitative and quantitative studies. The `query_string` field in the database records what search terms were used, but in practice I scraped broadly and included everything available rather than trying to filter by methodology — since the project goal is to seed the archive with as much data as possible.

---

### How to Reproduce

1. Clone this repository
2. Set up a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the pipeline:
   ```bash
   python3 main.py --max-projects 500
   ```
4. Check the results:
   ```bash
   python3 export/stats.py
   ```

The database will be created at `23080363-seeding.db` in the project root. Downloaded files go into the `data/` directory (or wherever `DATA_DIR` is configured in the scrapers).

---

### Submission Checklist

- [x] SQLite database `23080363-seeding.db` in repository root
- [x] Git tag `part-1-release` on final commit
- [x] `data/` folder uploaded to FAUbox / Google Drive
- [x] Submission form filled out with GitHub link and data folder link

---

### Dependencies

- Python 3.8+
- `requests` — HTTP requests for API calls and file downloads
- `beautifulsoup4` — HTML parsing for IHSN download page scraping
- `sqlite3` — built-in Python module for database operations
