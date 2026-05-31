# -*- coding: utf-8 -*-
"""
Migration script: syncs local SQLite → Supabase PostgreSQL using UPSERTS.
Safe to run multiple times — never duplicates, only inserts new / updates changed rows.

    python migrate_to_supabase.py
"""

import os, sys, ssl
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import create_engine, text, MetaData

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webinar_analytics.db")
SQLITE_URL  = "sqlite:///" + SQLITE_PATH
PG_URL      = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

print("Connecting to SQLite ...")
sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

print("Connecting to Supabase ...")
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
pg_engine = create_engine(
    PG_URL, pool_pre_ping=True, pool_size=1, max_overflow=0,
    connect_args={"ssl_context": ssl_ctx},
)
with pg_engine.connect() as c:
    c.execute(text("SELECT 1"))
print("[OK] Supabase connected")

# Create tables if they don't exist yet
import models
models.Base.metadata.create_all(bind=pg_engine)
print("[OK] Tables ready\n")


def upsert_table(table_name, conflict_col="id", chunk_size=500):
    """
    Upsert rows from SQLite → Supabase.
    - Rows with a new id are inserted.
    - Rows with an existing id are updated with the latest values.
    - Rows that were deleted locally are NOT removed from Supabase.
    """
    meta = MetaData()
    meta.reflect(bind=sqlite_engine, only=[table_name])
    tbl  = meta.tables[table_name]
    cols = [c.name for c in tbl.columns]

    # Build the SET clause for updates (all cols except the conflict col)
    update_cols = [c for c in cols if c != conflict_col]
    set_clause  = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)

    with sqlite_engine.connect() as src:
        total = src.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        if total == 0:
            print(f"  {table_name}: empty — skipped")
            return

        # Check how many already exist in Supabase
        with pg_engine.connect() as dst:
            existing = dst.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()

        print(f"  {table_name}: {total} local rows | {existing} already in Supabase")

        offset  = 0
        upserted = 0
        with pg_engine.connect() as dst:
            while True:
                rows = src.execute(
                    text(f"SELECT * FROM {table_name} LIMIT {chunk_size} OFFSET {offset}")
                ).fetchall()
                if not rows:
                    break
                data = [dict(r._mapping) for r in rows]

                col_list   = ", ".join(f'"{c}"' for c in cols)
                val_list   = ", ".join(f":{c}" for c in cols)
                sql = text(
                    f"INSERT INTO {table_name} ({col_list}) VALUES ({val_list}) "
                    f"ON CONFLICT ({conflict_col}) DO UPDATE SET {set_clause}"
                )
                dst.execute(sql, data)
                dst.commit()
                upserted += len(rows)
                print(f"\r    {upserted}/{total}", end="", flush=True)
                offset += chunk_size

            # Keep sequence in sync
            try:
                dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                    f"(SELECT MAX(id) FROM {table_name}), true)"
                ))
                dst.commit()
            except Exception:
                pass

        print(f"\r  [DONE] {table_name}: {upserted} rows upserted\n")


print("Syncing data (upsert — safe to re-run) ...")
upsert_table("speakers")
upsert_table("webinars")
upsert_table("registrations")
upsert_table("attendances")
upsert_table("upload_logs")

print("Sync complete! Supabase is now up to date.")
