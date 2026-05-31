"""
Free company data enrichment using the Wikidata REST API (no API key needed).

For each unique company name we:
  1. Check a local on-disk cache first (company_cache.json).
  2. Search Wikidata for the company entity.
  3. Pull the P1128 claim (number of employees).
  4. Cache the result so the same company is never queried twice.

Well-known large companies (DAZN, Southwest Airlines, Adyen, ZF, Target, etc.)
all have Wikidata entries with employee counts → they get excluded correctly.
Small/unknown Indian companies usually have no Wikidata entry → they pass
through as "Unknown" (permissive, the right behaviour).
"""
import json
import time
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_FILE   = Path(__file__).parent / "company_cache.json"
WIKIDATA_URL = "https://www.wikidata.org/w/api.php"
UA           = "JobAgent/1.0 (daily job filter; contact: personal use)"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Wikidata lookup
# ---------------------------------------------------------------------------

def _search_entity(company_name: str) -> list[str]:
    """Return list of Wikidata entity IDs matching the company name."""
    try:
        r = requests.get(
            WIKIDATA_URL,
            params={
                "action":   "wbsearchentities",
                "search":   company_name,
                "language": "en",
                "type":     "item",
                "format":   "json",
                "limit":    3,
            },
            headers={"User-Agent": UA},
            timeout=8,
        )
        return [x["id"] for x in r.json().get("search", [])]
    except Exception:
        return []


def _get_employee_count(entity_id: str) -> int | None:
    """Return P1128 (employee count) for a Wikidata entity, or None."""
    try:
        r = requests.get(
            WIKIDATA_URL,
            params={
                "action": "wbgetentities",
                "ids":    entity_id,
                "props":  "claims",
                "format": "json",
            },
            headers={"User-Agent": UA},
            timeout=8,
        )
        claims = (
            r.json()
            .get("entities", {})
            .get(entity_id, {})
            .get("claims", {})
        )
        for claim in claims.get("P1128", []):
            try:
                raw = claim["mainsnak"]["datavalue"]["value"]["amount"]
                return int(float(str(raw).replace("+", "").replace(",", "")))
            except (KeyError, ValueError, TypeError):
                continue
    except Exception:
        pass
    return None


def lookup_employee_count(company_name: str, cache: dict) -> int | None:
    """
    Public entry point. Returns employee count or None.
    Mutates `cache` in-place; caller should persist with save_cache().
    """
    key = company_name.lower().strip()

    if key in cache:
        return cache[key]

    entity_ids = _search_entity(company_name)
    count = None
    for eid in entity_ids[:2]:
        count = _get_employee_count(eid)
        if count is not None:
            break
        time.sleep(0.25)

    cache[key] = count
    logger.debug(f"[Wikidata] {company_name!r} → {count} employees")
    return count
