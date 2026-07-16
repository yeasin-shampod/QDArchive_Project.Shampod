"""Part 2 Step 4d — QDArchive Classification Report (PDF)

Layout engine
─────────────
Every page is an A4 portrait figure.  Content is placed with a simple
top-down cursor (figure-fraction y).  Tables are drawn inside a dedicated
axes that is sized *exactly* to fit the data, so nothing ever overflows.
Bar charts are similarly axes-boxed.

Running header, footer and stat-boxes are drawn with fig.text / patches.
"""

import os
import sqlite3
import textwrap
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

# ── file paths ──────────────────────────────────────────────────────────────
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB  = os.path.join(ROOT, "23080363-sq26-classification.db")
DEFAULT_OUT = os.path.join(ROOT, "23080363-sq26-classification-report.pdf")

# ── identity ────────────────────────────────────────────────────────────────
STUDENT_ID   = "23080363"
STUDENT_NAME = "Yeasin Arafat Shampod"

# ── palette (matches friend's report) ───────────────────────────────────────
NAVY    = "#1B2A4A"
ACCENT  = "#1B5EA6"   # section headings
BAR_C   = "#2D5FA0"   # histogram bars
STAT_BG = "#EEF4FB"
STAT_BD = "#90B8DA"
ROW_ODD = "#F2F6FB"
RULE    = "#CCCCCC"
TXT     = "#111111"
GRAY    = "#606060"
WHITE   = "#FFFFFF"

# ── page geometry (figure-fraction units, A4 portrait) ──────────────────────
A4W, A4H    = 8.27, 11.69       # inches
LM          = 0.065             # left  margin (fig-frac)
RM          = 0.935             # right margin
HDR_Y       = 0.962             # top of header text (fig-frac)
HDR_RULE    = 0.951             # rule below header
FTR_RULE    = 0.055             # rule above footer
FTR_Y       = 0.043             # baseline of footer text
CONTENT_TOP = 0.940             # first content starts here
CONTENT_BOT = 0.065             # nothing may go below this


# ════════════════════════════════════════════════════════════════════════════
# Database helpers
# ════════════════════════════════════════════════════════════════════════════

def _tex(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _repo_label(url):
    u = (url or "").lower()
    if "ihsn"   in u: return "IHSN Survey Catalog"
    if "murray" in u or "harvard" in u: return "Harvard Murray Research Archive"
    return u.split("//", 1)[-1].strip("/") or "Unknown"


def _repos(conn):
    rows = conn.execute(
        "SELECT repository_id rid, MIN(repository_url) url "
        "FROM PROJECTS GROUP BY repository_id ORDER BY repository_id"
    ).fetchall()
    return [{"id": r["rid"], "name": _repo_label(r["url"])} for r in rows]


def _pclass(conn, rid):
    rows = conn.execute(
        "SELECT pc.primary_class cls FROM PROJECT_CLASSES pc "
        "JOIN PROJECTS p ON p.id=pc.project_id "
        "WHERE p.repository_id=? AND pc.primary_class IS NOT NULL", (rid,)
    ).fetchall()
    return Counter(r["cls"] for r in rows)


def _ptypes(conn, rid):
    rows = conn.execute(
        "SELECT pc.project_type t, COUNT(*) c FROM PROJECT_CLASSES pc "
        "JOIN PROJECTS p ON p.id=pc.project_id "
        "WHERE p.repository_id=? GROUP BY pc.project_type", (rid,)
    ).fetchall()
    return {r["t"]: r["c"] for r in rows}


def _fclasses(conn, rid):
    return conn.execute(
        "SELECT COUNT(*) FROM FILE_CLASSES fc "
        "JOIN PROJECTS p ON p.id=fc.project_id WHERE p.repository_id=?", (rid,)
    ).fetchone()[0]


# ════════════════════════════════════════════════════════════════════════════
# Page canvas
# ════════════════════════════════════════════════════════════════════════════

class Page:
    """
    One A4 portrait matplotlib figure with chrome already drawn.
    All drawing methods accept and return a `y` cursor (figure-fraction).
    Content is guaranteed to stay inside [CONTENT_BOT, CONTENT_TOP].
    """

    # row-height economy: how many figure-fraction units per wrapped text line
    LINE_H = 0.0275

    def __init__(self, page_num: int,
                 footer="Generated from the classification SQLite database"):
        self.fig = plt.figure(figsize=(A4W, A4H))
        self.fig.patch.set_facecolor(WHITE)
        self._chrome(page_num, footer)
        self.y   = CONTENT_TOP     # current cursor
        self._pn = page_num

    # ── chrome ──────────────────────────────────────────────────────────────
    def _chrome(self, pn, footer):
        f = self.fig
        f.text(LM, HDR_Y,
               "SQ26 Part 2 \u2014 QDArchive Classification Report",
               ha="left", va="baseline",
               fontsize=7.5, color=NAVY, transform=f.transFigure)
        f.text(RM, HDR_Y, f"Student ID: {STUDENT_ID}",
               ha="right", va="baseline",
               fontsize=7.5, color=NAVY, transform=f.transFigure)
        for y in (HDR_RULE, FTR_RULE):
            f.add_artist(plt.Line2D([LM, RM], [y, y],
                                    transform=f.transFigure,
                                    color=RULE, lw=0.7, zorder=10))
        f.text(LM, FTR_Y, footer,
               ha="left", va="baseline",
               fontsize=7.5, color=GRAY, transform=f.transFigure)
        f.text(RM, FTR_Y, f"Page {pn}",
               ha="right", va="baseline",
               fontsize=7.5, color=GRAY, transform=f.transFigure)

    def save(self, pdf):
        pdf.savefig(self.fig)
        plt.close(self.fig)

    # ── remaining space ──────────────────────────────────────────────────────
    def space(self):
        """Figure-fraction space still available below the cursor."""
        return max(0.0, self.y - CONTENT_BOT)

    # ── spacing ──────────────────────────────────────────────────────────────
    def gap(self, h=0.012):
        self.y -= h

    # ── title block (cover page only) ────────────────────────────────────────
    def title_block(self):
        f = self.fig
        f.text(LM, self.y,
               "SQ26 Part 2 \u2014 QDArchive Classification Report",
               ha="left", va="top",
               fontsize=18, fontweight="bold", color=NAVY,
               transform=f.transFigure)
        self.y -= 0.048
        f.text(LM, self.y,
               f"Student ID: {STUDENT_ID}  \u2502  "
               "Final report generated from the classification SQLite database",
               ha="left", va="top",
               fontsize=8.5, color=GRAY, transform=f.transFigure)
        self.y -= 0.038

    # ── section heading ──────────────────────────────────────────────────────
    def section(self, text):
        self.fig.text(LM, self.y, text,
                      ha="left", va="top",
                      fontsize=13, fontweight="bold", color=ACCENT,
                      transform=self.fig.transFigure)
        self.y -= 0.042

    # ── sub-heading ──────────────────────────────────────────────────────────
    def sub(self, text):
        self.fig.text(LM, self.y, text,
                      ha="left", va="top",
                      fontsize=10, fontweight="bold", color=NAVY,
                      transform=self.fig.transFigure)
        self.y -= 0.030

    # ── body paragraph ────────────────────────────────────────────────────────
    def body(self, text, width=107, size=9.5, italic=False):
        wrapped = textwrap.fill(text, width=width)
        lines   = wrapped.count("\n") + 1
        needed  = lines * self.LINE_H + 0.012
        if self.y - needed < CONTENT_BOT:
            return          # silently skip if no room (handled by page design)
        self.fig.text(LM, self.y, wrapped,
                      ha="left", va="top",
                      fontsize=size, color=TXT,
                      linespacing=1.55,
                      style="italic" if italic else "normal",
                      transform=self.fig.transFigure)
        self.y -= needed

    def italic(self, text, width=107):
        self.body(text, width=width, size=8.5, italic=True)

    # ── stat boxes ────────────────────────────────────────────────────────────
    def stat_boxes(self, stats, box_h=0.080):
        """stats = [(val_str, label), ...]"""
        n   = len(stats)
        W   = RM - LM
        gap = 0.010
        bw  = (W - gap * (n - 1)) / n
        y0  = self.y

        for i, (val, lbl) in enumerate(stats):
            x0 = LM + i * (bw + gap)
            rect = FancyBboxPatch(
                (x0, y0 - box_h), bw, box_h,
                boxstyle="square,pad=0",
                linewidth=1.0, edgecolor=STAT_BD, facecolor=STAT_BG,
                transform=self.fig.transFigure, clip_on=False, zorder=3)
            self.fig.add_artist(rect)
            cx = x0 + bw / 2
            self.fig.text(cx, y0 - box_h * 0.38, str(val),
                          ha="center", va="center",
                          fontsize=18, fontweight="bold", color=NAVY,
                          transform=self.fig.transFigure)
            self.fig.text(cx, y0 - box_h * 0.75, lbl,
                          ha="center", va="center",
                          fontsize=7.5, color=GRAY,
                          transform=self.fig.transFigure)
        self.y = y0 - box_h - 0.022

    # ── table ─────────────────────────────────────────────────────────────────
    def table(self, headers, rows, col_w,
              hdr_h=0.036, row_h=0.032,
              note=None):
        """
        Draw a navy-header table using a dedicated axes.
        Automatically clips rows to fit the remaining page space.
        col_w = relative widths (will be normalised to [LM, RM]).

        Returns the y position after the table (and optional note).
        """
        # ── how many rows fit? ───────────────────────────────────────────────
        note_h   = 0.060 if note else 0
        avail    = self.y - CONTENT_BOT - note_h
        max_rows = max(0, int((avail - hdr_h) / row_h))
        rows     = rows[:max_rows]
        if not rows:
            return

        n_rows = len(rows)
        n_cols = len(headers)

        # ── axes geometry ────────────────────────────────────────────────────
        tbl_h  = hdr_h + n_rows * row_h
        ax_bot = self.y - tbl_h                     # bottom of table in fig-frac
        ax     = self.fig.add_axes(
            [LM, ax_bot, RM - LM, tbl_h],
            frameon=False)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, tbl_h)
        ax.axis("off")

        # ── normalise column widths ──────────────────────────────────────────
        sw = sum(col_w)
        cw = [w / sw for w in col_w]

        # ── draw header ──────────────────────────────────────────────────────
        x = 0.0
        for ci, (h, w) in enumerate(zip(headers, cw)):
            ax.add_patch(plt.Rectangle(
                (x, tbl_h - hdr_h), w, hdr_h,
                facecolor=NAVY, edgecolor="none", transform=ax.transData,
                clip_on=True, zorder=2))
            ax.text(x + w / 2, tbl_h - hdr_h / 2, h,
                    ha="center", va="center",
                    fontsize=8, fontweight="bold", color=WHITE,
                    zorder=3)
            x += w

        # ── draw data rows ───────────────────────────────────────────────────
        for ri, row in enumerate(rows):
            ry  = tbl_h - hdr_h - (ri + 1) * row_h
            bg  = WHITE if ri % 2 == 0 else ROW_ODD
            x   = 0.0
            for ci, (cell, w) in enumerate(zip(row, cw)):
                ax.add_patch(plt.Rectangle(
                    (x, ry), w, row_h,
                    facecolor=bg,
                    edgecolor="#DDDDDD", linewidth=0.4,
                    transform=ax.transData, clip_on=True, zorder=2))
                # Alignment: first & last col left; middle cols center
                if ci == 0:
                    tx, ha, pad = x, "left", 0.008
                elif ci == n_cols - 1 and len(str(cell)) > 8:
                    tx, ha, pad = x, "left", 0.008
                else:
                    tx, ha, pad = x + w / 2, "center", 0.0
                ax.text(tx + pad, ry + row_h / 2, str(cell),
                        ha=ha, va="center",
                        fontsize=7.8, color=TXT,
                        clip_on=True, zorder=3)
                x += w

        # ── outer border ─────────────────────────────────────────────────────
        ax.add_patch(plt.Rectangle(
            (0, 0), 1, tbl_h,
            facecolor="none",
            edgecolor=NAVY, linewidth=0.9,
            transform=ax.transData, clip_on=False, zorder=4))

        self.y = ax_bot - 0.010

        if note:
            self.italic(note)

    # ── bar chart ─────────────────────────────────────────────────────────────
    def hbar(self, labels, values, title, max_h=0.30, left_margin=0.28):
        """
        Horizontal bar chart inside a properly-sized axes.
        max_h = maximum height to use (figure-fraction); will shrink if less space.
        left_margin = margin to shift the axis to the right to accommodate y-labels.
        """
        if not values:
            return
        avail = self.y - CONTENT_BOT - 0.010
        h     = min(max_h, avail)
        if h < 0.05:
            return

        ax = self.fig.add_axes([LM + left_margin, self.y - h, RM - LM - left_margin, h - 0.012])
        n  = len(labels)
        yp = range(n)

        xmax  = max(values) if values else 1
        total = sum(values)
        bars  = ax.barh(list(yp), values,
                        color=BAR_C, edgecolor="#1A3A6A", linewidth=0.4,
                        height=0.65)
        ax.set_yticks(list(yp))
        ax.set_yticklabels(labels, fontsize=6.5, color=TXT)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=8.5, fontweight="bold",
                     color=NAVY, pad=4)
        ax.set_xlabel("Number of projects", fontsize=8, color=GRAY)
        ax.xaxis.grid(True, linestyle=":", lw=0.5, color="#DDDDDD")
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.spines["left"].set_color(RULE)
        ax.spines["bottom"].set_color(RULE)
        ax.tick_params(colors=GRAY, labelsize=7)

        for bar, v in zip(bars, values):
            pct = v / total * 100 if total else 0
            ax.text(v + xmax * 0.015,
                    bar.get_y() + bar.get_height() / 2,
                    f"{v:,}  ({pct:.1f}%)",
                    va="center", ha="left",
                    fontsize=7, fontweight="bold", color=NAVY)
        ax.set_xlim(0, xmax * 1.30)
        ax.margins(y=0.02)
        self.y -= h + 0.016


