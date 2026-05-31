"""
Job Agent — main entry point.

Sources (combined, all free):
  1. Adzuna API    — India job boards, accurate 24h filter  (primary)
  2. JSearch API   — LinkedIn / Indeed / Glassdoor aggregate (secondary)

Usage:
    python main.py
    python main.py --no-adzuna     # skip Adzuna
    python main.py --no-jsearch    # skip JSearch
"""
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from config          import JOB_ROLES, LOCATIONS
from adzuna_scraper  import AdzunaScraper
from scraper         import JobScraper
from filters         import JobFilter
from exporter        import export as export_excel

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            log_dir / f"run_{datetime.now().strftime('%Y-%m-%d')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Daily Job Agent")
    parser.add_argument("--no-adzuna",  action="store_true", help="Skip Adzuna")
    parser.add_argument("--no-jsearch", action="store_true", help="Skip JSearch")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Job Agent started")
    logger.info(f"Run time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Roles    : {', '.join(JOB_ROLES)}")
    logger.info(f"Locations: {', '.join(LOCATIONS)}")
    logger.info("=" * 60)

    raw_jobs: list = []

    # 1a. Adzuna — primary India source
    if not args.no_adzuna:
        adzuna_id  = os.getenv("ADZUNA_APP_ID",  "").strip()
        adzuna_key = os.getenv("ADZUNA_APP_KEY", "").strip()
        if adzuna_id and adzuna_key:
            logger.info("[Source] Adzuna ...")
            adzuna_jobs = AdzunaScraper(adzuna_id, adzuna_key).scrape_all(JOB_ROLES, LOCATIONS)
            logger.info(f"[Adzuna] {len(adzuna_jobs)} jobs collected")
            raw_jobs.extend(adzuna_jobs)
        else:
            logger.warning("ADZUNA_APP_ID / ADZUNA_APP_KEY not set — skipping Adzuna")

    # 1b. JSearch — secondary (LinkedIn + Indeed + Glassdoor)
    if not args.no_jsearch:
        rapidapi_key = os.getenv("RAPIDAPI_KEY", "").strip()
        if rapidapi_key:
            logger.info("[Source] JSearch ...")
            jsearch_jobs = JobScraper(rapidapi_key).scrape_all(JOB_ROLES, LOCATIONS)
            logger.info(f"[JSearch] {len(jsearch_jobs)} jobs collected")
            raw_jobs.extend(jsearch_jobs)
        else:
            logger.warning("RAPIDAPI_KEY not set — skipping JSearch")

    # Deduplicate across all sources by URL
    seen:   set  = set()
    unique: list = []
    for job in raw_jobs:
        url = job.get("job_url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(job)
        elif not url:
            unique.append(job)

    logger.info(f"Total raw jobs (all sources, deduplicated): {len(unique)}")

    # 2. Filter
    filtered_jobs = JobFilter().filter(unique)

    # 3. Export
    output_dir = os.getenv("OUTPUT_DIR", str(Path(__file__).parent / "output"))
    filepath   = export_excel(filtered_jobs, output_dir)

    logger.info("=" * 60)
    logger.info(f"Done -- {len(filtered_jobs)} jobs saved to {filepath}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
