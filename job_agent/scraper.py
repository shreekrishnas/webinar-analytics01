"""
JSearch (RapidAPI) scraper — aggregates LinkedIn, Indeed, Glassdoor and more.
No LinkedIn / Indeed platform API key needed; only a free RapidAPI account.

Free tier: 200 requests/month.
We batch all roles into 2 queries per location → 4 requests/day × 30 = 120/month.
"""
import time
import logging
import requests

logger = logging.getLogger(__name__)

JSEARCH_URL  = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"

# Two balanced batches so query strings stay short
ROLE_BATCHES = [
    ["DevOps Engineer", "Site Reliability Engineer", "IT Admin", "IT Administrator"],
    ["System Engineer", "System Administrator", "Network Engineer", "Lead Engineer"],
]


class JobScraper:
    def __init__(self, api_key: str):
        self.headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": JSEARCH_HOST,
        }

    def scrape_all(self, job_roles: list, locations: list, **_) -> list:
        all_items: list = []

        for location in locations:
            for batch in ROLE_BATCHES:
                roles_q = " OR ".join(f'"{r}"' for r in batch)
                query   = f'({roles_q}) {location} India'

                logger.info(f"[JSearch] {query[:90]}...")
                items = self._fetch(query)
                logger.info(f"[JSearch] {len(items)} results for {location} / batch")
                all_items.extend(items)
                time.sleep(1.2)   # stay within rate limits

        # Deduplicate by job URL
        seen:   set  = set()
        unique: list = []
        for job in all_items:
            url = job.get("job_url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(job)
            elif not url:
                unique.append(job)

        logger.info(f"[Scraper] {len(unique)} unique jobs after deduplication")
        return unique

    def _fetch(self, query: str, pages: int = 2) -> list:
        results = []
        for page in range(1, pages + 1):
            try:
                resp = requests.get(
                    JSEARCH_URL,
                    headers=self.headers,
                    params={
                        "query":       query,
                        "date_posted": "3days",   # cast wide net; strict 24h filter applied locally
                        "num_pages":   "1",
                        "page":        str(page),
                        "country":     "IN",
                        "language":    "en",
                    },
                    timeout=40,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") != "OK":
                    logger.warning(f"[JSearch] status={data.get('status')} — stopping pagination")
                    break

                batch = data.get("data", [])
                if not batch:
                    break

                results.extend(self._normalise(i) for i in batch)

            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    logger.warning("[JSearch] Rate-limited. Waiting 30 s…")
                    time.sleep(30)
                else:
                    logger.error(f"[JSearch] HTTP error (page {page}): {exc}")
                break
            except requests.exceptions.RequestException as exc:
                logger.error(f"[JSearch] Request failed (page {page}): {exc}")
                break

        return results

    @staticmethod
    def _normalise(item: dict) -> dict:
        city     = item.get("job_city")  or ""
        state    = item.get("job_state") or ""
        location = ", ".join(part for part in [city, state] if part)

        return {
            "source":        item.get("job_source", "JSearch"),
            "title":         item.get("job_title", ""),
            "company":       item.get("employer_name", ""),
            "location":      location,
            "industry":      item.get("employer_company_type") or "",
            "company_size":  "",   # JSearch does not expose this field
            "posted_at":     item.get("job_posted_at_datetime_utc", ""),
            "job_url":       item.get("job_apply_link") or item.get("job_google_link", ""),
            "_description":  (item.get("job_description") or "")[:600],
        }