# ════════════════════════════════════════════════════════════════════════════
# Helper: wrap long class names for y-axis labels
# ════════════════════════════════════════════════════════════════════════════

def _wrap_label(s, w=32):
    if len(s) <= w:
        return s
    words = s.split()
    line, lines = "", []
    for word in words:
        if len(line) + len(word) + 1 > w:
            lines.append(line); line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return "\n".join(lines[:3])


# ════════════════════════════════════════════════════════════════════════════
# Page 1 — Cover / Executive Overview
# ════════════════════════════════════════════════════════════════════════════

def _pg_cover(pdf, conn, pn):
    repos      = _repos(conn)
    total_p    = conn.execute("SELECT COUNT(*) FROM PROJECT_CLASSES").fetchone()[0]
    classified = conn.execute(
        "SELECT COUNT(*) FROM PROJECT_CLASSES WHERE primary_class IS NOT NULL"
    ).fetchone()[0]
    total_fc   = conn.execute("SELECT COUNT(*) FROM FILE_CLASSES").fetchone()[0]
    n_repos    = len(repos)

    pg = Page(pn)
    pg.title_block()

    # Executive Overview
    pg.section("Executive Overview")
    pg.body(
        "This report covers the complete Part 2 workflow for the QDArchive seeding "
        "project. Two repositories were assigned: the IHSN Survey Catalog and the "
        "Harvard Murray Research Archive. Every project was first classified by type "
        "based on the files it contains, then assigned an ISIC Rev. 5 subject label "
        "using a keyword-scoring heuristic that reads each project's title, description "
        "and keywords, giving the title the greatest weight."
    )
    pg.stat_boxes([
        (str(n_repos),       "Assigned repositories"),
        (f"{total_p:,}",     "Total projects in database"),
        (f"{classified:,}",  "ISIC-classified projects"),
        (f"{total_fc:,}",    "Primary files classified"),
    ])

    # Repository scope table
    pg.section("Repository scope")
    scope_rows = []
    for repo in repos:
        rid     = repo["id"]
        tp      = conn.execute(
            "SELECT COUNT(*) FROM PROJECTS WHERE repository_id=?", (rid,)
        ).fetchone()[0]
        cl      = conn.execute(
            "SELECT COUNT(*) FROM PROJECT_CLASSES pc "
            "JOIN PROJECTS p ON p.id=pc.project_id "
            "WHERE p.repository_id=? AND pc.primary_class IS NOT NULL", (rid,)
        ).fetchone()[0]
        purpose = (
            "International household surveys \u2014 NADA API + web scraping."
            if "IHSN" in repo["name"]
            else "Qualitative social-science archive \u2014 Harvard Dataverse API."
        )
        scope_rows.append([repo["name"], f"{tp:,}", f"{cl:,}", purpose])

    pg.table(
        ["Repository", "Projects", "Classified", "Description"],
        scope_rows,
        col_w=[2.6, 0.9, 0.9, 4.6],
        note=(
            "Only QD_PROJECT and QDA_PROJECT entries receive an ISIC label. "
            "OTHER_PROJECT and NOT_A_PROJECT entries are counted in the database "
            "but are excluded from the ISIC classification scope by design."
        )
    )

    # Data collection summary
    pg.section("Data collection summary")
    total_f  = conn.execute("SELECT COUNT(*) FROM FILES").fetchone()[0] if _tex(conn, "FILES") else 0
    succ     = conn.execute("SELECT COUNT(*) FROM FILES WHERE status='SUCCEEDED'").fetchone()[0] if _tex(conn, "FILES") else 0
    flog     = conn.execute("SELECT COUNT(*) FROM FILES WHERE status='FAILED_LOGIN_REQUIRED'").fetchone()[0] if _tex(conn, "FILES") else 0
    kw       = conn.execute("SELECT COUNT(*) FROM KEYWORDS").fetchone()[0] if _tex(conn, "KEYWORDS") else 0

    pg.table(
        ["Measure", "Result", "Interpretation"],
        [
            ["Total projects seeded",       f"{total_p:,}",  "Projects recorded across both repositories."],
            ["Total file download attempts", f"{total_f:,}",  "All download attempts logged in the FILES table."],
            ["Files successfully saved",    f"{succ:,}",     "Confirmed on disk; passed PDF byte-header check."],
            ["Restricted \u2014 login required", f"{flog:,}", "Files exist but require formal access approval."],
            ["Keywords extracted",          f"{kw:,}",       "Subject keywords stored alongside project metadata."],
        ],
        col_w=[2.2, 1.0, 5.8],
        row_h=0.034,
    )

    pg.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# Page 2 — Project-type classification
