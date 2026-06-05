"""Load campaign data from the RH CSV into webinars table."""
import csv, sqlite3, ssl, re
from sqlalchemy import create_engine, text
from datetime import datetime

CSV_PATH = r"C:\Users\shree\Downloads\RH_Reporting_FY26-27 - Webinar Highlights.csv"

def parse_num(s):
    if not s or s.strip() == '': return None
    cleaned = re.sub(r'[^0-9.]', '', str(s).replace(',', ''))
    try: return float(cleaned) if '.' in cleaned else int(cleaned)
    except: return None

def parse_date(s):
    if not s: return None
    s = s.strip()
    for fmt in ('%d-%b-%Y', '%d-%b-%y', '%Y-%m-%d'):
        try: return datetime.strptime(s, fmt).date()
        except: pass
    return None

# Parse CSV
rows = []
with open(CSV_PATH, encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        d = parse_date(r.get('Date', ''))
        if not d: continue
        rows.append({
            'date': str(d),
            'campaigns': parse_num(r.get('No. Campaign')),
            'spend': parse_num(r.get('Total Spend')),
            'leads': parse_num(r.get('Total FB Leads Generated')),
            'cpl': parse_num(r.get('Cost per Lead')),
            'impressions': parse_num(r.get('Total Impression')),
            'clicks': parse_num(r.get('Total Clicks')),
            'duration_days': r.get('Campaign duration', '').strip(),
        })
print(f'Parsed {len(rows)} rows from CSV')

# ── Update DBs ────────────────────────────────────────────────────────────────
def update_db(execute_fn, alter_sql, update_sql):
    for col_def in alter_sql:
        try: execute_fn(col_def)
        except Exception as e:
            if 'duplicate' not in str(e).lower() and 'already exists' not in str(e).lower():
                print('alter error:', e)
    for r in rows:
        try:
            execute_fn(update_sql, {
                'd': r['date'], 'c': r['campaigns'], 's': r['spend'], 'l': r['leads'],
                'p': r['cpl'], 'i': r['impressions'], 'k': r['clicks'], 'u': r['duration_days']
            })
        except Exception as e:
            print(f'Update error for {r["date"]}:', e)

# SQLite
conn = sqlite3.connect('webinar_analytics.db')
c = conn.cursor()
def sqlite_exec(sql, params=None):
    if params: c.execute(sql, params)
    else: c.execute(sql)
update_db(sqlite_exec, [
    "ALTER TABLE webinars ADD COLUMN campaigns INTEGER",
    "ALTER TABLE webinars ADD COLUMN spend REAL",
    "ALTER TABLE webinars ADD COLUMN leads INTEGER",
    "ALTER TABLE webinars ADD COLUMN cpl REAL",
    "ALTER TABLE webinars ADD COLUMN impressions INTEGER",
    "ALTER TABLE webinars ADD COLUMN clicks INTEGER",
    "ALTER TABLE webinars ADD COLUMN campaign_duration TEXT",
],
"UPDATE webinars SET campaigns=:c, spend=:s, leads=:l, cpl=:p, impressions=:i, clicks=:k, campaign_duration=:u WHERE date=:d")
conn.commit()
c.execute("SELECT COUNT(*) FROM webinars WHERE spend IS NOT NULL")
print(f'SQLite: {c.fetchone()[0]} webinars have campaign data')
conn.close()

# Supabase
ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
PG_URL = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
engine = create_engine(PG_URL, pool_size=1, max_overflow=0, connect_args={'ssl_context': ssl_ctx})
with engine.connect() as conn:
    def pg_exec(sql, params=None):
        if params: conn.execute(text(sql), params)
        else: conn.execute(text(sql))
    update_db(pg_exec, [
        "ALTER TABLE webinars ADD COLUMN IF NOT EXISTS campaigns INTEGER",
        "ALTER TABLE webinars ADD COLUMN IF NOT EXISTS spend NUMERIC",
        "ALTER TABLE webinars ADD COLUMN IF NOT EXISTS leads INTEGER",
        "ALTER TABLE webinars ADD COLUMN IF NOT EXISTS cpl NUMERIC",
        "ALTER TABLE webinars ADD COLUMN IF NOT EXISTS impressions INTEGER",
        "ALTER TABLE webinars ADD COLUMN IF NOT EXISTS clicks INTEGER",
        "ALTER TABLE webinars ADD COLUMN IF NOT EXISTS campaign_duration VARCHAR(50)",
    ],
    "UPDATE webinars SET campaigns=:c, spend=:s, leads=:l, cpl=:p, impressions=:i, clicks=:k, campaign_duration=:u WHERE date=:d")
    conn.commit()
    count = conn.execute(text("SELECT COUNT(*) FROM webinars WHERE spend IS NOT NULL")).scalar()
    print(f'Supabase: {count} webinars have campaign data')
