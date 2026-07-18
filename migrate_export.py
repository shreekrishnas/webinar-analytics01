"""
Export full WebinarIQ database (schema + data) as a SQL file.
Run locally or on any machine with DATABASE_URL set to the source Supabase.

Usage:
    DATABASE_URL="postgresql+pg8000://..." python migrate_export.py

Output: webinariq_full_export.sql  (ready to run on a new Supabase project)
"""
import os, sys
from datetime import datetime, date
from sqlalchemy import create_engine, text
import ssl

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Fallback: try local SQLite
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webinar_analytics.db")
    if os.path.exists(db_path):
        DATABASE_URL = f"sqlite:///{db_path}"
    else:
        print("ERROR: Set DATABASE_URL or have webinar_analytics.db locally")
        sys.exit(1)

if "postgresql" in DATABASE_URL or "postgres://" in DATABASE_URL:
    pg_url = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
    pg_url = pg_url.replace("postgresql://", "postgresql+pg8000://", 1)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    engine = create_engine(pg_url, connect_args={"ssl_context": ssl_ctx})
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def escape_sql(val):
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (datetime, date)):
        return f"'{val.isoformat()}'"
    s = str(val).replace("'", "''")
    return f"'{s}'"


SCHEMA_SQL = """
-- ============================================================
-- WebinarIQ Full Database Export
-- Generated: {timestamp}
-- ============================================================

-- 1. speakers
CREATE TABLE IF NOT EXISTS speakers (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR,
    bio TEXT
);
CREATE INDEX IF NOT EXISTS ix_speakers_name ON speakers(name);

-- 2. webinars
CREATE TABLE IF NOT EXISTS webinars (
    id SERIAL PRIMARY KEY,
    title VARCHAR NOT NULL,
    date DATE NOT NULL,
    time VARCHAR,
    speaker_id INTEGER REFERENCES speakers(id),
    description TEXT,
    status VARCHAR DEFAULT 'completed',
    icp VARCHAR DEFAULT 'Others',
    co_speaker_id INTEGER REFERENCES speakers(id),
    platform VARCHAR,
    category VARCHAR,
    language VARCHAR,
    recording_url VARCHAR,
    tags VARCHAR,
    expected_registrations INTEGER,
    notes TEXT,
    series VARCHAR,
    is_favourite BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_webinars_title ON webinars(title);

-- 3. registrations
CREATE TABLE IF NOT EXISTS registrations (
    id SERIAL PRIMARY KEY,
    webinar_id INTEGER REFERENCES webinars(id),
    attendee_name VARCHAR NOT NULL,
    email VARCHAR,
    phone VARCHAR,
    source VARCHAR,
    registered_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_reg_webinar_id ON registrations(webinar_id);
CREATE INDEX IF NOT EXISTS ix_reg_email_lower ON registrations(email);

-- 4. attendances
CREATE TABLE IF NOT EXISTS attendances (
    id SERIAL PRIMARY KEY,
    webinar_id INTEGER REFERENCES webinars(id),
    registration_id INTEGER REFERENCES registrations(id),
    joined_at TIMESTAMP,
    left_at TIMESTAMP,
    duration_minutes INTEGER,
    attended BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS ix_att_webinar_attended ON attendances(webinar_id, attended);
CREATE INDEX IF NOT EXISTS ix_att_registration_id ON attendances(registration_id);

-- 5. upload_logs
CREATE TABLE IF NOT EXISTS upload_logs (
    id SERIAL PRIMARY KEY,
    webinar_id INTEGER REFERENCES webinars(id),
    file_type VARCHAR NOT NULL,
    filename VARCHAR,
    original_count INTEGER DEFAULT 0,
    final_count INTEGER DEFAULT 0,
    duplicates_removed INTEGER DEFAULT 0,
    unmatched_attendees INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- 6. webinar_notes
CREATE TABLE IF NOT EXISTS webinar_notes (
    id SERIAL PRIMARY KEY,
    webinar_id INTEGER REFERENCES webinars(id) ON DELETE CASCADE,
    author VARCHAR DEFAULT 'Team',
    category VARCHAR DEFAULT 'observation',
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_webinar_notes_webinar_id ON webinar_notes(webinar_id);

-- 7. pipeline_contacts
CREATE TABLE IF NOT EXISTS pipeline_contacts (
    email VARCHAR PRIMARY KEY,
    status VARCHAR DEFAULT 'new',
    assigned_to VARCHAR,
    notes TEXT,
    follow_up_date DATE,
    added_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 8. webinar_ads
CREATE TABLE IF NOT EXISTS webinar_ads (
    id SERIAL PRIMARY KEY,
    webinar_id INTEGER REFERENCES webinars(id) ON DELETE CASCADE,
    title VARCHAR NOT NULL,
    platform VARCHAR,
    ad_type VARCHAR,
    creative_image TEXT,
    creative_url VARCHAR,
    headline VARCHAR,
    description TEXT,
    cta_text VARCHAR,
    landing_url VARCHAR,
    budget VARCHAR,
    spend VARCHAR,
    impressions INTEGER,
    clicks INTEGER,
    conversions INTEGER,
    start_date DATE,
    end_date DATE,
    status VARCHAR DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

TABLES = [
    ("speakers", ["id", "name", "email", "bio"]),
    ("webinars", ["id", "title", "date", "time", "speaker_id", "description", "status", "icp",
                  "co_speaker_id", "platform", "category", "language", "recording_url", "tags",
                  "expected_registrations", "notes", "series", "is_favourite"]),
    ("registrations", ["id", "webinar_id", "attendee_name", "email", "phone", "source", "registered_at"]),
    ("attendances", ["id", "webinar_id", "registration_id", "joined_at", "left_at", "duration_minutes", "attended"]),
    ("upload_logs", ["id", "webinar_id", "file_type", "filename", "original_count", "final_count",
                     "duplicates_removed", "unmatched_attendees", "uploaded_at"]),
    ("webinar_notes", ["id", "webinar_id", "author", "category", "content", "created_at"]),
    ("pipeline_contacts", ["email", "status", "assigned_to", "notes", "follow_up_date", "added_at", "updated_at"]),
    ("webinar_ads", ["id", "webinar_id", "title", "platform", "ad_type", "creative_image", "creative_url",
                     "headline", "description", "cta_text", "landing_url", "budget", "spend",
                     "impressions", "clicks", "conversions", "start_date", "end_date", "status",
                     "notes", "created_at"]),
]


def export():
    out = SCHEMA_SQL.format(timestamp=datetime.utcnow().isoformat())
    conn = engine.connect()

    for table_name, columns in TABLES:
        # Detect which columns actually exist in the source DB
        try:
            sample = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 1"))
            existing_cols = [c[0] for c in sample.cursor.description] if sample.cursor and sample.cursor.description else []
            sample.close()
        except Exception:
            existing_cols = []
        avail_cols = [c for c in columns if c in existing_cols] if existing_cols else columns

        col_list = ", ".join(avail_cols)
        try:
            rows = conn.execute(text(f"SELECT {col_list} FROM {table_name}")).fetchall()
        except Exception:
            out += f"\n-- {table_name}: table not found in source, skipping\n"
            continue
        if not rows:
            out += f"\n-- {table_name}: 0 rows (empty)\n"
            continue

        out += f"\n-- {table_name}: {len(rows)} rows\n"

        # Reset sequence for tables with integer PKs
        if columns[0] == "id":
            max_id = max(getattr(r, "id", 0) or 0 for r in rows)
            out += f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {max_id + 1}, false);\n"

        for row in rows:
            vals = ", ".join(escape_sql(getattr(row, c, None)) for c in avail_cols)
            out += f"INSERT INTO {table_name} ({col_list}) VALUES ({vals}) ON CONFLICT DO NOTHING;\n"

    conn.close()

    outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webinariq_full_export.sql")
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(out)

    print(f"Exported to {outfile}")
    print(f"Tables exported: {len(TABLES)}")
    for table_name, _ in TABLES:
        count = conn.connect().execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() if False else "done"
        print(f"  - {table_name}")


if __name__ == "__main__":
    export()