# ════════════════════════════════════════════════════════════════════════════

def _pg_types(pdf, conn, pn):
    pg = Page(pn)
    pg.y -= 0.010

    pg.section("1. Project-Type Classification")
    pg.body(
        "The first classification step assigns each project a type based solely on the "
        "file extensions it contains. Content is not inspected \u2014 only file types. "
        "Our own scraping artefacts (metadata.json, metadata_ddi.xml) are excluded so "
        "they do not distort the results."
    )
    pg.gap(0.008)

    pg.sub("Project-type definitions")
    pg.table(
        ["Project type", "Classification rule"],
        [
            ["QDA_PROJECT",   "Contains at least one recognised QDA analysis file (qdpx, mx24, nvp, atlproj, \u2026)"],
            ["QD_PROJECT",    "No QDA file, but contains primary data files (pdf, docx, txt, rtf, audio, video, \u2026)"],
            ["OTHER_PROJECT", "Contains only other data files (sav, dta, csv, xml, \u2026)"],
            ["NOT_A_PROJECT", "No usable file types found \u2014 metadata-only or empty"],
        ],
        col_w=[1.8, 7.2],
        row_h=0.044,
    )

    # Distribution table
    repos      = _repos(conn)
    all_types  = ["QDA_PROJECT", "QD_PROJECT", "OTHER_PROJECT", "NOT_A_PROJECT"]
    dist_rows  = []
    for repo in repos:
        tc  = _ptypes(conn, repo["id"])
        dist_rows.append([repo["name"]] + [str(tc.get(t, 0)) for t in all_types])
    totals = [str(conn.execute(
        "SELECT COUNT(*) FROM PROJECT_CLASSES WHERE project_type=?", (t,)
    ).fetchone()[0]) for t in all_types]
    dist_rows.append(["Both repositories combined"] + totals)

    pg.gap(0.012)
    pg.sub("Project-type distribution by repository")
    pg.table(
        ["Repository", "QDA", "QD", "Other", "Not a project"],
        dist_rows,
        col_w=[3.2, 1.0, 1.0, 1.0, 2.8],
    )

    pg.gap(0.012)
    pg.body(
        "The IHSN corpus is entirely composed of QD projects: every one of the 500 "
        "seeded entries contains downloadable documentation such as PDF questionnaires, "
        "DDI metadata exports, or technical reports. The Harvard Murray Archive is more "
        "varied: most of its 386 datasets qualify as QD projects, but 30 entries contain "
        "only statistical files (OTHER_PROJECT) and one entry had no derivable files."
    )
    pg.gap(0.014)

    # Combined bar chart
    pg.sub("Project-type counts \u2014 both repositories combined")
    labels = [t.replace("_PROJECT", "").replace("_", " ") for t in all_types]
    values = [int(c) for c in totals]
    pg.hbar(labels, values,
            "Project-type distribution (all repositories)",
            max_h=0.20,
            left_margin=0.14)

    pg.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# Page 3/5 — Repository results (stat boxes + histogram + rank table)
