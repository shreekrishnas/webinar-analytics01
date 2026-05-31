"""
Three-stage filter pipeline:
  1. Date       — posted within the last 24 hours
  2. Industry   — exclude IT services / staffing / HR / consulting / BPO
  3. Size       — exclude companies with > 500 employees
                  (checked via blocklist → Wikidata enrichment → permissive fallback)
"""
import re
import logging
from datetime import datetime, timezone, timedelta

from config import (
    EXCLUDED_INDUSTRIES_EXACT,
    EXCLUDED_INDUSTRY_KEYWORDS,
    MAX_COMPANY_SIZE_LOWER_BOUND,
)
from company_enricher import lookup_employee_count, load_cache, save_cache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Date filter
# ---------------------------------------------------------------------------

def _is_within_24h(posted_at: str) -> bool:
    if not posted_at:
        return False  # strict: no timestamp = can't verify it's within 24h → drop

    try:
        ts = posted_at.strip()
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) <= timedelta(hours=24)
    except (ValueError, TypeError):
        pass

    s = posted_at.lower().strip()
    if re.search(r"just now|moment|second|minute", s):
        return True
    m = re.search(r"(\d+)\s*hour", s)
    if m:
        return int(m.group(1)) <= 24
    m = re.search(r"(\d+)\s*day", s)
    if m:
        return int(m.group(1)) <= 1
    if re.search(r"week|month", s):
        return False
    return True


# ---------------------------------------------------------------------------
# 2. Industry / company-type filter
# ---------------------------------------------------------------------------

# Confirmed large (>500 employees) or excluded-industry companies.
# All entries are lowercase for case-insensitive substring matching.
COMPANY_BLOCKLIST: set = {
    # === Indian IT Services (Tier 1 & 2) ===
    "tata consultancy services", "tcs",
    "infosys", "infosys bpm",
    "wipro", "wipro bps",
    "hcl technologies", "hcl tech", "hcl bserv",
    "tech mahindra",
    "cognizant", "cognizant technology solutions",
    "capgemini",
    "accenture",
    "ibm", "ibm india",
    "dxc technology",
    "unisys",
    "cgi", "cgi group",
    "ntt data",
    "fujitsu",
    "atos",
    "sopra steria",
    "hexaware", "hexaware technologies",
    "mphasis",
    "ltimindtree", "l&t infotech",
    "persistent systems",
    "cyient",
    "niit technologies",
    "zensar", "zensar technologies",
    "mastech", "mastech digital",
    "mindtree",
    "happiest minds",
    "birlasoft",
    "sonata software",
    "sasken",
    "kpit technologies",
    "virtusa",
    "syntel",
    "igate",
    "patni computer systems",
    "tata elxsi",
    "tata technologies",
    "tata advanced systems",
    "hcltech", "hcl software",
    "coforge", "mphasis bpo", "lti", "ltts",
    "oracle financial services",
    "oracle india",
    "sap labs india",
    "sap india",
    "hp", "hewlett packard", "hp enterprise", "hpe",
    "dell technologies", "dell india",
    "cisco systems india",
    "netcracker",
    "newgen software",
    "eclerx",
    "firstsource",
    # === Big 4 / Management Consulting ===
    "deloitte", "ey", "ernst & young", "kpmg", "pwc", "pricewaterhousecoopers",
    "mckinsey", "mckinsey & company",
    "bcg", "boston consulting group",
    "bain & company",
    "booz allen hamilton", "booz allen",
    "oliver wyman",
    "roland berger",
    "pa consulting",
    # === Staffing / Recruiting ===
    "teamlease", "teamlease services",
    "quess corp",
    "randstad", "randstad india",
    "manpowergroup", "manpower",
    "adecco",
    "kelly services",
    "allegis",
    "kforce",
    "robert half",
    "hays",
    "michael page",
    "spencer stuart",
    "korn ferry",
    "naukri", "info edge",
    "abc consultants",
    "ikya human capital",
    "mafoi",
    "global hunt",
    "3i infotech",
    # === BPO / GBS / Outsourcing ===
    "genpact",
    "wns global", "wns",
    "concentrix",
    "teleperformance",
    "conduent",
    "hinduja global",
    "serco",
    "ienergizer",
    "startek",
    "transcom",
    "sutherland global",
    "itouch",
    "intelenet",
    # === Cybersecurity / Networking Vendors (>500 employees) ===
    "palo alto networks", "palo alto networks professional services",
    "crowdstrike", "crowdstrike services",
    "mandiant",
    "secureworks",
    "fortinet",
    "juniper networks",
    "f5", "f5 networks",
    "check point software", "check point", "checkpoint software",
    "netscout",
    "solarwinds",
    # === Large Enterprise Software (>500 employees) ===
    "infor", "infor india",
    "splunk",
    "dynatrace",
    "datadog",
    "new relic",
    "elastic", "elastic nv",
    "hashicorp",
    "red hat", "red hat india",
    "suse",
    "canonical",
    # === Large Global Non-IT Companies (>500 employees) ===
    "southwest airlines",
    "dazn",
    "target", "target india",
    "cme group",
    "adyen", "adyen india",
    "thermo fisher scientific", "thermo fisher",
    "backbase",
    "quest global",
    "zf india", "zf group", "zf",
    "amazon", "amazon india", "amazon web services", "aws",
    "google", "google india", "alphabet",
    "microsoft", "microsoft india",
    "apple", "apple india",
    "meta", "meta india", "facebook",
    "netflix", "netflix india",
    "uber", "uber india",
    "salesforce", "salesforce india",
    "servicenow",
    "workday",
    "paypal", "paypal india",
    "stripe",
    "adobe", "adobe india",
    "intuit",
    "sap",
    "oracle",
    "vmware",
    "citrix",
    "twilio",
    "atlassian",
    "shopify",
    # === Large Indian Conglomerates / Banks ===
    "mahindra", "mahindra & mahindra", "tech mahindra",
    "bajaj", "bajaj finserv",
    "reliance", "reliance industries", "jio",
    "hdfc", "hdfc bank",
    "icici", "icici bank",
    "axis bank",
    "kotak", "kotak mahindra",
    "sbi", "state bank of india",
    # === Global Banks / Finance ===
    "jpmorgan", "jp morgan", "jpmorgan chase",
    "goldman sachs",
    "morgan stanley",
    "bank of america",
    "citibank", "citi", "citigroup",
    "deutsche bank",
    "barclays",
    "hsbc",
    "wells fargo",
    "ubs",
    "credit suisse",
    "standard chartered",
    # === Large Healthcare / Pharma ===
    "dr reddy's", "dr. reddy's",
    "sun pharma", "sun pharmaceutical",
    "cipla",
    "biocon",
    "lupin",
    "astrazeneca", "astrazeneca india",
    "johnson & johnson",
    "gsk", "glaxosmithkline",
    "novartis",
    "pfizer",
    "abbott",
    # === Large Engineering / Auto ===
    "bosch", "bosch india",
    "siemens", "siemens india",
    "ge", "general electric",
    "honeywell",
    "3m",
    "caterpillar",
    "l&t", "larsen & toubro", "larsen and toubro",
    "bhel",
}

