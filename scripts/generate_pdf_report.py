"""Generate a printable PDF classification report for QDArchive seeding."""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from db.database import get_connection


REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "classification_report.pdf")


def fetch_summary(conn):
    summary = {}
    summary["total"] = conn.execute("SELECT COUNT(*) as c FROM CLASSIFICATIONS").fetchone()[0]
    summary["category_counts"] = conn.execute(
        "SELECT classification, COUNT(*) as c FROM CLASSIFICATIONS GROUP BY classification"
    ).fetchall()
    summary["algorithm_counts"] = conn.execute(
        "SELECT algorithm, COUNT(*) as c FROM CLASSIFICATIONS GROUP BY algorithm"
    ).fetchall()
    summary["confidence_bands"] = conn.execute(
        "SELECT CASE "
        "WHEN confidence >= 0.75 THEN '>=0.75' "
        "WHEN confidence >= 0.5 THEN '0.50-0.74' "
        "WHEN confidence > 0 THEN '0.01-0.49' "
        "ELSE '0.00' END as band, COUNT(*) as c "
        "FROM CLASSIFICATIONS GROUP BY band ORDER BY band DESC"
    ).fetchall()
    summary["repo_counts"] = conn.execute(
        "SELECT p.repository_id, c.classification, COUNT(*) as c "
        "FROM PROJECTS p JOIN CLASSIFICATIONS c ON p.id = c.project_id "
        "GROUP BY p.repository_id, c.classification "
        "ORDER BY p.repository_id, c.classification"
    ).fetchall()
    summary["file_status_counts"] = conn.execute(
        "SELECT status, COUNT(*) as c FROM FILES GROUP BY status"
    ).fetchall()
    summary["total_files"] = conn.execute("SELECT COUNT(*) as c FROM FILES").fetchone()[0]
    summary["top_projects"] = conn.execute(
        "SELECT p.id, p.repository_id, p.title, c.classification, c.confidence "
        "FROM PROJECTS p JOIN CLASSIFICATIONS c ON p.id = c.project_id "
        "ORDER BY c.confidence DESC, p.id ASC LIMIT 12"
    ).fetchall()
    summary["unknown_projects"] = conn.execute(
        "SELECT p.id, p.repository_id, p.title "
        "FROM PROJECTS p JOIN CLASSIFICATIONS c ON p.id = c.project_id "
        "WHERE c.classification = 'UNKNOWN' "
        "ORDER BY p.id ASC LIMIT 12"
    ).fetchall()
    return summary


def create_paragraph(text, style_name="BodyText"):
    return Paragraph(text, getSampleStyleSheet()[style_name])


def build_table(data, col_widths=None):
    table = Table(data, colWidths=col_widths)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B7BEC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ])
    table.setStyle(style)
    return table