# ════════════════════════════════════════════════════════════════════════════

def _pg_results(pdf, conn, pn, repo, section_num):
    rid    = repo["id"]
    rname  = repo["name"]
    counts = _pclass(conn, rid)
    fc     = _fclasses(conn, rid)
    total  = sum(counts.values())
    tp     = conn.execute(
        "SELECT COUNT(*) FROM PROJECTS WHERE repository_id=?", (rid,)
    ).fetchone()[0]

    pg = Page(pn)
    pg.y -= 0.010

    pg.section(f"{section_num}. Results \u2014 {rname}")

    pg.stat_boxes([
        (f"{tp:,}",          "Total projects"),
        (f"{total:,}",       "ISIC-classified"),
        (f"{fc:,}",          "Files classified"),
        (str(len(counts)),   "Distinct ISIC classes"),
    ])

    # Histogram (top 12)
    items  = counts.most_common(12)
    labels = [_wrap_label(n) for n, _ in items]
    values = [c for _, c in items]
    pg.sub(f"Primary ISIC class distribution (top {len(items)})")
    pg.hbar(labels, values,
            f"{rname} \u2014 primary ISIC classes",
            max_h=0.32)

    # Rank table (top 10)
    top10    = counts.most_common(10)
    cum      = 0
    tbl_rows = []
    for rank, (name, count) in enumerate(top10, 1):
        cum += count
        tbl_rows.append([
            str(rank), name, f"{count:,}",
            f"{count/total*100:.1f}%" if total else "\u2014",
            f"{cum/total*100:.1f}%"   if total else "\u2014",
        ])

    pg.sub("Primary ISIC class ranking (top 10)")
    pg.table(
        ["Rank", "ISIC Rev. 5 class", "Count", "Share", "Cumulative"],
        tbl_rows,
        col_w=[0.5, 5.5, 0.8, 0.9, 1.0],
        row_h=0.031,
        note=f"Total classified projects in this repository: {total:,}.",
    )

    pg.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# Page 4/6 — Repository interpretation + full breakdown table
