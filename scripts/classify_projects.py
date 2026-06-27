"""Project classification utility for QDArchive seeding."""

import re
from db.database import get_connection, insert_classification, get_keywords_for_project


QUALITATIVE_KEYWORDS = {
    "qualitative", "interview", "focus group", "ethnographic", "observation",
    "case study", "textual", "narrative", "discourse", "phenomenolog",
    "grounded theory", "thematic", "content analysis", "qualitative research",
    "participant", "fieldwork", "interviews", "field study", "case studies",
}

QUANTITATIVE_KEYWORDS = {
    "quantitative", "survey", "questionnaire", "statistical", "regression",
    "modeling", "experiment", "sample", "sampling", "scale", "demographic",
    "analysis of variance", "correlation", "descriptive statistics", "inferential",
    "measurements", "numerical", "data collection",
}

MIXED_KEYWORDS = {
    "mixed methods", "mixed-methods", "mixed methods research", "qual+quan",
}


def normalize_text(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).lower()).strip()


def score_text(text):
    text = normalize_text(text)
    qualitative_score = sum(1 for kw in QUALITATIVE_KEYWORDS if kw in text)
    quantitative_score = sum(1 for kw in QUANTITATIVE_KEYWORDS if kw in text)
    mixed_score = sum(1 for kw in MIXED_KEYWORDS if kw in text)
    return qualitative_score, quantitative_score, mixed_score


def classify_project(project, conn):
    title = project["title"] or ""
    description = project["description"] or ""
    keywords = " ".join(get_keywords_for_project(conn, project["id"]))

    title_scores = score_text(title)
    description_scores = score_text(description)
    keyword_scores = score_text(keywords)

    q_score = title_scores[0] + description_scores[0] + keyword_scores[0]
    n_score = title_scores[1] + description_scores[1] + keyword_scores[1]
    m_score = title_scores[2] + description_scores[2] + keyword_scores[2]

    if m_score > 0:
        classification = "MIXED"
    elif q_score > n_score and q_score > 0:
        classification = "QUALITATIVE"
    elif n_score > q_score and n_score > 0:
        classification = "QUANTITATIVE"
    elif q_score == n_score and q_score > 0:
        classification = "MIXED"
    else:
        classification = "UNKNOWN"

    total = q_score + n_score + m_score
    confidence = float(total) / (total + 2) if total > 0 else 0.0
    return classification, confidence


def classify_projects(force=False):
    conn = get_connection()
    projects = conn.execute("SELECT id, title, description FROM PROJECTS").fetchall()
    for project in projects:
        existing = conn.execute(
            "SELECT id FROM CLASSIFICATIONS WHERE project_id = ?",
            (project["id"],),
        ).fetchone()
        if existing and not force:
            continue

        classification, confidence = classify_project(project, conn)
        insert_classification(conn, project["id"], classification, confidence)

    conn.close()
