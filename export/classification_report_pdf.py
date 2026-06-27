"""Part 2 Step 4d: build the classification PDF report.

For each repository the report contains:

* a histogram of the primary ISIC classes identified, using the full ISIC
  Rev. 5 class name as the bin label, with the count printed on each bar;
* a rank-ordered table of the top-twenty classes with their counts;
* a short comment on the findings.

The whole document is produced with matplotlib's PDF backend, so every page is
true **vector** graphics and can be zoomed in without quality loss.
"""

import os
import sqlite3
from collections import Counter
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, "23080363-sq26-classification.db")
DEFAULT_OUT = os.path.join(ROOT, "23080363-sq26-classification-report.pdf")

TOP_N = 20


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _repo_name_from_url(url):
    """Derive a readable repository name from its base URL."""
    if not url:
        return None
    host = url.split("//", 1)[-1].strip("/").lower()
    if host.startswith("www."):
        host = host[4:]
    if "ihsn" in host:
        return "IHSN Survey Catalog (ihsn.org)"
    if "murray" in host or "harvard" in host:
        return "Harvard Murray Research Archive (murray.harvard.edu)"
    return host or None


def _repositories(conn):
    """Return ``[(repository_id, name), ...]`` for every repository.

    The classification database is derived from the Part 1 seeding database,
    which stores the repository only as ``PROJECTS.repository_id`` (the separate
    ``REPOSITORIES`` table was removed for validator compliance). The list is
    therefore derived from the projects themselves; a legacy ``REPOSITORIES``
    table is still honoured when present.
    """
    if _table_exists(conn, "REPOSITORIES"):
        rows = conn.execute(
            "SELECT id, name FROM REPOSITORIES ORDER BY id"
        ).fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]

    rows = conn.execute(
        """
        SELECT repository_id AS rid, MIN(repository_url) AS url
        FROM PROJECTS
        GROUP BY repository_id
        ORDER BY repository_id
        """
    ).fetchall()
    result = []
    for r in rows:
        rid = r["rid"]
        name = _repo_name_from_url(r["url"]) or f"Repository {rid}"
        result.append({"id": rid, "name": name})
    return result


def _primary_class_counts(conn, repository_id):
    rows = conn.execute(
        """
        SELECT pc.primary_class AS cls
        FROM PROJECT_CLASSES pc
        JOIN PROJECTS p ON p.id = pc.project_id
        WHERE p.repository_id = ? AND pc.primary_class IS NOT NULL
        """,
        (repository_id,),
    ).fetchall()
    return Counter(r["cls"] for r in rows)


def _project_type_counts(conn, repository_id):
    rows = conn.execute(
        """
        SELECT pc.project_type AS t, COUNT(*) AS c
        FROM PROJECT_CLASSES pc
        JOIN PROJECTS p ON p.id = pc.project_id
        WHERE p.repository_id = ?
        GROUP BY pc.project_type
        """,
        (repository_id,),
    ).fetchall()
    return {r["t"]: r["c"] for r in rows}


def _wrap(label, width=48):
    """Wrap a long class name onto at most two lines for axis labels."""
    if len(label) <= width:
        return label
    words = label.split()
    line, lines = "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
        if len(lines) == 1:           # keep to two lines, truncate the rest
            break
    rest = " ".join(words[sum(len(l.split()) for l in lines):])
    if rest:
        if len(rest) > width:
            rest = rest[: width - 1] + "\u2026"
        lines.append(rest)
    return "\n".join(lines[:2])


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------
def _title_page(pdf, conn):
    fig = plt.figure(figsize=(11.69, 8.27))   # A4 landscape
    fig.text(0.5, 0.66, "QDArchive Seeding \u2014 Part 2", ha="center",
             fontsize=26, fontweight="bold")
    fig.text(0.5, 0.58, "Data Classification Report", ha="center", fontsize=18)
    total = conn.execute("SELECT COUNT(*) FROM PROJECT_CLASSES").fetchone()[0]
    classified = conn.execute(
        "SELECT COUNT(*) FROM PROJECT_CLASSES WHERE primary_class IS NOT NULL"
    ).fetchone()[0]
    lines = [
        "Student: Yeasin Arafat Shampod  (23080363)",
        "Classification taxonomy: ISIC Rev. 5 (section + division)",
        f"Projects in database: {total}",
        f"Projects with an ISIC class: {classified}",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
    ]
    fig.text(0.5, 0.42, "\n".join(lines), ha="center", fontsize=12, linespacing=1.8)
    pdf.savefig(fig)
    plt.close(fig)


