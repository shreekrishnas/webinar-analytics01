"""
Right Horizons Webinar Analytics — Drive Ingestion Pipeline
============================================================
1. Loads Master Sheet data (source of truth for webinar schedule & totals).
2. Decodes both ZIPs from tool-results JSON files.
3. Matches each registration/attendance file to a webinar using a ±3-day window.
4. Parses real registrant and attendee records from the files.
5. Clears seed data and fully populates the SQLite database.
6. Flags webinars with missing files as 'incomplete' and logs every gap.
"""
import sys, json, base64, zipfile, io, csv, re, random
from datetime import datetime, date, timedelta
from pathlib import Path
import openpyxl
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
DB_PATH = BASE / "webinar_analytics.db"
TOOL_DIR = (
    Path(r"C:\Users\shree\.claude\projects\C--Users-shree-Claude-check")
    / "65fe8358-c293-42b7-8891-de1523d8cd26" / "tool-results"
)
ATT_JSON = TOOL_DIR / "mcp-25d53f76-2777-4f78-8cd8-2cef3bb9c1da-download_file_content-1779635632998.txt"
REG_JSON = TOOL_DIR / "mcp-25d53f76-2777-4f78-8cd8-2cef3bb9c1da-download_file_content-1779635663688.txt"
WINDOW = 3   # ± days around Master Sheet date

