# zenodo_config.py

ZENODO_API_BASE = "https://zenodo.org/api/records"

# Example query: looks for "qualitative" in the record
ZENODO_QUERY = "qualitative"

# Only retrieve *open* records (Zenodo facet)
ZENODO_ACCESS_RIGHT = "open"

# Page size – you can increase up to 200
ZENODO_PAGE_SIZE = 25

# QDA-related / relevant file extensions (extend as needed)
QDA_EXTENSIONS = [
    ".qdpx", ".qde", ".qdp",        # REFI/QDA
    ".nvp", ".nvpx",                # NVivo
    ".mx12", ".mx13", ".mx20",      # MaxQDA
    ".atlproj", ".atlproj9",        # ATLAS.ti
    ".qda", ".qdc", ".qd",         # generic QDA-like
]

# Primary data extensions (interviews, documents, etc.)
PRIMARY_EXTENSIONS = [".txt", ".rtf", ".doc", ".docx", ".pdf", ".odt"]

# Minimal open licenses you accept (you can refine)
OPEN_LICENSE_KEYS = [
    "cc-by", "cc-by-sa", "cc0", "cc-by-4.0", "cc-by-sa-4.0", "odc-by",
]

LOCAL_ROOT = "downloads/zenodo"
DB_PATH = "qdarchive_metadata.db"
