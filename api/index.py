import sys
import os
import shutil

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if os.environ.get("DATABASE_URL"):
    # PostgreSQL: create any missing tables, then add any missing columns.
    try:
        from database import engine
        import models
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        import traceback
        print("DB create_all error:", traceback.format_exc(), file=sys.stderr)

    # Column migrations — ADD COLUMN IF NOT EXISTS is idempotent in PostgreSQL.
    # Add new columns here whenever the model gains a new field.
    _COLUMN_MIGRATIONS = [
        # (table, column, pg_type)
        ("webinars", "icp",                    "VARCHAR"),
        ("webinars", "co_speaker_id",           "INTEGER"),
        ("webinars", "platform",                "VARCHAR"),
        ("webinars", "category",                "VARCHAR"),
        ("webinars", "language",                "VARCHAR"),
        ("webinars", "recording_url",           "VARCHAR"),
        ("webinars", "tags",                    "VARCHAR"),
        ("webinars", "expected_registrations",  "INTEGER"),
        ("webinars", "notes",                   "TEXT"),
        ("webinars", "series",                  "VARCHAR"),
        ("webinars", "is_favourite",            "BOOLEAN DEFAULT FALSE"),
        ("speakers",  "bio",                    "TEXT"),
        ("upload_logs", "unmatched_attendees",  "INTEGER DEFAULT 0"),
        ("upload_logs", "filename",             "VARCHAR"),
    ]
    try:
        from sqlalchemy import text as _text
        with engine.connect() as _conn:
            for _tbl, _col, _typ in _COLUMN_MIGRATIONS:
                try:
                    _conn.execute(_text(
                        f"ALTER TABLE {_tbl} ADD COLUMN IF NOT EXISTS {_col} {_typ}"
                    ))
                except Exception as _ce:
                    print(f"Column migration warning {_tbl}.{_col}: {_ce}", file=sys.stderr)
            _conn.commit()
        print("DB column migrations done", file=sys.stderr)
    except Exception as e:
        import traceback
        print("DB migration error:", traceback.format_exc(), file=sys.stderr)
elif os.environ.get("VERCEL"):
    # Vercel without Postgres: copy bundled SQLite DB to /tmp on cold start
    try:
        src_db = os.path.join(ROOT_DIR, "webinar_analytics.db")
        dst_db = "/tmp/webinar_analytics.db"
        if os.path.exists(src_db):
            shutil.copy2(src_db, dst_db)
    except Exception as e:
        print("SQLite copy error:", e, file=sys.stderr)
else:
    # Local dev: normal init + seeding
    try:
        from database import engine
        import models
        models.Base.metadata.create_all(bind=engine)
        from seed_data import seed_database
        seed_database()
    except Exception as e:
        import traceback
        print("Local init error:", traceback.format_exc(), file=sys.stderr)

from main import app
