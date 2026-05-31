"""Add ICP column to webinars and update all 62 webinars from CSV data."""
import csv, sqlite3, sys, io, ssl
sys.stdout.reconfigure(encoding='utf-8')

# ICP mapping by date (from the CSV, normalized)
ICP_BY_DATE = {
    '2024-08-05': 'Others',
    '2024-08-12': 'PMS',
    '2024-09-02': 'PMS',
    '2024-09-16': 'Retirement Planning',
    '2024-09-23': 'Others',
    '2024-09-30': 'Retirement Planning',
    '2024-10-07': 'PMS',
    '2024-10-28': 'Others',
    '2024-11-11': 'Others',
    '2024-11-30': 'Others',
    '2024-12-07': 'Others',
    '2024-12-14': 'PMS',
    '2024-12-28': 'Others',
    '2025-01-04': 'Others',
    '2025-01-11': 'PMS',
    '2025-01-18': 'Others',
    '2025-01-25': 'Others',
    '2025-02-08': 'Others',
    '2025-02-15': 'PMS',
    '2025-02-24': 'NRI',
    '2025-03-01': 'Others',
    '2025-03-08': 'Others',
    '2025-03-22': 'ESOPs',
    '2025-04-05': 'PMS',
    '2025-04-11': 'PMS',
    '2025-04-12': 'PMS',
    '2025-04-19': 'Others',
    '2025-04-26': 'Others',
    '2025-05-03': 'Others',
    '2025-05-10': 'Others',
    '2025-05-17': 'Retirement Planning',
    '2025-05-31': 'PMS',
    '2025-06-07': 'Others',
    '2025-06-14': 'Others',
    '2025-06-21': 'PMS',
    '2025-07-05': 'Others',
    '2025-07-12': 'Retirement Planning',
    '2025-07-19': 'Others',
    '2025-07-26': 'Others',
    '2025-08-02': 'Others',
    '2025-08-16': 'Others',
    '2025-08-23': 'Others',
    '2025-08-30': 'Others',
    '2025-09-06': 'Others',
    '2025-09-13': 'Others',
    '2025-09-20': 'PMS',
    '2025-09-27': 'NRI',
    '2025-10-11': 'NRI',
    '2025-10-18': 'Retirement Planning',
    '2025-11-01': 'Others',
    '2025-11-22': 'PMS',
    '2025-11-29': 'Family Office',
    '2025-12-06': 'PMS',
    '2025-12-20': 'PMS',
    '2026-01-10': 'Others',
    '2026-01-31': 'Others',
    '2026-02-07': 'PMS',
    '2026-02-21': 'Others',
    '2026-03-07': 'Others',
    '2026-03-28': 'NRI',
    '2026-04-04': 'PMS',
    '2026-04-11': 'PMS',
}

# ── SQLite ────────────────────────────────────────────────────────────────────
conn = sqlite3.connect('webinar_analytics.db')
c = conn.cursor()

# Add icp column if missing
try:
    c.execute("ALTER TABLE webinars ADD COLUMN icp TEXT DEFAULT 'Others'")
    print('Added icp column to SQLite')
except sqlite3.OperationalError:
    print('icp column already exists in SQLite')

# Update each webinar
updated = 0
for date_str, icp in ICP_BY_DATE.items():
    c.execute("UPDATE webinars SET icp=? WHERE date=?", (icp, date_str))
    updated += c.rowcount

conn.commit()
print(f'Updated {updated} webinars in SQLite')

# Verify
c.execute("SELECT icp, COUNT(*) FROM webinars GROUP BY icp ORDER BY COUNT(*) DESC")
print('ICP distribution:', dict(c.fetchall()))
conn.close()

# ── Supabase ──────────────────────────────────────────────────────────────────
print('\nUpdating Supabase...')
from sqlalchemy import create_engine, text

PG_URL = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
engine = create_engine(PG_URL, pool_pre_ping=True, pool_size=1, max_overflow=0,
                       connect_args={'ssl_context': ssl_ctx})

with engine.connect() as conn:
    # Add column if missing
    try:
        conn.execute(text("ALTER TABLE webinars ADD COLUMN icp VARCHAR(50) DEFAULT 'Others'"))
        conn.commit()
        print('Added icp column to Supabase')
    except Exception as e:
        if 'already exists' in str(e).lower():
            print('icp column already exists in Supabase')
        else:
            print('Column error:', e)

    # Update all webinars
    pg_updated = 0
    for date_str, icp in ICP_BY_DATE.items():
        result = conn.execute(text("UPDATE webinars SET icp=:icp WHERE date=:d"), {'icp': icp, 'd': date_str})
        pg_updated += result.rowcount
    conn.commit()
    print(f'Updated {pg_updated} webinars in Supabase')

    # Verify
    rows = conn.execute(text("SELECT icp, COUNT(*) FROM webinars GROUP BY icp ORDER BY COUNT(*) DESC")).fetchall()
    print('Supabase ICP distribution:', dict(rows))

print('\nDone!')