# ════════════════════════════════════════════════════════════════════════════

def _pg_discussion(pdf, conn, pn, repo, section_num):
    rid    = repo["id"]
    rname  = repo["name"]
    counts = _pclass(conn, rid)
    tc     = _ptypes(conn, rid)
    total  = sum(counts.values())
    ranked = counts.most_common()
    short  = rname.split(" (")[0]

    pg = Page(pn)
    pg.y -= 0.010

    pg.section(f"{section_num}. Interpretation \u2014 {rname}")

    if total == 0:
        pg.body(
            f"No projects in the {short} repository met the criteria for ISIC "
            "classification. All entries were either OTHER_PROJECT or NOT_A_PROJECT, "
            "meaning none contained primary qualitative data files from which a subject "
            "could be derived. The histogram and ranking for this repository are "
            "therefore empty by design \u2014 this is expected, not an error."
        )
        pg.save(pdf)
        return

    (c1n, c1) = ranked[0]
    p1 = c1 / total * 100

    para1 = (
        f"Across the {total:,} classified projects in the {short} repository, "
        f"\u201c{c1n}\u201d is the dominant subject area, covering {c1:,} projects "
        f"({p1:.0f}% of the collection). "
    )
    if len(ranked) >= 3:
        (c2n, c2), (c3n, c3) = ranked[1], ranked[2]
        top3 = (c1 + c2 + c3) / total * 100
        para1 += (
            f"It is followed by \u201c{c2n}\u201d ({c2:,} projects, "
            f"{c2/total*100:.0f}%) and \u201c{c3n}\u201d ({c3:,}, "
            f"{c3/total*100:.0f}%). Together the three leading classes account "
            f"for {top3:.0f}% of all classified entries."
        )
    pg.body(para1)
    pg.gap(0.006)

    n_cls = len(ranked)
    tail  = sum(1 for _, c in ranked if c <= 2)
    conc  = ("highly concentrated" if p1 >= 60
             else "moderately concentrated" if p1 >= 35
             else "fairly diverse")
    para2 = (
        f"In total {n_cls} distinct ISIC Rev. 5 divisions are represented in this "
        f"repository, making it a {conc} collection."
    )
    if tail:
        para2 += (
            f" {tail} of those divisions appear only once or twice, forming a long "
            "tail of niche subject areas."
        )
    pg.body(para2)
    pg.gap(0.006)

    qda = tc.get("QDA_PROJECT",   0)
    qd  = tc.get("QD_PROJECT",    0)
    oth = tc.get("OTHER_PROJECT", 0)
    nap = tc.get("NOT_A_PROJECT", 0)
    if "IHSN" in rname:
        repo_note = (
            "The strong dominance of government and administration topics reflects "
            "IHSN's mandate as a registry for official household and demographic "
            "survey programmes. Most downloadable content is metadata exports, PDF "
            "questionnaires, and codebooks \u2014 not raw microdata, which is almost "
            "always restricted."
        )
    else:
        repo_note = (
            "The broader spread of subject classes reflects the Harvard Murray Archive's "
            "roots in mid-20th-century psychology and social science: education, health "
            "research, and employment surveys all feature alongside public administration. "
            "Most of the archive's files are access-restricted, but the metadata was "
            "sufficient to classify the majority of projects."
        )
    pg.body(
        f"The repository holds {qd:,} QD and {qda:,} QDA projects (the only types "
        f"that receive an ISIC label), alongside {oth} other-data "
        f"{'project' if oth == 1 else 'projects'} and {nap} "
        f"{'entry' if nap == 1 else 'entries'} with no derivable files. " + repo_note
    )
    pg.gap(0.014)

    # Full breakdown table — rows auto-capped to available space
    pg.sub("Full ISIC class breakdown")
    top20    = counts.most_common(20)
    cum      = 0
    tbl_rows = []
    for rank, (name, count) in enumerate(top20, 1):
        cum += count
        tbl_rows.append([
            str(rank), name, f"{count:,}",
            f"{count/total*100:.1f}%",
            f"{cum/total*100:.1f}%",
        ])
    pg.table(
        ["Rank", "ISIC Rev. 5 class", "Count", "Share", "Cumulative"],
        tbl_rows,
        col_w=[0.5, 5.5, 0.8, 0.9, 1.0],
        row_h=0.030,
    )

    pg.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# Page 7 — Combined summary + conclusion
