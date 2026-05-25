# -*- coding: utf-8 -*-
"""
Migration script: copies all data from local SQLite to Supabase PostgreSQL.
Run once from the project root:
    python migrate_to_supabase.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Connection strings ────────────────────────────────────────────────────────
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webinar_analytics.db")
SQLITE_URL = "sqlite:///" + SQLITE_PATH

# @ in password encoded as %40
PG_URL = "postgresql://postgres:shreekrishna%401234@db.elhuhzqjawvhxkhnwdjf.supabase.co:5432/postgres"

# ── Engines ──────────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, text, MetaData

print("Connecting to SQLite ...")
sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

print("Connecting to Supabase PostgreSQL ...")
pg_engine = create_engine(
    PG_URL,
    pool_pre_ping=True,
    pool_size=1,
    max_overflow=0,
    connect_args={"sslmode": "require"},
)

# ── Test connection ───────────────────────────────────────────────────────────
with pg_engine.connect() as conn:
    conn.execute(text("SELECT 1"))
print("[OK] Supabase connection OK")

# ── Create tables ─────────────────────────────────────────────────────────────
import models
from models import Base

print("Creating tables in Supabase ...")
Base.metadata.create_all(bind=pg_engine)
print("[OK] Tables ready")

# ── Raw table copy ────────────────────────────────────────────────────────────
def copy_table(table_name, chunk_size=500):
    """Copy all rows from SQLite table to Postgres table using raw SQL."""
    meta = MetaData()
    meta.reflect(bind=sqlite_engine, only=[table_name])
    tbl = meta.tables[table_name]

    with sqlite_engine.connect() as src_conn:
        total = src_conn.execute(text("SELECT COUNT(*) FROM " + table_name)).scalar()
        print("  " + table_name + ": " + str(total) + " rows", end="", flush=True)

        if total == 0:
            print(" (skipped)")
            return

        with pg_engine.connect() as dst_conn:
            # Truncate destination first
            dst_conn.execute(text("TRUNCATE TABLE " + table_name + " RESTART IDENTITY CASCADE"))
            dst_conn.commit()

            offset = 0
            copied = 0
            while True:
                rows = src_conn.execute(
                    text("SELECT * FROM " + table_name + " LIMIT " + str(chunk_size) + " OFFSET " + str(offset))
                ).fetchall()
                if not rows:
                    break

                data = [dict(row._mapping) for row in rows]
                dst_conn.execute(tbl.insert(), data)
                dst_conn.commit()

                copied += len(rows)
                print("\r  " + table_name + ": " + str(copied) + "/" + str(total), end="", flush=True)
                offset += chunk_size

            print("\r  [DONE] " + table_name + ": " + str(copied) + " rows copied.   ")

            # Reset sequence so future INSERTs don't collide
            dst_conn.execute(text(
                "SELECT setval(pg_get_serial_sequence('" + table_name + "', 'id'), "
                "(SELECT MAX(id) FROM " + table_name + "), true)"
            ))
            dst_conn.commit()

# Copy in FK-safe order (parents before children)
print("\nMigrating data ...")
copy_table("speakers")
copy_table("webinars")
copy_table("registrations")
copy_table("attendances")
copy_table("upload_logs")

print("\nMigration complete! All data is now in Supabase.")
print("Source: " + SQLITE_PATH)
print("Target: db.elhuhzqjawvhxkhnwdjf.supabase.co")
