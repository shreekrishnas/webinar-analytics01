"""Create webinar_notes table in SQLite + Supabase."""
import sqlite3, ssl
from sqlalchemy import create_engine, text

# ── SQLite ────────────────────────────────────────────────────────────────────
conn = sqlite3.connect('webinar_analytics.db')
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS webinar_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webinar_id INTEGER REFERENCES webinars(id) ON DELETE CASCADE,
    author TEXT DEFAULT 'Team',
    category TEXT DEFAULT 'observation',
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
c.execute("CREATE INDEX IF NOT EXISTS ix_webinar_notes_webinar_id ON webinar_notes(webinar_id)")
conn.commit()
conn.close()
print("SQLite: webinar_notes table ready")

# ── Supabase ──────────────────────────────────────────────────────────────────
ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
PG_URL = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
engine = create_engine(PG_URL, pool_size=1, max_overflow=0, connect_args={'ssl_context': ssl_ctx})

with engine.connect() as conn:
    try:
        conn.execute(text("""
CREATE TABLE IF NOT EXISTS webinar_notes (
    id SERIAL PRIMARY KEY,
    webinar_id INTEGER REFERENCES webinars(id) ON DELETE CASCADE,
    author VARCHAR(100) DEFAULT 'Team',
    category VARCHAR(50) DEFAULT 'observation',
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_webinar_notes_webinar_id ON webinar_notes(webinar_id)"))
        conn.commit()
        print("Supabase: webinar_notes table ready")
    except Exception as e:
        print("Supabase error:", e)

print("\nDone!")