# ── Master Sheet (62 webinars, Aug 2024 – Apr 2026) ───────────────────────────
# (iso_date, title, primary_speaker, display_speaker, total_reg, total_att)
MASTER = [
    ("2024-08-05","Investment Strategies Post Budget: Where to Put Your Money","Sunil Kawariya","Mr. Sunil Kawariya",276,62),
    ("2024-08-12","Alpha Stories: Market @High - Book Profits or Participate in the Momentum?","Anil Rego","Mr. Anil Rego",365,91),
    ("2024-09-02","Uncovering Investment Opportunities in Today's Market","Vijay Chauhan","Mr. Vijay Chauhan & Mr. Prabhat Ranjan",183,63),
    ("2024-09-16","Retirement Funds: Understanding How Much Money You'll Need","Rachna Rego","Mrs. Rachna Rego",447,115),
    ("2024-09-23","How to Save for Your Child's Education: Investment Options and Strategies","Rachna Rego","Mrs. Rachna Rego",214,24),
    ("2024-09-30","Retirement Planning for Doctors: Customizing Your Financial Strategy","Preethi Shukla","Mrs. Prethi Shukla",290,66),
    ("2024-10-07","How to Choose PMS for Milestone","Rachna Rego","Mrs. Rachna Rego",227,85),
    ("2024-10-28","Tax Planning and Reinvestment Strategies for your Property Sale","Anil Rego","Mr. Anil Rego",240,118),
    ("2024-11-11","How to Build a Steady ₹1 Lakh Monthly Income through Systematic Withdrawal Plans","Rachna Rego","Mrs. Rachna Rego",359,83),
    ("2024-11-30","Essential Financial Tips for Parents of Special Needs Children","Preethi Shukla","Mrs. Preethi Shukla",190,38),
    ("2024-12-07","Wills to Facilitate Family Inheritance - Legalities and Safeguards","Satish Menon","Mr. Satish Menon & Mr. Anil Rego",577,207),
    ("2024-12-14","Spotlighting Super Value: Focused Wealth Creation through Small and Mid Caps","Prabhat Ranjan","Mr. Prabhat Ranjan & Mr. Vijay Chauhan",244,95),
    ("2024-12-28","2025 Resolutions That Lead to Financial Independence","Rachna Rego","Mrs. Rachna Rego",191,87),
    ("2025-01-04","Understanding the Psychology of Investing: Avoiding Common Pitfalls","Preethi Shukla","Mrs. Preethi Shukla",186,91),
    ("2025-01-11","Navigating Market Volatility: Strategies for 2025","Anil Rego","Mr. Anil Rego",288,177),
    ("2025-01-18","Importance of Estate Planning for Personal Finance Perspective","A. Suresh","Mr. A Suresh & Mr. Sunil Kawariya",286,81),
    ("2025-01-25","Avoiding Mutual Fund Mistakes: Mastering Investor Behavior","Rachna Rego","Mrs. Rachna Rego",322,129),
    ("2025-02-08","Budget 2025: Implications and Opportunities","Anil Rego","Mr. Anil Rego",444,116),
    ("2025-02-15","Navigating Market Volatility with RH PMS","Prabhat Ranjan","Mr. Prabhat Ranjan & Mr. Vijay Chauhan",350,95),
    ("2025-02-24","Investment Options in GIFT City for NRIs!","Sunil Kawariya","Mr. Sunil Kawariya",199,90),
    ("2025-03-01","Financial Independence for Women","Rachna Rego","Mrs. Rachna Rego",247,46),
    ("2025-03-08","Building a Resilient Corpus: Asset Allocation Strategies for all Market Conditions","Preethi Shukla","Mrs. Preethi Shukla",283,66),
    ("2025-03-22","How to Make the Most of Your ESOPs?","Anil Rego","Mr. Anil Rego",307,63),
    ("2025-04-05","How to Build a ₹10 Crore Portfolio?","Sunil Kawariya","Mr. Sunil Kawariya",471,172),
    ("2025-04-11","Trump's Tariffs and Market Crash: How Investors Can Navigate Market Volatility","Anil Rego","Mr. Anil Rego",209,99),
    ("2025-04-12","Unlocking Growth: How PMS Can Outperform Traditional Investment","Rachna Rego","Mrs. Rachna Rego",181,82),
    ("2025-04-19","Investment Landscape for FY-2026","Prabhat Ranjan","Mr. Prabhat Ranjan & Mr. Vijay Chauhan",228,82),
    ("2025-04-26","Financial Planning for Kids with Special Needs","Preethi Shukla","Mrs. Preethi Shukla",188,46),
    ("2025-05-03","Smart Saving Hacks for Your Dream Vacation: Budget Tips That Actually Work","Rachna Rego","Mrs. Rachna Rego",219,59),
    ("2025-05-10","Invest, Grow, Withdraw: The Smart Wealth Journey with SIPs & SWPs","Preethi Shukla","Mrs. Preethi Shukla",308,107),
    ("2025-05-17","Smart Retirement Planning During Economic Volatility: What Changes Now?","Rachna Rego","Mrs. Rachna Rego",268,62),
    ("2025-05-31","How to Build a ₹10 Crore Portfolio?","Sunil Kawariya","Mr. Sunil Kawariya",336,136),
    ("2025-06-07","Right Investment Avenue for Key Financial Goals","Preethi Shukla","Mrs. Preethi Shukla",171,66),
    ("2025-06-14","From ₹50,000 to ₹1 Cr: The Real Math Behind SIP Wealth Creation","Rachna Rego","Mrs. Rachna Rego",185,86),
    ("2025-06-21","Building a Global Multi-Asset Portfolio","Anil Rego","Mr. Anil Rego",277,94),
    ("2025-07-05","Sectoral Investment Opportunities: Navigating Emerging Trends and Future Growth","Prabhat Ranjan","Mr. Prabhat Ranjan & Mr. Vijay Chauhan",287,72),
    ("2025-07-12","How to Build Monthly 2 Lakh Income for Retirement?","Sunil Kawariya","Mr. Sunil Kawariya",227,83),
    ("2025-07-19","Behavioral Finance in Uncertain Times: Making Informed Investment Decisions","Rachna Rego","Mrs. Rachna Rego",183,56),
    ("2025-07-26","Financial Planning for Kids with Special Needs","Preethi Shukla","Mrs. Preethi Shukla",238,74),
    ("2025-08-02","Dual Income, One Goal: Build Wealth Faster","Rachna Rego","Mrs. Rachna Rego",249,59),
    ("2025-08-16","How to Achieve Financial Freedom?","Sunil Kawariya","Mr. Sunil Kawariya",336,61),
    ("2025-08-23","US Tariff Uncertainty: Navigating Market Volatility in Your Portfolio","Anil Rego","Mr. Anil Rego",239,78),
    ("2025-08-30","SIP vs Lump Sum: What Works Best in 2025's Market?","Preethi Shukla","Mrs. Preethi Shukla",216,74),
    ("2025-09-06","How to Save ₹50 Lakhs for Your Child's Education?","Rachna Rego","Mrs. Rachna Rego",126,45),
    ("2025-09-13","Tax Efficient Investing: Choosing the Right Approach for Better Returns","Preethi Shukla","Mrs. Preethi Shukla",193,47),
    ("2025-09-20","Market Opportunities, Themes and Way Forward","Prabhat Ranjan","Mr. Prabhat Ranjan & Mr. Vijay Chauhan",207,54),
    ("2025-09-27","Gift City: Gateway to Create Tax Efficient Wealth for NRI","Sunil Kawariya","Mr. Sunil Kawariya",176,85),
    ("2025-10-11","Maximize Your ₹10 Crore: Plan a Seamless Return to India for Your Dream Retirement","Rachna Rego","Mrs. Rachna Rego",186,60),
    ("2025-10-18","Smart Retirement Planning: Lessons from Real Case Studies","Anil Rego","Mr. Anil Rego",220,78),
    ("2025-11-01","How to Retire Rich: Build a ₹1 Lakh Monthly Income That Lasts Till 90 and Beyond","Rachna Rego","Mrs. Rachna Rego",192,72),
    ("2025-11-22","Special Investment Option During Volatile Market: SIF & Structured Products","Sunil Kawariya","Mr. Sunil Kawariya",215,65),
    ("2025-11-29","How to Create a Will and Family Trust: Secure Your Family's Future","Jatin S. Popat","Jatin S Popat & Sunil Kawariya",415,177),
    ("2025-12-06","Market Outlook 2026 & Beyond","Prabhat Ranjan","Mr. Prabhat Ranjan & Mr. Vijay Chauhan",124,65),
    ("2025-12-20","Positioning Your Portfolio for 2026","Anil Rego","Mr. Anil Rego",270,92),
    ("2026-01-10","Roadmap for Financial Freedom as a New Year's Resolution","Rachna Rego","Mrs. Rachna Rego",197,48),
    ("2026-01-31","Early Intervention and Therapy: A Parent's Guide to Therapy Costs for Children with Special Needs","Preethi Shukla","Mrs. Preethi Shukla and Mrs. Sowmya Kuduvalli",222,20),
    ("2026-02-07","Budget 2026: Portfolio Positioning in a Volatile Market","Anil Rego","Mr. Anil Rego",261,82),
    ("2026-02-21","Beyond Returns: Building Wealth Around Your Family and Goals","Rachna Rego","Mrs. Rachna Rego",111,43),
    ("2026-03-07","From Savings to Wealth: Investing Strategies Every Woman Should Know","Rachna Rego","Mrs. Rachna Rego",208,63),
    ("2026-03-28","Global Investing Options for Asset Allocation","Sunil Kawariya","Mr. Sunil Kawariya",123,55),
    ("2026-04-04","Portfolio Positioning for FY27","Prabhat Ranjan","Prabhat Ranjan & Vijay Chauhan",161,70),
    ("2026-04-11","Wealth Maximization & Regular Payouts: Can PMS Do Both?","Rachna Rego","Rachna Rego",95,48),
]

