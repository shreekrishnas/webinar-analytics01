import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # PostgreSQL (Supabase) — serverless-safe settings
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        connect_args={"sslmode": "require"},
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
