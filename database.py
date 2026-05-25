import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# On Vercel the filesystem is read-only except /tmp
if os.environ.get("VERCEL"):
    db_path = "/tmp/webinar_analytics.db"
else:
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webinar_analytics.db")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass
