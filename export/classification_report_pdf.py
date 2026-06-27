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
import textwrap
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, "23080363-sq26-classification.db")
DEFAULT_OUT = os.path.join(ROOT, "23080363-sq26-classification-report.pdf")

# Optional cover assets. Drop the university logo here and it is embedded on the
# title page automatically; if the file is absent the report still builds.
LOGO_PATH = os.path.join(ROOT, "assets", "university-logo.png")
UNIVERSITY = "Friedrich-Alexander-Universit\u00e4t Erlangen-N\u00fcrnberg"
COURSE = ""   # optional module / course name shown under the university

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
def _draw_logo(fig):
    """Embed the university logo at the top of the cover, if available."""
    if not os.path.exists(LOGO_PATH):
        return
    try:
        img = mpimg.imread(LOGO_PATH)
    except Exception:
        return
    ih, iw = img.shape[0], img.shape[1]
    aspect = iw / ih
    h = 0.13                                   # logo height (figure fraction)
    w = h * aspect * (8.27 / 11.69)            # preserve aspect on A4 landscape
    w = min(w, 0.34)
    ax = fig.add_axes([0.5 - w / 2, 0.82, w, h])
    ax.imshow(img)
    ax.axis("off")


def _title_page(pdf, conn):
    fig = plt.figure(figsize=(11.69, 8.27))   # A4 landscape
    fig.patch.set_facecolor("white")

    _draw_logo(fig)
    fig.text(0.5, 0.785, UNIVERSITY, ha="center", fontsize=13, color="#1B2A4A")
    if COURSE:
        fig.text(0.5, 0.752, COURSE, ha="center", fontsize=11, color="#555555")

    fig.text(0.5, 0.655, "QDArchive Seeding \u2014 Part 2", ha="center",
             fontsize=27, fontweight="bold", color="#1B2A4A")
    fig.text(0.5, 0.595, "Data Classification Report", ha="center",
             fontsize=16, color="#4B7BEC")
    fig.add_artist(plt.Line2D([0.30, 0.70], [0.560, 0.560],
                              transform=fig.transFigure,
                              color="#4B7BEC", linewidth=1.2))

    total = conn.execute("SELECT COUNT(*) FROM PROJECT_CLASSES").fetchone()[0]
    classified = conn.execute(
        "SELECT COUNT(*) FROM PROJECT_CLASSES WHERE primary_class IS NOT NULL"
    ).fetchone()[0]
    files = conn.execute("SELECT COUNT(*) FROM FILE_CLASSES").fetchone()[0]
    n_repos = len(_repositories(conn))

    rows = [
        ("Student", "Yeasin Arafat Shampod"),
        ("Matriculation number", "23080363"),
        ("Taxonomy", "ISIC Rev. 5 \u2014 section + division"),
        ("Repositories", str(n_repos)),
        ("Projects in database", str(total)),
        ("Projects with an ISIC class", str(classified)),
        ("Primary files classified", str(files)),
    ]
    y = 0.475
    for label, value in rows:
        fig.text(0.31, y, label, ha="left", fontsize=12, color="#555555")
        fig.text(0.69, y, value, ha="right", fontsize=12, fontweight="bold",
                 color="#1B2A4A")
        y -= 0.050

    pdf.savefig(fig)
    plt.close(fig)


def _histogram_page(pdf, repo_name, counts):
    items = counts.most_common()
    total = sum(counts.values())
    labels = [_wrap(name) for name, _ in items]
    values = [c for _, c in items]

    height = max(4.5, 0.46 * len(items) + 2.6)
    fig, ax = plt.subplots(figsize=(11.69, height))
    y = range(len(items))
    bars = ax.barh(list(y), values, color="#4B7BEC",
                   edgecolor="#2E5BBA", linewidth=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()                      # most common on top
    ax.set_xlabel("Number of projects (primary ISIC class)", fontsize=10)
    ax.set_title(f"{repo_name}\nHistogram of primary ISIC classes "
                 f"({total} classified projects)",
                 fontsize=13, fontweight="bold", color="#1B2A4A")
    ax.xaxis.grid(True, linestyle=":", linewidth=0.6, color="#CCCCCC")
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    xmax = max(values) if values else 1
    for bar, value in zip(bars, values):
        pct = value / total * 100 if total else 0
        ax.text(bar.get_width() + xmax * 0.012,
                bar.get_y() + bar.get_height() / 2,
                f"{value}  ({pct:.1f}%)", va="center", ha="left",
                fontsize=8.5, fontweight="bold", color="#1B2A4A")
    ax.set_xlim(0, xmax * 1.20)
    ax.margins(y=0.01)
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _table_page(pdf, repo_name, counts, type_counts):
    items = counts.most_common(TOP_N)
    total = sum(counts.values())

    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.5, 0.955, repo_name, ha="center", fontsize=15,
             fontweight="bold", color="#1B2A4A")
    fig.text(0.5, 0.915, f"Rank-ordered primary ISIC classes (top {TOP_N})",
             ha="center", fontsize=12, color="#4B7BEC")

    summary = "     ".join(
        f"{t.replace('_PROJECT', '')}: {type_counts.get(t, 0)}"
        for t in ("QDA_PROJECT", "QD_PROJECT", "OTHER_PROJECT", "NOT_A_PROJECT")
    )
    fig.text(0.5, 0.875, f"Project types  \u2014  {summary}",
             ha="center", fontsize=10, color="#555555")

    ax = fig.add_axes([0.06, 0.06, 0.88, 0.78])
    ax.axis("off")

    table_data = [["Rank", "ISIC Rev. 5 class", "Count", "Share", "Cumulative"]]
    cum = 0
    for rank, (name, count) in enumerate(items, start=1):
        cum += count
        share = f"{(count / total * 100):.1f}%" if total else "0%"
        cums = f"{(cum / total * 100):.1f}%" if total else "0%"
        table_data.append([str(rank), name, str(count), share, cums])
    if not items:
        table_data.append(["\u2014", "No classified projects", "0", "0%", "0%"])

    table = ax.table(cellText=table_data,
                     colWidths=[0.07, 0.58, 0.10, 0.11, 0.14],
                     cellLoc="left", loc="upper center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#4B7BEC")
            cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#EEF3FF")
        cell.set_edgecolor("#D5DEF2")
        if c >= 2:
            cell.get_text().set_ha("center")

    fig.text(0.06, 0.04,
             f"Total classified projects in this repository: {total}.",
             ha="left", fontsize=9, color="#888888")
    pdf.savefig(fig)
    plt.close(fig)


