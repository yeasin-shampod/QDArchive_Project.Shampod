"""Run the complete Part 2 (Data Classification) workflow.

This single entry point performs every Part 2 deliverable:

1. Builds ``23080363-sq26-classification.db`` from the Part 1 seeding database,
   derives the PROJECT_TYPE of every project and classifies all QDA / QD
   projects (and their primary files) with the ISIC Rev. 5 taxonomy.
2. Exports the result table to ``23080363-sq26-classification.xlsx`` (Step 4c).
3. Builds the PDF report ``23080363-sq26-classification-report.pdf`` (Step 4d).

Usage::

    python run_classification.py
"""

from classification.pipeline import run as run_classification
from export.export_classification_xlsx import export as export_xlsx
from export.classification_report_pdf import build_report


def main():
    print("=" * 64)
    print("Part 2 \u2014 Data Classification")
    print("=" * 64)

    run_classification()

    print("\n" + "-" * 64)
    print("Exporting result table (Step 4c)...")
    export_xlsx()

    print("\n" + "-" * 64)
    print("Building PDF report (Step 4d)...")
    build_report()

    print("\nDone. Deliverables:")
    print("  - 23080363-sq26-classification.db")
    print("  - 23080363-sq26-classification.xlsx")
    print("  - 23080363-sq26-classification-report.pdf")


if __name__ == "__main__":
    main()
