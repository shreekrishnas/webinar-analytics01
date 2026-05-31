"""
Resume attendance migration — inserts rows that are NOT yet in Supabase.
Uses the SQLite local DB as source and Supabase direct IPv6 as destination.
ON CONFLICT DO NOTHING ensures idempotency.
"""
import ssl
import os
import sys
from sqlalchemy import create_engine, text, MetaData, Table

# ── Source: local SQLite ──────────────────────────────────────────────────────
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webinar_analytics.db")
src_engine = create_engine(
    f"sqlite:///{SQLITE_PATH}",
    connect_args={"check_same_thread": False},
)

# ── Destination: Supabase (direct IPv6, works locally) ───────────────────────
SUPABASE_URL = (
    "postgresql+pg8000://postgres:shreekrishna%401234"
    "@db.agwzlnljqfqjkybbqteb.supabase.co:5432/postgres"
)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

dst_engine = create_engine(
    SUPABASE_URL,
    pool_pre_ping=True,
    pool_size=1,
    max_overflow=0,
    connect_args={"ssl_context": ssl_ctx},
)

# ── Reflect destination table ─────────────────────────────────────────────────
dst_meta = MetaData()
dst_meta.reflect(bind=dst_engine, only=["attendances"])
att_tbl = dst_meta.tables["attendances"]

CHUNK = 20  # small chunks to avoid statement timeout on Nano compute

def main():
    # How many are already in Supabase?
    with dst_engine.connect() as dc:
        existing = dc.execute(text("SELECT COUNT(*) FROM attendances")).scalar()
    print(f"Already in Supabase: {existing}")

    # Fetch all rows from SQLite
    with src_engine.connect() as sc:
        rows = sc.execute(text("SELECT * FROM attendances ORDER BY id")).mappings().all()
    total = len(rows)
    print(f"Total in SQLite: {total}")

    if existing >= total:
        print("[DONE] Supabase already has all attendance rows.")
        return

    # Build set of IDs already in Supabase to skip them
    with dst_engine.connect() as dc:
        dc.execute(text("SET statement_timeout = 0"))
        existing_ids = {r[0] for r in dc.execute(text("SELECT id FROM attendances")).fetchall()}

    to_insert = [dict(r) for r in rows if r["id"] not in existing_ids]
    print(f"Rows to insert: {len(to_insert)}")

    inserted = 0
    errors = 0
    with dst_engine.connect() as dc:
        dc.execute(text("SET statement_timeout = 0"))
        dc.commit()

        for i in range(0, len(to_insert), CHUNK):
            chunk = to_insert[i : i + CHUNK]
            try:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt = pg_insert(att_tbl).values(chunk).on_conflict_do_nothing(index_elements=["id"])
                dc.execute(stmt)
                dc.commit()
                inserted += len(chunk)
                done = existing + inserted
                sys.stdout.write(f"\r  attendances: {done}/{total}")
                sys.stdout.flush()
            except Exception as e:
                dc.rollback()
                errors += 1
                print(f"\n  chunk {i}-{i+len(chunk)} error: {e}")
                # Re-disable timeout after rollback
                try:
                    dc.execute(text("SET statement_timeout = 0"))
                    dc.commit()
                except Exception:
                    pass

    print(f"\n[DONE] Inserted {inserted} rows. Errors: {errors}.")

    # Final count
    with dst_engine.connect() as dc:
        final = dc.execute(text("SELECT COUNT(*) FROM attendances")).scalar()
    print(f"Final Supabase count: {final}/{total}")

if __name__ == "__main__":
    main()
