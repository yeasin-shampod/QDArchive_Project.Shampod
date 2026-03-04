# Seeding QDArchive - Part 1: Data Acquisition

This project implements an automated pipeline to find, download, and document qualitative research data from **Zenodo** to seed the **QDArchive**.

## 🚀 Project Overview
This repository contains the source code for **Part 1** of the Seeding QDArchive project. The goal is to identify qualitative research projects, specifically looking for Analysis Data Files (QDA files) and Primary Data, ensuring all data follows open-access licenses.

## 📂 Project Structure
The project is organized following professional software engineering standards:

```text
seeding_qdarchive/
├── data/                       # Downloaded qualitative data (ignored by git)
│   └── zenodo/                 # Organized by Zenodo record ID
├── database/                   # Metadata storage
│   └── qdarchive_metadata.db   # SQLite database containing project metadata
├── logs/                       # Pipeline execution history
│   └── pipeline.log            # Detailed logs of downloads and skips
├── src/                        # Source code
│   ├── zenodo_config.py        # Configuration (API settings, file extensions)
│   ├── zenodo_scraper.py       # Main automated scraper script
│   └── fix_db_schema.py        # Database maintenance utility
├── .gitignore                  # Prevents large data files from being pushed
├── README.md                   # Project documentation
└── requirements.txt            # Python dependencies
```

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.10 or higher
- `pip` (Python package manager)

### 2. Install Dependencies
Clone the repository and install the required libraries:
```bash
git clone https://github.com/yeasin-shampod/QDArchive_Project.Shampod.git
cd QDArchive_Project.Shampod
pip install -r requirements.txt
```

## ⚙️ Running the Pipeline

To start the automated data acquisition process, run the main scraper script:

```bash
python src/zenodo_scraper.py
```

### What the pipeline does:
1. **Search**: Queries Zenodo for "qualitative" research records.
2. **Filter**: Automatically filters for **Open Access** licenses.
3. **Classify**: Identifies files as `analysis_qda` (e.g., .qdpx, .nvp) or `primary_data`.
4. **Download**: Saves files into structured folders under `data/zenodo/`.
5. **Log**: Records all metadata (DOI, Author, License, etc.) into the SQLite database.

## 📊 Metadata Database
The metadata is stored in `database/qdarchive_metadata.db`. You can inspect it using any SQLite viewer. Key fields include:
- `source_url`: Link to the original Zenodo record.
- `license`: Verified open license (e.g., CC-BY).
- `file_type`: Classification of the file (Analysis vs Primary).

## 📝 Submission Details
- **Tag**: `part-1-release`
- **Deadline**: March 15, 2026
- **Author**: Shampod

---
*Developed for the Seeding QDArchive Project.*
