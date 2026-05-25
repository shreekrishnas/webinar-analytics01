import sys
import os
import shutil

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if os.environ.get("DATABASE_URL"):
    # PostgreSQL (Supabase): ensure tables exist (idempotent, tables likely already there)
    try:
        from database import engine
        import models
        models.Base.metadata.create_all(bind=engine)
    except Exception:
        pass  # Tables already exist — safe to ignore
elif os.environ.get("VERCEL"):
    # Vercel without Postgres: copy bundled SQLite DB to /tmp on cold start
    src_db = os.path.join(ROOT_DIR, "webinar_analytics.db")
    dst_db = "/tmp/webinar_analytics.db"
    if os.path.exists(src_db):
        shutil.copy2(src_db, dst_db)
else:
    # Local dev: normal init + seeding
    from database import engine
    import models
    models.Base.metadata.create_all(bind=engine)
    from seed_data import seed_database
    seed_database()

from main import app