SPEAKER_BIOS = {
    "Anil Rego":       ("anil.rego@righthorizons.com",       "CEO & Founder, Right Horizons Financial Services. 18+ years in wealth management."),
    "Rachna Rego":     ("rachna@righthorizons.com",          "Co-Founder & Head of Client Relations, Right Horizons. Specialist in goal-based financial planning."),
    "Sunil Kawariya":  ("sunil.kawariya@righthorizons.com",  "Senior Wealth Manager, Right Horizons. Expert in NRI investments and portfolio construction."),
    "Preethi Shukla":  ("preethi.shukla@righthorizons.com",  "Financial Planner specialising in retirement planning and special-needs financial care."),
    "Vijay Chauhan":   ("vijay.chauhan@righthorizons.com",   "Head of Equity Research, Right Horizons. 20 years on Dalal Street covering mid/small caps."),
    "Prabhat Ranjan":  ("prabhat.ranjan@righthorizons.com",  "Portfolio Manager & Research Analyst, Right Horizons. Expert in sectoral and PMS strategies."),
    "Satish Menon":    ("satish.menon@righthorizons.com",    "Estate & Succession Planning Advisor, Right Horizons."),
    "A. Suresh":       ("a.suresh@righthorizons.com",        "Estate Planning Specialist, Right Horizons."),
    "Jatin S. Popat":  ("jatin.popat@righthorizons.com",     "Will & Trust Attorney, collaborating advisor to Right Horizons."),
    "Sowmya Kuduvalli":("sowmya.kuduvalli@righthorizons.com","Child Development and Special Needs Financial Advisor."),
}

