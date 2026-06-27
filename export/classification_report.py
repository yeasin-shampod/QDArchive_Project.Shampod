"""Generate classification report for QDArchive seeding."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_connection


def generate_classification_report(conn=None, output_path=None, print_report=True):
    if conn is None:
        conn = get_connection()
        close_conn = True
    else:
        close_conn = False

    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT p.id, p.title, p.repository_id, c.classification, c.confidence, c.algorithm "
            "FROM PROJECTS p JOIN CLASSIFICATIONS c ON p.id = c.project_id "
            "ORDER BY c.classification, p.id"
        ).fetchall()

        if print_report:
            print("Classification report")
            print("=" * 60)
            print(f"Total classified projects: {len(rows)}")
            print("")
            print("ID\tRepo\tClassification\tConfidence\tTitle")
            for row in rows:
                repo = "IHSN" if row["repository_id"] == 1 else "Harvard"
                print(
                    f"{row['id']}\t{repo}\t{row['classification']}\t{row['confidence']:.2f}\t{row['title'][:80]}"
                )

        if output_path is None:
            output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "classification_report.pdf")

        from scripts.generate_pdf_report import main as generate_pdf_report

        # Reuse the existing PDF report generator by writing to the requested path.
        import importlib.util
        import pathlib

        spec = importlib.util.spec_from_file_location("generate_pdf_report_mod", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "generate_pdf_report.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        module.REPORT_PATH = output_path
        module.main(conn=conn)

        return output_path
    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    generate_classification_report()

