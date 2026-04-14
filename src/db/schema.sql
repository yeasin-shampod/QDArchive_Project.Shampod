-- Schema for QDArchive Seeding Database
-- Student ID: 23080363

CREATE TABLE IF NOT EXISTS REPOSITORIES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS PROJECTS (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_string TEXT,
    repository_id INTEGER NOT NULL,
    repository_url TEXT,
    project_url TEXT,
    version TEXT,
    title TEXT,
    description TEXT,
    language TEXT,
    doi TEXT,
    upload_date TEXT,
    download_date TEXT,
    download_repository_folder TEXT,
    download_project_folder TEXT,
    download_version_folder TEXT,
    download_method TEXT CHECK(download_method IN ('SCRAPING', 'API-CALL')),
    FOREIGN KEY (repository_id) REFERENCES REPOSITORIES(id)
);

CREATE TABLE IF NOT EXISTS FILES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    file_name TEXT,
    file_type TEXT,
    status TEXT CHECK(status IN ('SUCCEEDED', 'FAILED_LOGIN_REQUIRED', 'FAILED_SERVER_UNRESPONSIVE', 'FAILED_TOO_LARGE')),
    FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
);

CREATE TABLE IF NOT EXISTS KEYWORDS (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    keyword TEXT,
    FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
);

CREATE TABLE IF NOT EXISTS PERSON_ROLE (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT,
    role TEXT CHECK(role IN ('AUTHOR', 'UPLOADER', 'OWNER', 'OTHER', 'UNKNOWN')),
    FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
);

CREATE TABLE IF NOT EXISTS LICENSES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    license TEXT,
    FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
);

-- Seed the REPOSITORIES table
INSERT OR IGNORE INTO REPOSITORIES (id, name, url) VALUES (1, 'ihsn', 'https://ihsn.org/');
INSERT OR IGNORE INTO REPOSITORIES (id, name, url) VALUES (2, 'harvard-murray-archive', 'https://www.murray.harvard.edu/');