"""Create competitor + competitor_activity tables and seed the 7 competitors."""
import sqlite3, ssl
from sqlalchemy import create_engine, text

# 7 competitors per spec
COMPETITORS = [
    ("Dezerv",                 "Tech-led wealth platform, digital-first, AIF/PMS focus",                  "https://dezerv.in",                  "#6366F1"),
    ("360 ONE Wealth",         "Independent wealth firm, UHNI/HNI focus, family office services",         "https://360.one",                    "#0EA5E9"),
    ("Nuvama Wealth",          "Edelweiss spin-off, full-stack wealth, PMS/AIF/Distribution",             "https://www.nuvamawealth.com",       "#10B981"),
    ("Anand Rathi Wealth",     "Mid-HNI focus, mutual funds & wealth advisory",                          "https://www.rathi.com",              "#F59E0B"),
    ("Kotak Wealth",           "Bank-backed wealth, UHNI/HNI, family office",                            "https://www.kotak.com/en/private-banking", "#7C3AED"),
    ("Motilal Oswal PWM",      "Equity-focused PMS, retail+HNI, research-driven",                        "https://www.motilaloswalgroup.com",  "#DC2626"),
    ("Waterfield Advisors",    "Multi-family office, UHNI focus, full advisory",                         "https://waterfieldadvisors.com",     "#0891B2"),
]

# ── SQLite ────────────────────────────────────────────────────────────────────
conn = sqlite3.connect('webinar_analytics.db')
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    focus TEXT,
    website TEXT,
    color_hex TEXT DEFAULT '#6366F1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS competitor_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER REFERENCES competitors(id) ON DELETE CASCADE,
    activity_date DATE NOT NULL,
    format TEXT,                   -- webinar | linkedin | report | guide | event | other
    topic TEXT NOT NULL,
    speaker TEXT,
    audience_focus TEXT,           -- HNI | UHNI | CXO | Founder | Retiree | Doctor | NRI
    messaging_angle TEXT,          -- Retirement | Wealth Preservation | Market Outlook | Tax | Estate | PMS_AIF | Real Estate | etc
    cta TEXT,                      -- Consultation | Portfolio Review | Report Download | Invite Event
    link TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
c.execute("CREATE INDEX IF NOT EXISTS ix_competitor_activity_date ON competitor_activity(activity_date DESC)")
c.execute("CREATE INDEX IF NOT EXISTS ix_competitor_activity_comp ON competitor_activity(competitor_id)")

for n, f, w, color in COMPETITORS:
    try:
        c.execute("INSERT INTO competitors (name, focus, website, color_hex) VALUES (?,?,?,?)",
                  (n, f, w, color))
    except sqlite3.IntegrityError:
        pass
conn.commit()
c.execute("SELECT COUNT(*) FROM competitors")
print(f"SQLite competitors: {c.fetchone()[0]}")
conn.close()

# ── Supabase ──────────────────────────────────────────────────────────────────
ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
PG_URL = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
engine = create_engine(PG_URL, pool_size=1, max_overflow=0, connect_args={'ssl_context': ssl_ctx})
with engine.connect() as conn:
    conn.execute(text("""
CREATE TABLE IF NOT EXISTS competitors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    focus TEXT,
    website VARCHAR(255),
    color_hex VARCHAR(10) DEFAULT '#6366F1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""))
    conn.execute(text("""
CREATE TABLE IF NOT EXISTS competitor_activity (
    id SERIAL PRIMARY KEY,
    competitor_id INTEGER REFERENCES competitors(id) ON DELETE CASCADE,
    activity_date DATE NOT NULL,
    format VARCHAR(50),
    topic TEXT NOT NULL,
    speaker VARCHAR(150),
    audience_focus VARCHAR(50),
    messaging_angle VARCHAR(50),
    cta VARCHAR(100),
    link TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_competitor_activity_date ON competitor_activity(activity_date DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_competitor_activity_comp ON competitor_activity(competitor_id)"))
    for n, f, w, color in COMPETITORS:
        try:
            conn.execute(text("INSERT INTO competitors (name, focus, website, color_hex) VALUES (:n,:f,:w,:c) ON CONFLICT (name) DO NOTHING"),
                         {"n": n, "f": f, "w": w, "c": color})
        except Exception as e:
            print("Seed error:", e)
    conn.commit()
    count = conn.execute(text("SELECT COUNT(*) FROM competitors")).scalar()
    print(f"Supabase competitors: {count}")