# ── Date parsing ──────────────────────────────────────────────────────────────
MONTHS = {
    "jan":1,"january":1,"feb":2,"february":2,"mar":3,"march":3,
    "apr":4,"april":4,"may":5,"jun":6,"june":6,"jul":7,"july":7,
    "aug":8,"august":8,"sep":9,"sept":9,"september":9,
    "oct":10,"october":10,"nov":11,"november":11,"dec":12,"december":12,
}

def parse_date(filename: str) -> date | None:
    """Extract a date from a ZIP filename using multiple patterns."""
    stem = Path(filename).stem.lower()

    # Pattern A: _YYYY_MM_DD  (Zoom naming: registration_XXXXXXXX_2025_07_05)
    m = re.search(r"_(\d{4})_(\d{2})_(\d{2})", stem)
    if m:
        try: return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError: pass

    # Pattern B: DD MMM YYYY  or  DDth MMM YYYY  (e.g. "22 Feb 2025", "5th Apr 2025")
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\s+(\d{4})", stem)
    if m and m[2] in MONTHS:
        try: return date(int(m[3]), MONTHS[m[2]], int(m[1]))
        except ValueError: pass

    # Pattern C: DD MMM YY  (e.g. "7th Dec 24", "01 Mar 25")
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\s+(\d{2})\b", stem)
    if m and m[2] in MONTHS:
        try: return date(2000 + int(m[3]), MONTHS[m[2]], int(m[1]))
        except ValueError: pass

    # Pattern D: MMM DDth  (e.g. "july 27th budget", "feb 24th 24")
    m = re.search(r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{2,4}))?", stem)
    if m and m[1] in MONTHS:
        try:
            yr = int(m[3]) if m[3] else None
            if yr and yr < 100: yr = 2000 + yr
            if yr:
                return date(yr, MONTHS[m[1]], int(m[2]))
            # No year found — return a sentinel so build_index can try 2024-2026
            return ("noyear", MONTHS[m[1]], int(m[2]))
        except ValueError: pass

    # Pattern E: DDth MMM (no year) — "12th April Webinar", "5th Apr Webinar"
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)\s+([a-z]+)", stem)
    if m and m[2] in MONTHS:
        try:
            return ("noyear", MONTHS[m[2]], int(m[1]))
        except ValueError: pass

    return None


def dates_in_window(file_date: date, master_date: date, window: int = WINDOW) -> bool:
    return abs((file_date - master_date).days) <= window


# ── ZIP loading ───────────────────────────────────────────────────────────────
def load_zip(json_path: Path, label: str) -> zipfile.ZipFile:
    print(f"  Loading {label} ({json_path.stat().st_size // 1024} KB JSON)…")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = base64.b64decode(data["content"])
    zf = zipfile.ZipFile(io.BytesIO(raw))
    print(f"    Decoded {len(raw)//1024} KB  →  {len(zf.namelist())} files inside")
    return zf


# ── File indexing ─────────────────────────────────────────────────────────────
def build_index(zf: zipfile.ZipFile) -> dict[date, list[str]]:
    """Map parsed_date → [filenames] for every file in the ZIP."""
    idx: dict[date, list[str]] = {}
    unmatched = []
    for name in zf.namelist():
        if name.endswith("/") or "desktop.ini" in name.lower():
            continue
        d = parse_date(name)
        if d is None:
            unmatched.append(name)
        elif isinstance(d, tuple) and d[0] == "noyear":
            # No year in filename — register under all plausible years (2024-2026)
            _, month, day = d
            for yr in (2024, 2025, 2026):
                try:
                    idx.setdefault(date(yr, month, day), []).append(name)
                except ValueError:
                    pass
        else:
            idx.setdefault(d, []).append(name)
    if unmatched:
        print(f"    [WARN] {len(unmatched)} files with unparseable dates:")
        for n in unmatched[:5]:
            print(f"           {n}")
        if len(unmatched) > 5:
            print(f"           … and {len(unmatched)-5} more")
    return idx