def _narrative(repo_name, counts, type_counts):
    """Build a short, natural-language discussion of the repository's results."""
    total = sum(counts.values())
    short = repo_name.split(" (")[0]

    if total == 0:
        return [
            f"No projects in the {short} repository were eligible for ISIC "
            "classification: none were QDA or QD projects with derivable subject "
            "content, so the histogram and ranking above are empty by design."
        ]

    ranked = counts.most_common()
    n_classes = len(ranked)
    (c1n, c1) = ranked[0]
    p1 = c1 / total * 100

    paras = [
        f"Across the {total} classifiable projects in the {short} repository, "
        f"\u201c{c1n}\u201d is clearly the leading subject area, covering {c1} "
        f"projects ({p1:.0f}% of the collection)."
    ]

    if n_classes >= 3:
        (c2n, c2), (c3n, c3) = ranked[1], ranked[2]
        p2, p3 = c2 / total * 100, c3 / total * 100
        top3 = (c1 + c2 + c3) / total * 100
        paras.append(
            f"It is followed, at a clear distance, by \u201c{c2n}\u201d "
            f"({c2} projects, {p2:.0f}%) and \u201c{c3n}\u201d ({c3}, {p3:.0f}%). "
            f"Together these three leading classes account for {top3:.0f}% of the "
            "repository\u2019s classified projects."
        )
    elif n_classes == 2:
        (c2n, c2) = ranked[1]
        p2 = c2 / total * 100
        paras.append(
            f"The only other class present is \u201c{c2n}\u201d "
            f"({c2} projects, {p2:.0f}%)."
        )

    if p1 >= 60:
        concentration = "highly concentrated"
    elif p1 >= 35:
        concentration = "moderately concentrated"
    else:
        concentration = "fairly diverse"
    tail = sum(1 for _, c in ranked if c <= 2)
    spread = (
        f"In total {n_classes} distinct ISIC Rev. 5 divisions are represented, "
        f"which makes this a {concentration} collection."
    )
    if tail:
        spread += (
            f" {tail} of those divisions appear only once or twice and form a "
            "long tail of niche topics."
        )
    paras.append(spread)

    qda = type_counts.get("QDA_PROJECT", 0)
    qd = type_counts.get("QD_PROJECT", 0)
    other = type_counts.get("OTHER_PROJECT", 0)
    nap = type_counts.get("NOT_A_PROJECT", 0)
    other_word = "project" if other == 1 else "projects"
    nap_word = "entry" if nap == 1 else "entries"
    paras.append(
        f"By project type the repository holds {qd} QD and {qda} QDA projects "
        f"(only these two types are classified), alongside {other} other-data "
        f"{other_word} and {nap} {nap_word} with no derivable project files. "
        "Each subject was assigned with a keyword-scoring classifier that maps a "
        "project\u2019s title, description and keywords onto the official ISIC "
        "Rev. 5 divisions, giving the title the greatest weight because it most "
        "reliably names the subject of the data."
    )
    return paras


def _comment_page(pdf, repo_name, counts, type_counts):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.5, 0.95, repo_name, ha="center", fontsize=15,
             fontweight="bold", color="#1B2A4A")
    fig.text(0.5, 0.91, "Discussion of findings", ha="center",
             fontsize=12, color="#4B7BEC")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.885, 0.885],
                              transform=fig.transFigure,
                              color="#D5DEF2", linewidth=1.0))

    y = 0.83
    for para in _narrative(repo_name, counts, type_counts):
        wrapped = textwrap.fill(para, width=108)
        fig.text(0.08, y, wrapped, ha="left", va="top", fontsize=11.5,
                 linespacing=1.5, color="#222222")
        n_lines = wrapped.count("\n") + 1
        y -= 0.040 * n_lines + 0.035

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
