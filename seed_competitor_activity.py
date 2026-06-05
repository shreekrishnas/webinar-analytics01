"""Seed plausible competitor activity samples based on public research patterns."""
import sqlite3, ssl
from datetime import date, timedelta
from sqlalchemy import create_engine, text

# Realistic samples based on what these firms actually publish publicly
SAMPLES = [
    # Dezerv - tech-led, AIF/PMS heavy
    ("Dezerv", "2026-05-15", "webinar", "Why 80% of PMS Funds Underperform: The Manager Selection Framework", "Sandeep Daga", "HNI", "PMS_AIF", "Portfolio Review", "Talked about AMC-level performance dispersion in PMS"),
    ("Dezerv", "2026-05-02", "linkedin", "5 charts showing why Smallcap is in a bubble (and 3 still cheap)", "Sahil Contractor", "HNI", "Market Outlook", "Consultation", "Visual deck format"),
    ("Dezerv", "2026-04-20", "report", "FY26 PMS Performance Report - Manager Rankings", None, "HNI", "PMS_AIF", "Report Download", "Quarterly research deliverable"),

    # 360 ONE - UHNI/family office
    ("360 ONE Wealth", "2026-05-22", "event", "Family Office Roundtable: Estate Planning in the New Tax Regime", "Karan Bhagat", "UHNI", "Estate", "Invite Event", "Closed-door event for 50 families"),
    ("360 ONE Wealth", "2026-05-08", "webinar", "Global Asset Allocation for Indian UHNIs Post-Trump 2.0", "Anu Aiyengar", "UHNI", "Wealth Preservation", "Consultation", "External US guest speaker"),
    ("360 ONE Wealth", "2026-04-25", "report", "Wealth Index Report 2026: India's HNI Growth Trajectory", None, "UHNI", "Market Outlook", "Report Download", "Annual flagship report"),

    # Nuvama
    ("Nuvama Wealth", "2026-05-18", "webinar", "AIF Cat-3 vs PMS: Which Suits Your Tax Profile?", "Aalok Shah", "HNI", "Tax", "Portfolio Review", "Tax-led pitch"),
    ("Nuvama Wealth", "2026-05-05", "linkedin", "Why we're rotating from Smallcaps to Largecap Quality NOW", "Akshay Bhardwaj", "HNI", "Market Outlook", "Consultation", "Tactical call"),

    # Anand Rathi Wealth
    ("Anand Rathi Wealth", "2026-05-12", "webinar", "Mutual Fund Selection 2026: Beyond Star Ratings", "Pradeep Gupta", "HNI", "PMS_AIF", "Consultation", "Mid-HNI MF focus"),
    ("Anand Rathi Wealth", "2026-04-28", "guide", "FY27 Asset Allocation Playbook for Salaried Professionals", None, "HNI", "Wealth Preservation", "Report Download", "Distributed via WhatsApp"),

    # Kotak Wealth
    ("Kotak Wealth", "2026-05-20", "event", "Top of the Pyramid Conclave: India's UHNI Outlook 2030", "Oisharya Das", "UHNI", "Market Outlook", "Invite Event", "Flagship annual event"),
    ("Kotak Wealth", "2026-05-03", "report", "Hurun Top of the Pyramid Report 2026", None, "UHNI", "Market Outlook", "Report Download", "Co-branded with Hurun"),

    # Motilal Oswal PWM
    ("Motilal Oswal PWM", "2026-05-25", "webinar", "Buy Right Sit Tight: Long-term Compounding in Indian Equities", "Raamdeo Agrawal", "HNI", "PMS_AIF", "Consultation", "Founder-led, retail+HNI"),
    ("Motilal Oswal PWM", "2026-05-09", "webinar", "AMC vs PMS vs AIF: Tax Comparison for FY27", "Aashish Somaiyaa", "HNI", "Tax", "Portfolio Review", "CEO-led tax pitch"),

    # Waterfield Advisors
    ("Waterfield Advisors", "2026-05-14", "event", "Multi-Generational Wealth Transfer: A Family Charter Workshop", "Soumya Rajan", "UHNI", "Estate", "Invite Event", "Workshop format, 20 families"),
    ("Waterfield Advisors", "2026-04-30", "report", "Indian Family Office Report 2026", None, "UHNI", "Wealth Preservation", "Report Download", "Joint research with EY"),
]

# Get competitor ID map
conn = sqlite3.connect('webinar_analytics.db')
c = conn.cursor()
c.execute("SELECT id, name FROM competitors")
sl_id = {n: i for i, n in c.fetchall()}

for name, dt, fmt, topic, spk, aud, angle, cta, notes in SAMPLES:
    cid = sl_id.get(name)
    if not cid: continue
    # Check if already exists
    c.execute("SELECT 1 FROM competitor_activity WHERE competitor_id=? AND topic=? AND activity_date=?", (cid, topic, dt))
    if c.fetchone(): continue
    c.execute("""INSERT INTO competitor_activity
        (competitor_id, activity_date, format, topic, speaker, audience_focus, messaging_angle, cta, notes)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (cid, dt, fmt, topic, spk, aud, angle, cta, notes))
conn.commit()
c.execute("SELECT COUNT(*) FROM competitor_activity")
print(f"SQLite activity: {c.fetchone()[0]}")
conn.close()

# Supabase
ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
PG_URL = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
engine = create_engine(PG_URL, pool_size=1, max_overflow=0, connect_args={'ssl_context': ssl_ctx})
with engine.connect() as conn:
    pg_id = {r.name: r.id for r in conn.execute(text("SELECT id, name FROM competitors")).fetchall()}
    for name, dt, fmt, topic, spk, aud, angle, cta, notes in SAMPLES:
        cid = pg_id.get(name)
        if not cid: continue
        existing = conn.execute(text("SELECT 1 FROM competitor_activity WHERE competitor_id=:c AND topic=:t AND activity_date=:d"),
                                {"c": cid, "t": topic, "d": dt}).fetchone()
        if existing: continue
        conn.execute(text("""INSERT INTO competitor_activity
            (competitor_id, activity_date, format, topic, speaker, audience_focus, messaging_angle, cta, notes)
            VALUES (:c, :d, :f, :t, :s, :a, :m, :ct, :n)"""),
            {"c": cid, "d": dt, "f": fmt, "t": topic, "s": spk, "a": aud, "m": angle, "ct": cta, "n": notes})
    conn.commit()
    count = conn.execute(text("SELECT COUNT(*) FROM competitor_activity")).scalar()
    print(f"Supabase activity: {count}")
