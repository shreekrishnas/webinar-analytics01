"""Quick count check for Supabase tables."""
import ssl
from sqlalchemy import create_engine, text

DIRECT_URL = "postgresql+pg8000://postgres:shreekrishna%401234@db.agwzlnljqfqjkybbqteb.supabase.co:5432/postgres"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

engine = create_engine(
    DIRECT_URL,
    pool_pre_ping=True,
    pool_size=1,
    max_overflow=0,
    connect_args={"ssl_context": ssl_ctx},
)

with engine.connect() as conn:
    for tbl in ("speakers", "webinars", "registrations", "attendances"):
        try:
            row = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).fetchone()
            print(f"  {tbl}: {row[0]}")
        except Exception as e:
            print(f"  {tbl}: ERROR - {e}")
