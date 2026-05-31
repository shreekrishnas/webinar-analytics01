"""
Adzuna Job Search API scraper — free tier (1,000 calls/day).
Covers India job boards, returns structured data with accurate posted timestamps.
Sign up free at: https://developer.adzuna.com/
"""
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search/{page}"   # 'in' = India

LOCATION_ALIASES = {
    "Hyderabad": "Hyderabad",
    "Bangalore":  "Bangalore",
}

# Role keywords for Adzuna's `what` parameter.
# Simple keywords work reliably; Adzuna matches them in title + description.
ROLE_KEYWORDS = [
    "DevOps",
    "Site Reliability Engineer",
    "IT Admin",
    "IT Administrator",
    "System Engineer",
    "System Administrator",
    "Network Engineer",
    "Lead Engineer",
]


class AdzunaScraper:
    def __init__(self, app_id: str, app_key: str):
        self.app_id  = app_id
        self.app_key = app_key

    def _fetch(self, keyword: str, location: str, page: int = 1) -> list:
        """Single page fetch. Page number goes in the URL path only."""
        params = {
            "app_id":           self.app_id,
            "app_key":          self.app_key,
            "results_per_page": 50,
            "what":             keyword,
            "where":            location,
            "max_days_old":     1,
            "sort_by":          "date",
        }
        try:
            resp = requests.get(
                BASE_URL.format(page=page),
                params=params,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.debug(
                f"[Adzuna] {keyword}/{location} p{page}: "
                f"total={data.get('count','?')} returned={len(data.get('results',[]))}"
            )
            return data.get("results", [])
        except Exception as exc:
            logger.error(f"[Adzuna] {keyword}/{location} page {page}: {exc}")
            return []

    def search_jobs(self, keyword: str, location: str) -> list:
        items = self._fetch(keyword, location, page=1)
        if len(items) == 50:                          # full page → fetch page 2
            items += self._fetch(keyword, location, page=2)
            time.sleep(0.4)
        logger.info(f"[Adzuna] {keyword}/{location} -> {len(items)} results")
        return [self._normalise(i) for i in items]

    @staticmethod
    def _normalise(item: dict) -> dict:
        company  = (item.get("company")  or {}).get("display_name", "")
        location = (item.get("location") or {}).get("display_name", "")

        created = item.get("created", "")
        posted  = ""
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                posted = dt.isoformat()
            except (ValueError, TypeError):
                posted = created

        return {
            "source":       "Adzuna",
            "title":        item.get("title", ""),
            "company":      company,
            "location":     location,
            "industry":     (item.get("category") or {}).get("label", ""),
            "company_size": "",
            "posted_at":    posted,
            "job_url":      item.get("redirect_url", ""),
            "_description": (item.get("description") or "")[:600],
        }

    def scrape_all(self, job_roles: list, locations: list, **_) -> list:
        """
        One query per role per location.
        8 roles × 2 locations = 16 calls/day — well within 1,000/day free limit.
        """
        all_items: list = []

        for location in locations:
            loc = LOCATION_ALIASES.get(location, location)
            for keyword in ROLE_KEYWORDS:
                all_items.extend(self.search_jobs(keyword, loc))
                time.sleep(0.8)

        # Deduplicate by URL
        seen:   set  = set()
        unique: list = []
        for job in all_items:
            url = job.get("job_url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(job)
            elif not url:
                unique.append(job)

        logger.info(f"[Adzuna] {len(unique)} unique jobs after deduplication")
        return unique