# Substrings in company name that indicate excluded company type
EXCLUDED_NAME_SUBSTRINGS: list = [
    "staffing", "recruitment", "recruiting",
    "hr solutions", "hr services", "hr consulting",
    "it staffing", "it services", "it consulting",
    "outsourcing", "offshoring", "bpo",
    "manpower", "placement services",
    "talent solutions", "talent hunt",
    "executive search", "headhunting",
    "cyber security consulting", "security consulting",
    # Global Business Services / Shared Services / GBS operations
    "- gbs", "gbs india", "global business services",
    "shared services", "captive center",
]


def _is_excluded_by_type(company: str, industry: str) -> tuple[bool, str]:
    """
    Returns (should_exclude, reason).
    """
    company_lower = company.lower().strip()

    # Exact match
    if company_lower in COMPANY_BLOCKLIST:
        return True, f"blocklist-exact: {company}"

    # Partial / substring match against every blocklist entry
    for entry in COMPANY_BLOCKLIST:
        if len(entry) >= 4 and entry in company_lower:
            return True, f"blocklist-partial: {entry}"

    # Company name contains excluded keyword
    for kw in EXCLUDED_NAME_SUBSTRINGS:
        if kw in company_lower:
            return True, f"name-keyword: {kw}"

    # Industry field
    if industry:
        if industry in EXCLUDED_INDUSTRIES_EXACT:
            return True, f"industry-exact: {industry}"
        il = industry.lower()
        for kw in EXCLUDED_INDUSTRY_KEYWORDS:
            if kw in il:
                return True, f"industry-keyword: {kw}"

    return False, ""


# ---------------------------------------------------------------------------
# 3. Size filter (Wikidata enrichment)
# ---------------------------------------------------------------------------

def _check_size(company: str, cache: dict) -> tuple[str, int | None]:
    """
    Returns (verdict, employee_count).
    verdict: "pass" | "fail" | "unknown"
    """
    count = lookup_employee_count(company, cache)
    if count is None:
        return "unknown", None
    if count <= MAX_COMPANY_SIZE_LOWER_BOUND:
        return "pass", count
    return "fail", count


# ---------------------------------------------------------------------------
# Main filter class
# ---------------------------------------------------------------------------

class JobFilter:
    def filter(self, jobs: list) -> list:
        cache = load_cache()
        passed:  list = []
        dropped: int  = 0

        # Maps company name -> (verdict, count) to avoid re-querying Wikidata
        company_size_results: dict = {}

        for job in jobs:
            title    = job.get("title",    "")
            company  = job.get("company",  "")
            industry = job.get("industry", "")
            posted   = job.get("posted_at", "")

            # 1. Date
            if not _is_within_24h(posted):
                logger.info(f"  DROP(date)     {title} @ {company} | posted: {posted!r}")
                dropped += 1
                continue

            # 2. Industry / company type
            excluded, reason = _is_excluded_by_type(company, industry)
            if excluded:
                logger.info(f"  DROP(company)  {title} @ {company} [{reason}]")
                dropped += 1
                continue

            # 3. Company size via Wikidata
            if company and company not in company_size_results:
                company_size_results[company] = _check_size(company, cache)

            size_verdict, emp_count = company_size_results.get(company, ("unknown", None))

            if size_verdict == "fail":
                logger.info(f"  DROP(size)     {title} @ {company} [{emp_count:,} employees]")
                dropped += 1
                continue

            # Annotate job with enriched size info for Excel
            if emp_count is not None:
                job["company_size"] = f"~{emp_count:,}"
            else:
                job["company_size"] = "Verify manually"

            passed.append(job)

        save_cache(cache)
        logger.info(f"[Filter] {len(passed)} passed / {dropped} dropped / {len(jobs)} total")
        return passed
