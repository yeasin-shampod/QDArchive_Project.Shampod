"""Database initialization and utilities for QDArchive seeding."""
import sqlite3
import os
from pathlib import Path

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "23080363-seeding.db")


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with schema from schema.sql."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    conn = get_connection()
    cursor = conn.cursor()

    with open(schema_path, "r") as f:
        schema = f.read()

    cursor.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def insert_project(conn, project_data):
    """Insert a project into the database."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO PROJECTS (
            query_string, repository_id, repository_url, project_url,
            version, title, description, language, doi, upload_date,
            download_date, download_repository_folder, download_project_folder,
            download_version_folder, download_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_data.get("query_string"),
            project_data.get("repository_id"),
            project_data.get("repository_url"),
            project_data.get("project_url"),
            project_data.get("version"),
            project_data.get("title"),
            project_data.get("description"),
            project_data.get("language"),
            project_data.get("doi"),
            project_data.get("upload_date"),
            project_data.get("download_date"),
            project_data.get("download_repository_folder"),
            project_data.get("download_project_folder"),
            project_data.get("download_version_folder"),
            project_data.get("download_method"),
        )
    )
    conn.commit()
    project_id = cursor.lastrowid
    return project_id


def insert_file(conn, project_id, file_name, file_type, status):
    """Insert a file record into the database."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO FILES (project_id, file_name, file_type, status) VALUES (?, ?, ?, ?)",
        (project_id, file_name, file_type, status)
    )
    conn.commit()


def insert_keyword(conn, project_id, keyword):
    """Insert a keyword into the database."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO KEYWORDS (project_id, keyword) VALUES (?, ?)",
        (project_id, keyword)
    )
    conn.commit()


def insert_person_role(conn, project_id, name, role):
    """Insert a person role into the database."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO PERSON_ROLE (project_id, name, role) VALUES (?, ?, ?)",
        (project_id, name, role)
    )
    conn.commit()


def insert_license(conn, project_id, license_text):
    """Insert a license into the database."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO LICENSES (project_id, license) VALUES (?, ?)",
        (project_id, license_text)
    )
    conn.commit()


def get_all_projects(repository_id=None):
    """Get all projects, optionally filtered by repository."""
    conn = get_connection()
    cursor = conn.cursor()
    if repository_id:
        cursor.execute("SELECT * FROM PROJECTS WHERE repository_id = ?", (repository_id,))
    else:
        cursor.execute("SELECT * FROM PROJECTS")
    results = cursor.fetchall()
    conn.close()
    return results


def project_exists(conn, repository_id, project_url):
    """Check if a project already exists in the database."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM PROJECTS WHERE repository_id = ? AND project_url = ?",
        (repository_id, project_url)
    )
    result = cursor.fetchone()
    return result is not None
