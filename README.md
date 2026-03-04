# Seeding QDArchive - Zenodo Scraper

This project implements a scraper for Zenodo to collect qualitative research data and QDA files for the QDArchive initiative.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the scraper:
   ```bash
   python zenodo_scraper.py
   ```

## Configuration

Edit `zenodo_config.py` to customize:
- Search terms
- File extensions to target
- License filters
- Local storage paths

## Output

- All downloaded files are stored in `downloads/zenodo/`
- Metadata is logged into `qdarchive_metadata.db`
