import sys
import os
import shutil

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if os.environ.get("DATABASE_URL"):
    # PostgreSQL (Supabase): run create_all so new tables (e.g. webinar_ads) are
    # created automatically. create_all is idempotent — it skips existing tables.
    try:
        from database import engine
        import models
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        import traceback
        print("DB create_all error:", traceback.format_exc(), file=sys.stderr)
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