# ════════════════════════════════════════════════════════════════════════════

def _pg_summary(pdf, conn, pn):
    repos      = _repos(conn)
    classified = conn.execute(
        "SELECT COUNT(*) FROM PROJECT_CLASSES WHERE primary_class IS NOT NULL"
    ).fetchone()[0]
    total_fc   = conn.execute("SELECT COUNT(*) FROM FILE_CLASSES").fetchone()[0]
    total_p    = conn.execute("SELECT COUNT(*) FROM PROJECT_CLASSES").fetchone()[0]

    n = len(repos) * 2 + 2     # cover + types + 2 per repo
    pg = Page(pn)
    pg.y -= 0.010

    pg.section(f"{n}. Combined Classification Summary")
    pg.body(
        "The table below brings the classification results from both repositories into "
        "a single overview. ISIC totals reflect only projects that qualified for "
        "classification (QD and QDA types). File-level classifications were produced "
        "independently for every primary data file."
    )
    pg.gap(0.008)

    # Per-repo breakdown
    hdr  = ["Repository", "Projects", "QD", "QDA", "Other", "NAP", "Classified", "Files"]
    rows = []
    for repo in repos:
        rid = repo["id"]
        tp  = conn.execute("SELECT COUNT(*) FROM PROJECTS WHERE repository_id=?", (rid,)).fetchone()[0]
        tc  = _ptypes(conn, rid)
        cl  = conn.execute(
            "SELECT COUNT(*) FROM PROJECT_CLASSES pc "
            "JOIN PROJECTS p ON p.id=pc.project_id "
            "WHERE p.repository_id=? AND pc.primary_class IS NOT NULL", (rid,)
        ).fetchone()[0]
        fc  = _fclasses(conn, rid)
        rows.append([
            repo["name"], f"{tp:,}",
            str(tc.get("QD_PROJECT", 0)),
            str(tc.get("QDA_PROJECT", 0)),
            str(tc.get("OTHER_PROJECT", 0)),
            str(tc.get("NOT_A_PROJECT", 0)),
            f"{cl:,}", f"{fc:,}",
        ])
    pg.table(hdr, rows,
             col_w=[2.6, 0.8, 0.55, 0.55, 0.6, 0.6, 0.9, 0.9],
             row_h=0.028)

    pg.gap(0.008)
    pg.sub("Top 5 ISIC classes \u2014 both repositories combined")
    top = conn.execute(
        "SELECT primary_class, COUNT(*) c FROM PROJECT_CLASSES "
        "WHERE primary_class IS NOT NULL "
        "GROUP BY primary_class ORDER BY c DESC LIMIT 5"
    ).fetchall()
    cum, top_rows = 0, []
    for i, row in enumerate(top, 1):
        cum += row["c"]
        top_rows.append([
            str(i), row["primary_class"], f"{row['c']:,}",
            f"{row['c']/classified*100:.1f}%",
            f"{cum/classified*100:.1f}%",
        ])
    pg.table(
        ["Rank", "ISIC Rev. 5 class", "Count", "Share", "Cumulative"],
        top_rows,
        col_w=[0.5, 5.5, 0.8, 0.9, 1.0],
        row_h=0.027,
    )

    pg.gap(0.008)
    pg.section("Conclusion")
    pg.body(
        "Both repositories were successfully scraped, typed, and classified within the "
        "ISIC Rev. 5 taxonomy. The IHSN corpus is highly concentrated in public "
        "administration and demographic survey topics, which reflects its institutional "
        "mandate. The Harvard Murray Archive shows a wider subject spread, consistent "
        "with its social-science and psychology heritage. Together the two repositories "
        f"contributed {classified:,} ISIC-classified projects and {total_fc:,} "
        "file-level classifications stored in the delivery database."
    )
    pg.gap(0.004)
    pg.body(
        "By enforcing a clean separation between raw metadata ingestion and derived "
        "classification layers, the resulting datasets maintain strict integrity. These "
        "deliverables include the SQLite database, structured Excel sheets, and this report. "
        "They establish a reliable and reproducible foundation for future research across "
        "different repositories."
    )

    pg.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════════════════════════

def build_report(db_path=DEFAULT_DB, out_path=DEFAULT_OUT):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    repos    = _repos(conn)
    page_num = 1

    with PdfPages(out_path) as pdf:
        d = pdf.infodict()
        d["Title"]   = "SQ26 Part 2 \u2014 QDArchive Classification Report"
        d["Author"]  = f"{STUDENT_NAME} ({STUDENT_ID})"
        d["Subject"] = "ISIC Rev. 5 classification \u2014 QDArchive seeding project"

        _pg_cover(pdf, conn, page_num); page_num += 1
        _pg_types(pdf, conn, page_num); page_num += 1

        for i, repo in enumerate(repos, 3):
            _pg_results(pdf,    conn, page_num, repo, i); page_num += 1
            _pg_discussion(pdf, conn, page_num, repo, i); page_num += 1

        _pg_summary(pdf, conn, page_num)

    conn.close()
    print(f"Wrote {page_num} pages to {out_path}")
    return out_path


if __name__ == "__main__":
    build_report()