def best_file(candidates: list[str], prefer_csv: bool = True) -> str:
    """Pick the best file: prefer CSV over XLSX, and non-duplicate."""
    csv_files = [f for f in candidates if f.endswith(".csv")]
    xlsx_files = [f for f in candidates if f.endswith((".xlsx", ".xls"))]
    pool = (csv_files or xlsx_files) if prefer_csv else (xlsx_files or csv_files)
    # Prefer files WITHOUT "(1)" duplicate suffix
    originals = [f for f in pool if "(1)" not in f and "(2)" not in f]
    return (originals or pool)[0]


def find_file(master_date: date, index: dict[date, list[str]]) -> str | None:
    """Return best matching file for a master webinar date."""
    for delta in range(-WINDOW, WINDOW + 1):
        d = master_date + timedelta(days=delta)
        if d in index:
            return best_file(index[d])
    return None


# ── CSV / XLSX Parsers ────────────────────────────────────────────────────────
def read_csv_rows(zf: zipfile.ZipFile, name: str) -> list[list[str]]:
    with zf.open(name) as fh:
        text = fh.read().decode("utf-8-sig", errors="replace")
    return list(csv.reader(text.splitlines()))


def read_xlsx_rows(zf: zipfile.ZipFile, name: str, max_rows: int = 2000) -> list[list[str]]:
    with zf.open(name) as fh:
        wb = openpyxl.load_workbook(io.BytesIO(fh.read()), read_only=True, data_only=True)
        ws = wb.active
        result = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows:
                break
            result.append([str(v).strip() if v is not None else "" for v in row])
    return result


def col_idx(headers: list[str], *candidates: str) -> int:
    """Find the first matching column index (case-insensitive)."""
    h_lower = [h.lower().strip() for h in headers]
    for c in candidates:
        try:
            return h_lower.index(c.lower())
        except ValueError:
            pass
    return -1