def _histogram_page(pdf, repo_name, counts):
    items = counts.most_common()
    labels = [_wrap(name) for name, _ in items]
    values = [c for _, c in items]

    height = max(4.5, 0.42 * len(items) + 2.5)
    fig, ax = plt.subplots(figsize=(11.69, height))
    y = range(len(items))
    bars = ax.barh(list(y), values, color="#4B7BEC")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()                      # most common on top
    ax.set_xlabel("Number of projects (primary class)")
    ax.set_title(f"{repo_name} \u2014 Histogram of primary ISIC classes",
                 fontsize=14, fontweight="bold")

    xmax = max(values) if values else 1
    for bar, value in zip(bars, values):
        ax.text(bar.get_width() + xmax * 0.01,
                bar.get_y() + bar.get_height() / 2,
                str(value), va="center", ha="left", fontsize=8, fontweight="bold")
    ax.set_xlim(0, xmax * 1.12)
    ax.margins(y=0.01)
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _table_page(pdf, repo_name, counts, type_counts):
    items = counts.most_common(TOP_N)
    total = sum(counts.values())

    fig = plt.figure(figsize=(11.69, 8.27))
    fig.suptitle(f"{repo_name} \u2014 Rank-ordered primary classes (top {TOP_N})",
                 fontsize=14, fontweight="bold", y=0.97)

    # project-type summary line
    summary = "   ".join(
        f"{t}: {type_counts.get(t, 0)}"
        for t in ("QDA_PROJECT", "QD_PROJECT", "OTHER_PROJECT", "NOT_A_PROJECT")
    )
    fig.text(0.5, 0.91, f"Project types \u2014 {summary}", ha="center", fontsize=10)

    ax = fig.add_axes([0.06, 0.08, 0.88, 0.78])
    ax.axis("off")

    table_data = [["Rank", "ISIC Rev. 5 class (division)", "Count", "Share"]]
    for rank, (name, count) in enumerate(items, start=1):
        share = f"{(count / total * 100):.1f}%" if total else "0%"
        table_data.append([str(rank), name, str(count), share])
    if not items:
        table_data.append(["\u2014", "No classified projects", "0", "0%"])

    table = ax.table(cellText=table_data, colWidths=[0.07, 0.66, 0.12, 0.12],
                     cellLoc="left", loc="upper center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#4B7BEC")
            cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#F0F4FF")
        cell.set_edgecolor("#CCCCCC")

    pdf.savefig(fig)
    plt.close(fig)


def _comment_page(pdf, repo_name, counts, type_counts):
    total = sum(counts.values())
    dominant = counts.most_common(1)
    dominant_txt = (
        f"{dominant[0][0]} ({dominant[0][1]} projects, "
        f"{dominant[0][1] / total * 100:.0f}% of classified projects)"
        if dominant and total else "n/a"
    )
    n_classes = len(counts)

    fig = plt.figure(figsize=(11.69, 8.27))
    fig.suptitle(f"{repo_name} \u2014 Comments on findings",
                 fontsize=14, fontweight="bold", y=0.95)

    comment = (
        f"\u2022 The dominant primary class is: {dominant_txt}.\n\n"
        f"\u2022 In total {n_classes} distinct ISIC Rev. 5 divisions were "
        f"identified across the classified projects of this repository.\n\n"
        f"\u2022 Project-type breakdown: "
        + ", ".join(f"{t} = {type_counts.get(t, 0)}"
                    for t in ("QDA_PROJECT", "QD_PROJECT",
                              "OTHER_PROJECT", "NOT_A_PROJECT"))
        + ".\n\n"
        "\u2022 The classification is produced by a transparent keyword-scoring "
        "heuristic over each project's title, description and keywords, mapped "
        "to the official ISIC Rev. 5 divisions. The distribution reflects the "
        "subject focus of the repository's holdings."
    )
    fig.text(0.08, 0.78, comment, ha="left", va="top", fontsize=11,
             wrap=True, linespacing=1.6)
    pdf.savefig(fig)
    plt.close(fig)


def build_report(db_path=DEFAULT_DB, out_path=DEFAULT_OUT):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    with PdfPages(out_path) as pdf:
        _title_page(pdf, conn)
        for repo in _repositories(conn):
            counts = _primary_class_counts(conn, repo["id"])
            type_counts = _project_type_counts(conn, repo["id"])
            _histogram_page(pdf, repo["name"], counts)
            _table_page(pdf, repo["name"], counts, type_counts)
            _comment_page(pdf, repo["name"], counts, type_counts)

    conn.close()
    print(f"Wrote report to {out_path}")
    return out_path


if __name__ == "__main__":
    build_report()
