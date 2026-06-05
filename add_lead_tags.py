"""Create lead_tags table for manual lead classification overrides."""
import sqlite3, ssl
from sqlalchemy import create_engine, text

# ── SQLite ────────────────────────────────────────────────────────────────────
conn = sqlite3.connect('webinar_analytics.db')
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS lead_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    tag TEXT NOT NULL,
    note TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
c.execute("CREATE INDEX IF NOT EXISTS ix_lead_tags_email ON lead_tags(email)")
conn.commit()
conn.close()
print("SQLite: lead_tags ready")

# ── Supabase ──────────────────────────────────────────────────────────────────
ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
PG_URL = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
engine = create_engine(PG_URL, pool_size=1, max_overflow=0, connect_args={'ssl_context': ssl_ctx})
with engine.connect() as conn:
    try:
        conn.execute(text("""
CREATE TABLE IF NOT EXISTS lead_tags (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    tag VARCHAR(50) NOT NULL,
    note TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_lead_tags_email ON lead_tags(email)"))
        conn.commit()
        print("Supabase: lead_tags ready")
    except Exception as e:
        print("Supabase err:", e)