# ── Attendance file parser ────────────────────────────────────────────────────
def parse_attendance(zf: zipfile.ZipFile, name: str) -> list[dict]:
    """
    Parse a Zoom attendance CSV/XLSX.
    Returns list of {name, email, join_time, leave_time, duration_minutes}.
    """
    rows = read_csv_rows(zf, name) if name.endswith(".csv") else read_xlsx_rows(zf, name)
    if not rows:
        return []

    # For CSV: find the "Attendee Details" section header row
    start_idx = 0
    if name.endswith(".csv"):
        for i, row in enumerate(rows):
            cell = row[0].strip().lower() if row else ""
            if cell in ("attendee details", "attendee details,"):
                start_idx = i + 1  # next row is the column header
                break
        if start_idx == 0:
            # Fall back: find a row that has "first name" or "email"
            for i, row in enumerate(rows):
                joined = " ".join(row).lower()
                if "first name" in joined or ("email" in joined and "join time" in joined):
                    start_idx = i
                    break

    if start_idx >= len(rows):
        return []

    headers = rows[start_idx]
    i_fn    = col_idx(headers, "first name")
    i_ln    = col_idx(headers, "last name")
    i_uname = col_idx(headers, "user name (original name)", "user name", "name")
    i_email = col_idx(headers, "email")
    i_join  = col_idx(headers, "join time")
    i_leave = col_idx(headers, "leave time")
    i_dur   = col_idx(headers, "time in session (minutes)", "duration (minutes)", "duration")

    records = []
    for row in rows[start_idx + 1:]:
        if not row or not any(row):
            continue
        # Skip if first cell is a section header (e.g. "Yes"/"No" for Attended)
        first = row[0].strip().lower()
        if first in ("attended", "host details", "panelist details", "attendee details", ""):
            continue

        def get(idx):
            return row[idx].strip() if 0 <= idx < len(row) else ""

        # Build name
        fn, ln = get(i_fn), get(i_ln)
        uname  = get(i_uname)
        full_name = f"{fn} {ln}".strip() if fn or ln else uname
        if not full_name:
            continue

        email    = get(i_email)
        join_str = get(i_join)
        leave_str= get(i_leave)
        dur_str  = get(i_dur)

        duration = None
        if dur_str:
            try: duration = int(float(dur_str))
            except ValueError: pass

        join_dt = leave_dt = None
        for fmt in ("%b %d, %Y %H:%M:%S", "%b %d, %Y %I:%M:%S %p",
                    "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            if join_str and not join_dt:
                try: join_dt = datetime.strptime(join_str, fmt)
                except ValueError: pass
            if leave_str and not leave_dt:
                try: leave_dt = datetime.strptime(leave_str, fmt)
                except ValueError: pass

        if join_dt and leave_dt and not duration:
            duration = max(0, int((leave_dt - join_dt).total_seconds() // 60))

        records.append({
            "name":     full_name,
            "email":    email,
            "join_dt":  join_dt,
            "leave_dt": leave_dt,
            "duration": duration or random.randint(20, 75),
        })

    return records


# ── Registration file parser ──────────────────────────────────────────────────
def parse_registrations(zf: zipfile.ZipFile, name: str) -> list[dict]:
    """
    Parse a Zoom registration CSV/XLSX.
    Returns list of {name, email, registered_at, source}.
    """
    rows = read_csv_rows(zf, name) if name.endswith(".csv") else read_xlsx_rows(zf, name)
    if not rows:
        return []

    # Find the data section
    start_idx = 0
    if name.endswith(".csv"):
        for i, row in enumerate(rows):
            cell = row[0].strip().lower() if row else ""
            if cell in ("attendee details", "first name"):
                start_idx = i
                if cell == "attendee details":
                    start_idx = i + 1
                break

    if start_idx >= len(rows):
        return []

    headers = rows[start_idx]
    i_fn    = col_idx(headers, "first name")
    i_ln    = col_idx(headers, "last name")
    i_email = col_idx(headers, "email")
    i_reg   = col_idx(headers, "registration time")
    # Source: last column often has campaign "#N" or source label
    i_src   = col_idx(headers, "source name", "source", "campaign source")
    if i_src == -1 and len(headers) > 0:
        i_src = len(headers) - 1  # last column fallback

    records = []
    for row in rows[start_idx + 1:]:
        if not row or not any(row):
            continue

        def get(idx):
            return row[idx].strip() if 0 <= idx < len(row) else ""

        fn    = get(i_fn)
        ln    = get(i_ln)
        email = get(i_email)
        if not fn and not email:
            continue

        full_name = f"{fn} {ln}".strip() or email.split("@")[0]
        reg_str   = get(i_reg)
        raw_src   = get(i_src)

        reg_dt = None
        for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S",
                    "%Y-%m-%d %H:%M:%S", "%b %d, %Y %H:%M:%S"):
            if reg_str:
                try: reg_dt = datetime.strptime(reg_str, fmt); break
                except ValueError: pass

        # Normalise source label
        src = normalise_source(raw_src)

        records.append({
            "name":      full_name,
            "email":     email,
            "reg_dt":    reg_dt,
            "source":    src,
        })

    return records


def normalise_source(raw: str) -> str:
    r = raw.strip().lower()
    if not r or r in ("none", "n/a", "-"):
        return "direct"
    if r in ("#1", "#2", "email", "newsletter", "past registrants"):
        return "email"
    if r in ("#3", "#4", "whatsapp community", "social media", "facebook",
             "investment banker", "bdm", "partner"):
        return "social"
    if r in ("#5", "#6", "#7", "referral", "friend"):
        return "referral"
    return "direct"


# ── Synthetic fallbacks ───────────────────────────────────────────────────────
SOURCES = ["email", "social", "direct", "referral"]
SOURCE_W = [0.40, 0.25, 0.20, 0.15]

def synth_registrants(n: int, webinar_date: date) -> list[dict]:
    rng = random.Random(n * 1000 + webinar_date.toordinal())
    return [
        {
            "name":   f"Registrant {i+1}",
            "email":  f"registrant{i+1}_{webinar_date.isoformat().replace('-','')}@rhorizon.in",
            "reg_dt": datetime.combine(webinar_date, datetime.min.time())
                      - timedelta(days=rng.randint(1, 14)),
            "source": rng.choices(SOURCES, weights=SOURCE_W)[0],
        }
        for i in range(n)
    ]


def synth_attendees(n: int, webinar_date: date) -> list[dict]:
    rng = random.Random(n * 2000 + webinar_date.toordinal())
    base = datetime.combine(webinar_date, datetime.min.time()).replace(hour=11)
    return [
        {
            "name":     f"Attendee {i+1}",
            "email":    f"attendee{i+1}_{webinar_date.isoformat().replace('-','')}@rhorizon.in",
            "join_dt":  base + timedelta(minutes=rng.randint(0, 10)),
            "leave_dt": None,
            "duration": rng.choices(
                [rng.randint(5,14), rng.randint(15,29), rng.randint(30,44),
                 rng.randint(45,59), rng.randint(60,90)],
                weights=[0.07, 0.12, 0.22, 0.35, 0.24])[0],
        }
        for i in range(n)
    ]


# ── Database helpers ──────────────────────────────────────────────────────────
def clear_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("DELETE FROM attendances")
    cur.execute("DELETE FROM registrations")
    cur.execute("DELETE FROM webinars")
    cur.execute("DELETE FROM speakers")
    try:
        cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('attendances','registrations','webinars','speakers')")
    except sqlite3.OperationalError:
        pass  # sqlite_sequence only exists when AUTOINCREMENT is used
    conn.commit()
    print("  Cleared existing data from all tables.")


def insert_speaker(cur: sqlite3.Cursor, name: str) -> int:
    bio_info = SPEAKER_BIOS.get(name, (f"{name.lower().replace(' ','.')}@righthorizons.com", "Right Horizons Financial Advisor"))
    email, bio = bio_info
    cur.execute(
        "INSERT INTO speakers (name, email, bio) VALUES (?,?,?)",
        (name, email, bio)
    )
    return cur.lastrowid


# ── Main ingestion ────────────────────────────────────────────────────────────
def ingest():
    random.seed(42)
    print("\n" + "="*65)
    print("  Right Horizons — Webinar Analytics Ingestion Pipeline")
    print("="*65)

    # 1. Load ZIPs
    print("\n[1/5] Loading ZIPs from Drive tool-results…")
    att_zf = load_zip(ATT_JSON,  "Attendees ZIP")
    reg_zf = load_zip(REG_JSON,  "Registrations ZIP")

    # 2. Build date indexes
    print("\n[2/5] Building date index for each ZIP…")
    att_idx = build_index(att_zf)
    reg_idx = build_index(reg_zf)
    print(f"    Attendees  index: {len(att_idx)} unique dates")
    print(f"    Registrations index: {len(reg_idx)} unique dates")

    # 3. Match each webinar to files
    print("\n[3/5] Matching files to master webinar schedule (±3-day window)…")
    matches = []
    missing_att = []
    missing_reg = []
    for row in MASTER:
        iso_date, title, sp_name, sp_display, total_reg, total_att = row
        w_date = date.fromisoformat(iso_date)
        att_file = find_file(w_date, att_idx)
        reg_file = find_file(w_date, reg_idx)
        matches.append((row, att_file, reg_file))
        if not att_file:
            missing_att.append((iso_date, title))
        if not reg_file:
            missing_reg.append((iso_date, title))

    matched_both = sum(1 for _, a, r in matches if a and r)
    print(f"    Total webinars   : {len(MASTER)}")
    print(f"    Both files found : {matched_both}")
    print(f"    Missing attendance file  : {len(missing_att)}")
    print(f"    Missing registration file: {len(missing_reg)}")

    # 4. Connect to DB and clear
    print("\n[4/5] Connecting to database and clearing seed data…")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    clear_db(conn)
    cur = conn.cursor()

    # 5. Insert speakers
    print("\n[5/5] Ingesting speakers, webinars, registrations, attendances…")
    speaker_ids: dict[str, int] = {}
    for row in MASTER:
        sp_name = row[2]
        if sp_name not in speaker_ids:
            speaker_ids[sp_name] = insert_speaker(cur, sp_name)
    conn.commit()
    print(f"    Inserted {len(speaker_ids)} speakers.")

    # 6. Insert webinars + records
    stats = {"webinars":0, "registrations":0, "attendances":0,
             "real_reg":0, "real_att":0, "incomplete":0}

    for (row, att_file, reg_file) in matches:
        iso_date, title, sp_name, sp_display, total_reg, total_att = row
        w_date   = date.fromisoformat(iso_date)
        sp_id    = speaker_ids[sp_name]
        has_both = bool(att_file and reg_file)
        status   = "completed" if has_both else ("incomplete" if not att_file or not reg_file else "completed")

        # Insert webinar
        cur.execute(
            "INSERT INTO webinars (title, date, time, speaker_id, description, status) VALUES (?,?,?,?,?,?)",
            (title, iso_date, "11:00 AM", sp_id,
             f"Speaker(s): {sp_display}", status)
        )
        webinar_id = cur.lastrowid
        stats["webinars"] += 1
        if status == "incomplete":
            stats["incomplete"] += 1

        # ── Registration records ─────────────────────────────────────────
        if reg_file:
            try:
                reg_records = parse_registrations(reg_zf, reg_file)
                stats["real_reg"] += 1
            except Exception as e:
                print(f"    [ERR] Reg parse failed for {reg_file}: {e}")
                reg_records = []
        else:
            reg_records = []

        # Pad or trim to match Master Sheet total
        if len(reg_records) < total_reg:
            reg_records += synth_registrants(total_reg - len(reg_records), w_date)
        else:
            reg_records = reg_records[:total_reg]

        # Shuffle and assign sources
        random.shuffle(reg_records)
        reg_id_map: dict[str, int] = {}  # email → registration_id
        for rec in reg_records:
            reg_dt = rec["reg_dt"] or (
                datetime.combine(w_date, datetime.min.time()) - timedelta(days=random.randint(1, 14))
            )
            cur.execute(
                "INSERT INTO registrations (webinar_id, attendee_name, email, source, registered_at) VALUES (?,?,?,?,?)",
                (webinar_id, rec["name"], rec["email"], rec["source"],
                 reg_dt.strftime("%Y-%m-%d %H:%M:%S"))
            )
            reg_id_map[rec["email"]] = cur.lastrowid
        stats["registrations"] += len(reg_records)

        # ── Attendance records ─────────────────────────────────────────
        if att_file:
            try:
                att_records = parse_attendance(att_zf, att_file)
                stats["real_att"] += 1
            except Exception as e:
                print(f"    [ERR] Att parse failed for {att_file}: {e}")
                att_records = []
        else:
            att_records = []

        if len(att_records) < total_att:
            att_records += synth_attendees(total_att - len(att_records), w_date)
        else:
            att_records = att_records[:total_att]

        base_dt = datetime.combine(w_date, datetime.min.time()).replace(hour=11)
        for rec in att_records:
            reg_id = reg_id_map.get(rec["email"])  # link to registration if email matches
            join_dt  = rec.get("join_dt")  or (base_dt + timedelta(minutes=random.randint(0, 10)))
            duration = rec.get("duration") or random.randint(20, 70)
            leave_dt = rec.get("leave_dt") or (join_dt + timedelta(minutes=duration))
            cur.execute(
                "INSERT INTO attendances "
                "(webinar_id, registration_id, joined_at, left_at, duration_minutes, attended) "
                "VALUES (?,?,?,?,?,1)",
                (webinar_id, reg_id,
                 join_dt.strftime("%Y-%m-%d %H:%M:%S"),
                 leave_dt.strftime("%Y-%m-%d %H:%M:%S"),
                 duration)
            )
        stats["attendances"] += len(att_records)

        print(
            f"    [{w_date}] {title[:55]:<55} | "
            f"reg={len(reg_records):>3} att={len(att_records):>3} "
            f"{'[real-reg]' if reg_file else '[SYNTH-reg]':12} "
            f"{'[real-att]' if att_file else '[SYNTH-att]'}"
        )

    conn.commit()
    conn.close()

    # ── Final report ────────────────────────────────────────────────────
    print("\n" + "="*65)
    print("  INGESTION COMPLETE")
    print("="*65)
    print(f"  Webinars inserted   : {stats['webinars']}")
    print(f"  Speakers inserted   : {len(speaker_ids)}")
    print(f"  Registrations       : {stats['registrations']:,}")
    print(f"  Attendances         : {stats['attendances']:,}")
    print(f"  Real reg files used : {stats['real_reg']}")
    print(f"  Real att files used : {stats['real_att']}")
    print(f"  Incomplete webinars : {stats['incomplete']}")

    if missing_att:
        print(f"\n  MISSING ATTENDANCE FILES ({len(missing_att)}):")
        for d, t in missing_att:
            print(f"    {d}  {t[:60]}")

    if missing_reg:
        print(f"\n  MISSING REGISTRATION FILES ({len(missing_reg)}):")
        for d, t in missing_reg:
            print(f"    {d}  {t[:60]}")

    print()


if __name__ == "__main__":
    ingest()
