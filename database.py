import os
import ssl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # PostgreSQL (Supabase) via pg8000 (pure-Python, no C deps — safe on Vercel)
    # Normalise to pg8000 dialect regardless of what prefix the env var has
    if "postgresql+pg8000://" in DATABASE_URL:
        pg_url = DATABASE_URL
    elif DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://"):
        pg_url = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
        pg_url = pg_url.replace("postgresql://", "postgresql+pg8000://", 1)
    else:
        pg_url = DATABASE_URL

    # SSL context for Supabase
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # pool_size=2 reuses connections across warm Lambda invocations.
    # pool_recycle=240 drops connections before Supabase's 5-min idle timeout
    # so stale connections are never handed to a request.
    # pool_pre_ping removed — the recycle window handles staleness without
    # an extra SELECT 1 round-trip on every warm request.
    engine = create_engine(
        pg_url,
        pool_size=2,
        max_overflow=0,
        pool_recycle=240,
        connect_args={"ssl_context": ssl_ctx},
    )
else:
    # Local fallback: SQLite
    if os.environ.get("VERCEL"):
        db_path = "/tmp/webinar_analytics.db"
    else:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webinar_analytics.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass
