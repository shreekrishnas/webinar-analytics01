"""Add co_speaker_id to webinars and assign Vijay Chauhan to all Prabhat Ranjan joint webinars."""
import sqlite3, ssl
from sqlalchemy import create_engine, text

# Webinar dates where Vijay Chauhan co-presents with Prabhat Ranjan (from CSV)
VIJAY_DATES = [
    '2024-09-02',  # Uncovering Investment Opportunities
    '2024-12-14',  # Spotlighting Super Value: SMIDs
    '2025-04-19',  # Investment Landscape FY-2026
    '2025-07-05',  # Sectoral Investment Opportunities
    '2025-09-20',  # Market Opportunities, Themes
    '2025-12-06',  # Market Outlook 2026
    '2026-04-04',  # Portfolio Positioning for FY27
]

# ── SQLite ────────────────────────────────────────────────────────────────────
conn = sqlite3.connect('webinar_analytics.db')
c = conn.cursor()

# Add co_speaker_id column
try:
    c.execute("ALTER TABLE webinars ADD COLUMN co_speaker_id INTEGER REFERENCES speakers(id)")
    print('Added co_speaker_id to SQLite')
except sqlite3.OperationalError:
    print('co_speaker_id already exists in SQLite')

# Get Vijay Chauhan's speaker ID
c.execute("SELECT id, name FROM speakers WHERE name LIKE '%Vijay%'")
vijay = c.fetchone()
if not vijay:
    # Create him
    c.execute("INSERT INTO speakers (name, email, bio) VALUES ('Vijay Chauhan', 'vijay.chauhan@righthorizons.com', 'Head of Equity Research, Right Horizons. 20 years on Dalal Street covering mid/small caps.')")
    vijay_id = c.lastrowid
    print(f'Created Vijay Chauhan with id={vijay_id}')
else:
    vijay_id = vijay[0]
    print(f'Found Vijay Chauhan: id={vijay_id}, name={vijay[1]}')

# Update co_speaker for joint webinars
updated = 0
for date in VIJAY_DATES:
    c.execute("UPDATE webinars SET co_speaker_id=? WHERE date=?", (vijay_id, date))
    updated += c.rowcount
    print(f'  {date}: set co_speaker_id={vijay_id} ({c.rowcount} rows)')

conn.commit()
c.execute("SELECT COUNT(*) FROM webinars WHERE co_speaker_id=?", (vijay_id,))
print(f'Total webinars with Vijay as co-speaker: {c.fetchone()[0]}')
conn.close()

# ── Supabase ──────────────────────────────────────────────────────────────────
print('\nUpdating Supabase...')
ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
PG_URL = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
engine = create_engine(PG_URL, pool_size=1, max_overflow=0, connect_args={'ssl_context':ssl_ctx})

with engine.connect() as conn:
    # Add column
    try:
        conn.execute(text("ALTER TABLE webinars ADD COLUMN co_speaker_id INTEGER REFERENCES speakers(id)"))
        conn.commit()
        print('Added co_speaker_id to Supabase')
    except Exception as e:
        if 'already exists' in str(e).lower():
            print('co_speaker_id already exists')
        else:
            print('Column error:', e)

    # Get Vijay's ID in Supabase
    row = conn.execute(text("SELECT id FROM speakers WHERE name LIKE '%Vijay%'")).fetchone()
    if row:
        vijay_pg_id = row[0]
        print(f'Vijay Chauhan in Supabase: id={vijay_pg_id}')
    else:
        conn.execute(text("INSERT INTO speakers (name,email,bio) VALUES ('Vijay Chauhan','vijay.chauhan@righthorizons.com','Head of Equity Research, Right Horizons. 20 years on Dalal Street covering mid/small caps.')"))
        conn.commit()
        vijay_pg_id = conn.execute(text("SELECT id FROM speakers WHERE name='Vijay Chauhan'")).fetchone()[0]
        print(f'Created Vijay Chauhan: id={vijay_pg_id}')

    for date in VIJAY_DATES:
        r = conn.execute(text("UPDATE webinars SET co_speaker_id=:vid WHERE date=:d"), {'vid': vijay_pg_id, 'd': date})
        print(f'  {date}: {r.rowcount} rows updated')
    conn.commit()

    cnt = conn.execute(text("SELECT COUNT(*) FROM webinars WHERE co_speaker_id=:v"), {'v': vijay_pg_id}).scalar()
    print(f'Supabase: {cnt} webinars have Vijay as co-speaker')

print('\nDone!')
