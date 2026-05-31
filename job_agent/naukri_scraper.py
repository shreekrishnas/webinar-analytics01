"""
Naukri.com scraper — India's largest job portal.
Approach:
  1. Try the internal JSON API (with browser-like AJAX headers).
  2. If that returns 406/403, fall back to scraping the HTML search page
     and extracting the embedded __NEXT_DATA__ JSON.
No API key required.
"""
import re
import json
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SEARCH_API_URL = "https://www.naukri.com/jobapi/v3/search"

API_HEADERS = {
    "User-Agent":        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept":            "application/json, text/javascript, */*; q=0.01",
    "Accept-Language":   "en-US,en;q=0.9",
    "Accept-Encoding":   "gzip, deflate, br",
    "X-Requested-With":  "XMLHttpRequest",
    "Connection":        "keep-alive",
    "Referer":           "https://www.naukri.com/",
    "appid":             "109",
    "systemid":          "109",
    "gid":               "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
}

HTML_HEADERS = {
    "User-Agent":        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept":            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":   "en-US,en;q=0.9",
    "Accept-Encoding":   "gzip, deflate, br",
    "Connection":        "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Role → Naukri URL slug
ROLE_SLUGS = {
    "DevOps Engineer":           "devops-engineer",
    "Site Reliability Engineer": "site-reliability-engineer",
    "IT Admin":                  "it-admin",
    "IT Administrator":          "it-administrator",
    "System Engineer":           "system-engineer",
    "System Administrator":      "system-administrator",
    "Network Engineer":          "network-engineer",
    "Lead Engineer":             "lead-engineer",
}

LOCATION_SLUGS = {
    "Hyderabad": "hyderabad",
    "Bangalore":  "bangalore",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _epoch_to_iso(epoch) -> str | None:
    try:
        dt = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        return None


def _normalise(item: dict, search_loc: str) -> dict:
    title   = item.get("title") or item.get("jobTitle", "")
    company = item.get("companyName") or item.get("company", "")

    epoch = item.get("date") or item.get("createdDate") or item.get("modifiedDate")
    posted_iso = _epoch_to_iso(epoch) if epoch else ""

    jd_url = item.get("jdURL") or item.get("jobDetailsUrl", "")
    if jd_url and not jd_url.startswith("http"):
        jd_url = "https://www.naukri.com" + jd_url

    # Location from placeholders list
    placeholders = item.get("placeholders", [])
    loc_parts = [p.get("label", "") for p in placeholders if p.get("type") == "location"]
    location_str = ", ".join(loc_parts) if loc_parts else search_loc

    industry_list = item.get("industryTypes", [])
    industry = industry_list[0] if industry_list else ""

    return {
        "source":       "Naukri",
        "title":        title,
        "company":      company,
        "location":     location_str,
        "industry":     industry,
        "company_size": "",
        "posted_at":    posted_iso,
        "job_url":      jd_url,
        "_description": (item.get("jobDescription", "") or "")[:600],
    }


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class NaukriScraper:
    def __init__(self):
        self.session = requests.Session()
        self._cookies_loaded = False

    def _prime_session(self):
        """Load Naukri homepage once to pick up required session cookies."""
        if self._cookies_loaded:
            return
        try:
            self.session.get("https://www.naukri.com/", headers=HTML_HEADERS, timeout=15)
            logger.debug("[Naukri] Session cookies set")
        except Exception:
            pass
        self._cookies_loaded = True

    # ------------------------------------------------------------------
    # Approach 1: JSON API
    # ------------------------------------------------------------------
    def _try_api(self, keyword: str, location: str) -> list | None:
        params = {
            "noOfResults":  "50",
            "urlType":      "search_by_key_loc",
            "searchType":   "adv",
            "keyword":      keyword,
            "location":     LOCATION_SLUGS.get(location, location.lower()),
            "jobAge":       "1",
            "src":          "jobsearchDesk",
            "latLong":      "",
            "pageNo":       "1",
            "searchId":     "",
        }
        self._prime_session()
        try:
            resp = self.session.get(
                SEARCH_API_URL, params=params,
                headers=API_HEADERS, timeout=20,
            )
            if resp.status_code in (406, 403, 401):
                return None   # signal: fall back to HTML
            resp.raise_for_status()
            data = resp.json()
            return data.get("jobDetails", data.get("jobs", []))
        except Exception as exc:
            logger.debug(f"[Naukri API] {keyword}/{location}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Approach 2: HTML page → __NEXT_DATA__ JSON
    # ------------------------------------------------------------------
    def _try_html(self, keyword: str, location: str) -> list:
        role_slug = ROLE_SLUGS.get(keyword, keyword.lower().replace(" ", "-"))
        loc_slug  = LOCATION_SLUGS.get(location, location.lower())
        url       = f"https://www.naukri.com/{role_slug}-jobs-in-{loc_slug}?jobAge=1&noOfResults=50"

        try:
            resp = self.session.get(url, headers=HTML_HEADERS, timeout=25)
            resp.raise_for_status()
            return self._parse_next_data(resp.text)
        except Exception as exc:
            logger.debug(f"[Naukri HTML] {keyword}/{location}: {exc}")
            return []

    @staticmethod
    def _parse_next_data(html: str) -> list:
        """Extract job listings from Next.js __NEXT_DATA__ embedded JSON."""
        match = re.search(
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>\s*(\{.*?\})\s*</script>',
            html, re.DOTALL,
        )
        if not match:
            return []

        try:
            root  = json.loads(match.group(1))
            props = root.get("props", {}).get("pageProps", {})

            # Different Naukri page versions use different keys
            for key in ("jobList", "jobDetails"):
                if props.get(key):
                    return props[key]

            # Nested under searchResultList
            srl = props.get("searchResultList") or {}
            if srl.get("jobDetails"):
                return srl["jobDetails"]

            # Nested under initialDataJSON
            idj = props.get("initialDataJSON") or {}
            return idj.get("jobDetails", [])

        except (json.JSONDecodeError, AttributeError):
            return []

    # ------------------------------------------------------------------
    # Per-role search
    # ------------------------------------------------------------------
    def search_jobs(self, keyword: str, location: str) -> list:
        # Try API first
        items = self._try_api(keyword, location)

        if items is None:
            # API blocked → fall back to HTML
            items = self._try_html(keyword, location)

        if items is None:
            items = []

        logger.info(f"[Naukri] {keyword} / {location} -> {len(items)} results")
        return [_normalise(j, location) for j in items]

    # ------------------------------------------------------------------
    # Bulk entry point
    # ------------------------------------------------------------------
    def scrape_all(self, job_roles: list, locations: list, **_) -> list:
        all_items: list = []

        for location in locations:
            for role in job_roles:
                all_items.extend(self.search_jobs(role, location))
                time.sleep(1.5)

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

        logger.info(f"[Naukri] {len(unique)} unique jobs after deduplication")
        return unique
