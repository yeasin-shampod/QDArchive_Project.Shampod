"""File-type knowledge used to derive the PROJECT_TYPE of a research project.

The categories follow the assignment definitions:

* **QDA file** (Analysis Data file) -- structured output of a qualitative data
  analysis tool (REFI-QDA ``.qdpx``, MAXQDA ``.mx``*, NVivo ``.nvp``/``.nvpx``,
  ATLAS.ti ``.atlproj``/``.hpr*``, Dedoose, Transana, ...).
* **Primary data file** -- the raw qualitative material a researcher analyses,
  e.g. interview transcripts or research articles (``txt``, ``pdf``, ``rtf``,
  ``docx`` and audio/video/image material).
* **Other valid data file** -- structured / statistical data that is neither a
  QDA file nor primary qualitative material (SPSS ``.sav``, Stata ``.dta``,
  spreadsheets, ``csv``, ``xml`` ...). A project that only contains such files
  is an ``OTHER_PROJECT``.

The mapping is intentionally generous: extension matching is case-insensitive.
"""

# ---------------------------------------------------------------------------
# QDA (Analysis Data) file extensions -- the REFI-QDA exchange format plus the
# native project formats of the common qualitative-analysis tools.
# ---------------------------------------------------------------------------
QDA_EXTENSIONS = {
    # REFI-QDA standard exchange format
    "qdpx", "qdp", "qde", "qdc",
    # MAXQDA
    "mx24", "mx22", "mx20", "mx18", "mx12", "mx5", "mx4", "mx3", "mx2", "mx",
    "mexproj",
    # NVivo
    "nvp", "nvpx", "nvc", "nvcx",
    # ATLAS.ti
    "atlproj", "atlas22", "hpr5", "hpr6", "hpr7", "hpr8", "hpr9",
    # Dedoose / QDA Miner / Transana / others
    "dedoose", "ppx", "wpj", "qdpx", "tams", "transana", "qcamap",
    "cat", "qsr", "n6",
}

# ---------------------------------------------------------------------------
# Primary (qualitative) data file extensions -- documents, transcripts and
# audio / video / image material.
# ---------------------------------------------------------------------------
PRIMARY_DATA_EXTENSIONS = {
    # text documents
    "pdf", "doc", "docx", "txt", "rtf", "odt", "md", "tex", "epub",
    "html", "htm", "xhtml", "pages", "wpd",
    # transcripts / captions
    "vtt", "srt", "trs", "cha", "eaf", "textgrid",
    # audio
    "mp3", "wav", "m4a", "aac", "flac", "ogg", "wma", "aiff",
    # video
    "mp4", "mov", "avi", "mkv", "wmv", "mpg", "mpeg", "m4v", "webm",
    # images (scanned documents, photographs used as qualitative material)
    "jpg", "jpeg", "png", "tif", "tiff", "gif", "bmp", "heic",
}

# ---------------------------------------------------------------------------
# Other valid (structured / statistical) data file extensions.
# ---------------------------------------------------------------------------
OTHER_VALID_DATA_EXTENSIONS = {
    # statistical packages
    "sav", "zsav", "por", "dta", "sas7bdat", "xpt", "sd2", "sd7", "sas",
    "sps", "do", "dct", "r", "rdata", "rds", "mat", "nlogo",
    # tabular / spreadsheets
    "csv", "tsv", "tab", "dat", "data", "xls", "xlsx", "xlsm", "ods",
    # databases / structured
    "mdb", "accdb", "dbf", "db", "sqlite", "json", "xml", "rdf", "nc", "h5",
    "parquet", "geojson", "shp", "kml",
    # archives that typically bundle data
    "zip", "tar", "gz", "7z", "rar",
}

# Files produced by *our own* scraping pipeline rather than by the researcher.
# They must not influence the PROJECT_TYPE derivation.
ARTIFACT_FILE_NAMES = {
    "metadata.json",
    "metadata_ddi.xml",
}


def get_extension(file_name):
    """Return the lowercase extension of *file_name* (without the dot).

    Returns an empty string when there is no usable extension.
    """
    if not file_name:
        return ""
    name = str(file_name).strip().lower()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[1]


def normalize_extension(file_name, file_type=None):
    """Best-effort extension for a FILES row.

    Prefers the extension embedded in ``file_name`` and falls back to the
    ``file_type`` column (which sometimes holds a bare extension or a MIME
    subtype such as ``x-spss-por``).
    """
    ext = get_extension(file_name)
    if ext:
        return ext
    if file_type:
        ft = str(file_type).strip().lower()
        ft = ft.split(";")[0].strip()           # drop "; charset=..."
        if "/" in ft:                            # a full MIME type
            ft = ft.split("/", 1)[1]
        ft = ft.replace("x-", "")
        return ft
    return ""


def is_artifact(file_name):
    """True when *file_name* is a pipeline artifact (our own metadata export)."""
    if not file_name:
        return False
    return str(file_name).strip().lower() in ARTIFACT_FILE_NAMES


def file_role(file_name, file_type=None):
    """Classify a single file into one of the four data roles.

    Returns one of ``"QDA"``, ``"PRIMARY"``, ``"OTHER"`` or ``"NONE"``.
    """
    if is_artifact(file_name):
        return "NONE"
    ext = normalize_extension(file_name, file_type)
    if not ext:
        return "NONE"
    if ext in QDA_EXTENSIONS:
        return "QDA"
    if ext in PRIMARY_DATA_EXTENSIONS:
        return "PRIMARY"
    if ext in OTHER_VALID_DATA_EXTENSIONS:
        return "OTHER"
    return "NONE"


def is_primary_data_file(file_name, file_type=None):
    """Convenience predicate: is this a primary (qualitative) data file?"""
    return file_role(file_name, file_type) == "PRIMARY"
