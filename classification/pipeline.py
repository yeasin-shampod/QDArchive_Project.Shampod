"""Part 2 orchestrator: build the classification database and populate it.

Running ``python -m classification.pipeline`` will:

1. Copy the Part 1 seeding database to ``23080363-sq26-classification.db``.
2. Add a ``type`` column (PROJECT_TYPE) to ``PROJECTS`` and create the
   ``PROJECT_CLASSES`` and ``FILE_CLASSES`` tables.
3. Derive the PROJECT_TYPE of every project from its files.
4. Run the ISIC Rev. 5 classifier on every ``QDA_PROJECT`` and ``QD_PROJECT``
   (the whole project plus each individual primary data file) and store the
   results.
"""

import os
import re
import shutil
import sqlite3

from classification.project_type import derive_project_type
from classification import isic
from classification.file_types import file_role, is_artifact

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDING_DB = os.path.join(ROOT, "23080363-seeding.db")
CLASSIFICATION_DB = os.path.join(ROOT, "23080363-sq26-classification.db")

# Only these project types are classified with ISIC (assignment, Part 2 Step 3).
CLASSIFIABLE_TYPES = ("QDA_PROJECT", "QD_PROJECT")


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------
def _build_database():
    """Create a fresh classification database from the seeding database."""
    if not os.path.exists(SEEDING_DB):
        raise FileNotFoundError(
            f"Seeding database not found at {SEEDING_DB}. Run Part 1 first."
        )
    shutil.copyfile(SEEDING_DB, CLASSIFICATION_DB)
    conn = sqlite3.connect(CLASSIFICATION_DB)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn):
    cur = conn.cursor()

    # Add the PROJECT_TYPE column if it does not exist yet.
    existing = {row["name"] for row in cur.execute("PRAGMA table_info(PROJECTS)")}
    if "type" not in existing:
        cur.execute("ALTER TABLE PROJECTS ADD COLUMN type TEXT")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS PROJECT_CLASSES (
            project_id          INTEGER PRIMARY KEY,
            project_type        TEXT,
            primary_section     TEXT,
            primary_division    TEXT,
            primary_class       TEXT,
            secondary_section   TEXT,
            secondary_division  TEXT,
            secondary_class     TEXT,
            no_project_files    INTEGER,
            tags                TEXT,
            method              TEXT,
            FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS FILE_CLASSES (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id     INTEGER,
            project_id  INTEGER,
            file_name   TEXT,
            section     TEXT,
            division    TEXT,
            class_name  TEXT,
            method      TEXT,
            FOREIGN KEY (file_id) REFERENCES FILES(id),
            FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
        )
        """
    )

    # Start from a clean slate on re-runs.
    cur.execute("DELETE FROM PROJECT_CLASSES")
    cur.execute("DELETE FROM FILE_CLASSES")
    conn.commit()


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def _project_keywords(conn, project_id):
    rows = conn.execute(
        "SELECT keyword FROM KEYWORDS WHERE project_id = ?", (project_id,)
    ).fetchall()
    return " ".join(r["keyword"] for r in rows if r["keyword"])


def _pooled_text(project, keywords):
    parts = [project["title"] or "", project["description"] or "", keywords]
    return " ".join(p for p in parts if p)


def _make_tags(text, classification, limit=8):
    """Build a small set of search tags from the project signal."""
    tags = []
    if classification["primary_section"]:
        tags.append(isic.section_name(classification["primary_section"]))
    if classification["primary_class"]:
        tags.append(classification["primary_class"])
    # add a few salient content words
    stop = {"data", "study", "research", "survey", "national", "analysis",
            "project", "dataset", "from", "with", "this", "that", "into",
            "report", "results"}
    words = [w for w in re.findall(r"[a-zA-Z]{5,}", (text or "").lower())
             if w not in stop]
    seen = set()
    for w in words:
        if w not in seen:
            seen.add(w)
            tags.append(w)
        if len(tags) >= limit:
            break
    # de-duplicate while preserving order
    out, seen = [], set()
    for t in tags:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return ", ".join(out[:limit])


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------
def run(verbose=True):
    conn = _build_database()
    cur = conn.cursor()

    projects = conn.execute(
        "SELECT id, repository_id, title, description FROM PROJECTS"
    ).fetchall()

    type_counts = {}
    classified_projects = 0
    classified_files = 0

    for project in projects:
        pid = project["id"]
        files = conn.execute(
            "SELECT id, file_name, file_type FROM FILES WHERE project_id = ?", (pid,)
        ).fetchall()

        # ---- Step 1: PROJECT_TYPE -------------------------------------
        project_type = derive_project_type(
            [(f["file_name"], f["file_type"]) for f in files]
        )
        cur.execute("UPDATE PROJECTS SET type = ? WHERE id = ?", (project_type, pid))
        type_counts[project_type] = type_counts.get(project_type, 0) + 1

        # number of real project files (excluding our scraping artifacts)
        no_project_files = sum(1 for f in files if not is_artifact(f["file_name"]))

        keywords = _project_keywords(conn, pid)
        pooled = _pooled_text(project, keywords)

        # ---- Step 3: ISIC classification (QDA + QD only) --------------
        if project_type in CLASSIFIABLE_TYPES:
            cls = isic.classify_text(pooled, title=project["title"])
            tags = _make_tags(pooled, cls)
            cur.execute(
                """
                INSERT INTO PROJECT_CLASSES (
                    project_id, project_type, primary_section, primary_division,
                    primary_class, secondary_section, secondary_division,
                    secondary_class, no_project_files, tags, method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid, project_type,
                    cls["primary_section"], cls["primary_division"], cls["primary_class"],
                    cls["secondary_section"], cls["secondary_division"], cls["secondary_class"],
                    no_project_files, tags,
                    "isic5-keyword-heuristic",
                ),
            )
            classified_projects += 1

            # classify each primary data file
            for f in files:
                if file_role(f["file_name"], f["file_type"]) != "PRIMARY":
                    continue
                file_text = " ".join([f["file_name"] or "", pooled])
                fcls = isic.classify_text(file_text, title=project["title"])
                cur.execute(
                    """
                    INSERT INTO FILE_CLASSES (
                        file_id, project_id, file_name, section, division,
                        class_name, method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f["id"], pid, f["file_name"],
                        fcls["primary_section"], fcls["primary_division"],
                        fcls["primary_class"], "isic5-keyword-heuristic",
                    ),
                )
                classified_files += 1
        else:
            # Still record the type and file count for the export table.
            cur.execute(
                """
                INSERT INTO PROJECT_CLASSES (
                    project_id, project_type, no_project_files, method
                ) VALUES (?, ?, ?, ?)
                """,
                (pid, project_type, no_project_files, "type-only"),
            )

    conn.commit()

    if verbose:
        print("Classification database:", CLASSIFICATION_DB)
        print("\nPROJECT_TYPE distribution:")
        for ptype in ("QDA_PROJECT", "QD_PROJECT", "OTHER_PROJECT", "NOT_A_PROJECT"):
            print(f"  {ptype:<14} {type_counts.get(ptype, 0)}")
        print(f"\nProjects ISIC-classified: {classified_projects}")
        print(f"Primary files ISIC-classified: {classified_files}")

    conn.close()
    return CLASSIFICATION_DB


if __name__ == "__main__":
    run()