def build_report(summary):
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.fontSize = 22
    title_style.leading = 26

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#555555"),
    )

    body_style = styles["BodyText"]
    body_style.spaceAfter = 10

    story = []
    story.append(Paragraph("QDArchive Classification Report", title_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        Paragraph(
            "This document summarizes the project classification results generated from the seeded QDArchive database. "
            "The classification algorithm assigns each project to one of four categories based on title, description, and keyword metadata.",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("1. Executive Summary", styles["Heading2"]))
    story.append(
        Paragraph(
            f"A total of <b>{summary['total']}</b> seeded projects have been classified. "
            "Quantitative assignments are the largest share, while qualitative and mixed-methods labels are concentrated within the Harvard Murray Archive subset. "
            "The UNKNOWN category is used when metadata signals are insufficient or ambiguous.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "Confidence is scored from keyword matches in the project title, description, and metadata keywords. "
            "Higher confidence values indicate stronger evidence for the selected label.",
            body_style,
        )
    )

    story.append(Paragraph("2. Classification Results", styles["Heading2"]))
    story.append(
        Paragraph(
            "The following table shows the distribution of classification labels across all projects.",
            body_style,
        )
    )

    category_data = [["Classification", "Project Count", "Share"]]
    for row in summary["category_counts"]:
        percentage = row[1] / summary["total"] * 100 if summary["total"] else 0
        category_data.append([row[0], str(row[1]), f"{percentage:.1f}%"])
    story.append(build_table(category_data, col_widths=[5 * cm, 3 * cm, 3 * cm]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(
        Paragraph(
            "The count of classified projects by repository is shown below.",
            body_style,
        )
    )

    repo_data = [["Repository", "Classification", "Count", "Share"]]
    for row in summary["repo_counts"]:
        repo_name = "IHSN" if row[0] == 1 else "Harvard"
        repo_total = sum(r[2] for r in summary["repo_counts"] if r[0] == row[0])
        share = row[2] / repo_total * 100 if repo_total else 0
        repo_data.append([repo_name, row[1], str(row[2]), f"{share:.1f}%"])
    story.append(build_table(repo_data, col_widths=[4 * cm, 4 * cm, 2 * cm, 2 * cm]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("3. Algorithm and Confidence", styles["Heading2"]))
    story.append(
        Paragraph(
            "All classifications use a heuristic keyword scoring algorithm applied to project metadata. "
            "The confidence score reflects the strength of the matched keywords for each project.",
            body_style,
        )
    )

    algorithm_data = [["Algorithm", "Classified Projects"]]
    for row in summary["algorithm_counts"]:
        algorithm_data.append([row[0], str(row[1])])
    story.append(build_table(algorithm_data, col_widths=[8 * cm, 4 * cm]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            "The following confidence bands summarize classification strength across the dataset. "
            "Records with confidence below 0.50 are the best candidates for manual review.",
            body_style,
        )
    )
    band_data = [["Confidence Band", "Project Count"]]
    for row in summary["confidence_bands"]:
        band_data.append([row[0], str(row[1])])
    story.append(build_table(band_data, col_widths=[5 * cm, 4 * cm]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("4. Download Status Context", styles["Heading2"]))
    story.append(
        Paragraph(
            "Download status provides an operational view of dataset readiness. "
            "A large number of login-required failures means many files are not currently accessible without credentials.",
            body_style,
        )
    )
    file_data = [["File Status", "Count"]]
    for row in summary["file_status_counts"]:
        file_data.append([row[0], str(row[1])])
    file_data.append(["Total files", str(summary["total_files"])])
    story.append(build_table(file_data, col_widths=[7 * cm, 4 * cm]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("4. Representative Projects", styles["Heading2"]))
    story.append(
        Paragraph(
            "The following selected projects illustrate the most confidently classified records in the dataset.",
            body_style,
        )
    )

    top_data = [["ID", "Repository", "Classification", "Confidence", "Title"]]
    for row in summary["top_projects"]:
        repo_name = "IHSN" if row[1] == 1 else "Harvard"
        top_data.append([str(row[0]), repo_name, row[3], f"{row[4]:.2f}", row[2][:70]])
    story.append(build_table(top_data, col_widths=[1.2 * cm, 2 * cm, 3 * cm, 2 * cm, 7 * cm]))
    story.append(Spacer(1, 0.4 * cm))

    if summary["unknown_projects"]:
        story.append(Paragraph("5. Ambiguous Projects", styles["Heading2"]))
        story.append(
            Paragraph(
                "A small subset of projects remains in the UNKNOWN category due to weak or unclear metadata signals.",
                body_style,
            )
        )
        unknown_data = [["ID", "Repository", "Title"]]
        for row in summary["unknown_projects"]:
            repo_name = "IHSN" if row[1] == 1 else "Harvard"
            unknown_data.append([str(row[0]), repo_name, row[2][:90]])
        story.append(build_table(unknown_data, col_widths=[1.2 * cm, 2 * cm, 10 * cm]))
        story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("6. Notes", styles["Heading2"]))
    story.append(
        Paragraph(
            "The classification engine is intended to provide a first-pass labeling of seeded projects. "
            "Because the algorithm is based on metadata keyword frequency, projects with minimal metadata may be assigned to the UNKNOWN category.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "The report can serve as a foundation for future refinement, including manual review or machine learning-based classification.",
            body_style,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    story.append(
        Paragraph(
            f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#555555")),
        )
    )

    return story


def main(conn=None, output_path=None):
    if conn is None:
        conn = get_connection()
        close_conn = True
    else:
        close_conn = False

    try:
        summary = fetch_summary(conn)

        target_path = output_path or REPORT_PATH
        doc = SimpleDocTemplate(
            target_path,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        story = build_report(summary)
        doc.build(story)
        print(f"Report generated: {target_path}")
        return target_path
    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    main()
