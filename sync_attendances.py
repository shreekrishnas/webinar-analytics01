# -*- coding: utf-8 -*-
"""Sync attendances from SQLite → Supabase with proper boolean handling and retries."""
import os, sys, ssl, time
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import create_engine, text

SQLITE_URL = "sqlite:///webinar_analytics.db"
PG_URL     = "postgresql+pg8000://postgres.agwzlnljqfqjkybbqteb:shreekrishna%401234@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
pg_engine = create_engine(PG_URL, pool_pre_ping=True, pool_size=1, max_overflow=0,
                           pool_recycle=120, connect_args={"ssl_context": ssl_ctx})

CHUNK = 200  # smaller chunks to avoid timeout

with sqlite_engine.connect() as src:
    total = src.execute(text("SELECT COUNT(*) FROM attendances")).scalar()
    print(f"Attendances to sync: {total}")

    with pg_engine.connect() as dst:
        existing = dst.execute(text("SELECT COUNT(*) FROM attendances")).scalar()
        print(f"Already in Supabase: {existing}")

    offset = 0
    synced = 0
    errors = 0

    while True:
        rows = src.execute(
            text(f"SELECT id,webinar_id,registration_id,joined_at,left_at,duration_minutes,attended "
                 f"FROM attendances ORDER BY id LIMIT {CHUNK} OFFSET {offset}")
        ).fetchall()
        if not rows:
            break

        # Convert attended 0/1 → Python bool for PostgreSQL
        data = []
        for r in rows:
            data.append({
                "id": r[0], "webinar_id": r[1], "registration_id": r[2],
                "joined_at": r[3], "left_at": r[4], "duration_minutes": r[5],
                "attended": bool(r[6])
            })

        # Retry up to 3 times on network error
        for attempt in range(3):
            try:
                with pg_engine.connect() as dst:
                    dst.execute(text(
                        'INSERT INTO attendances (id,webinar_id,registration_id,joined_at,left_at,duration_minutes,attended) '
                        'VALUES (:id,:webinar_id,:registration_id,:joined_at,:left_at,:duration_minutes,:attended) '
                        'ON CONFLICT (id) DO UPDATE SET '
                        'webinar_id=EXCLUDED.webinar_id, registration_id=EXCLUDED.registration_id, '
                        'joined_at=EXCLUDED.joined_at, left_at=EXCLUDED.left_at, '
                        'duration_minutes=EXCLUDED.duration_minutes, attended=EXCLUDED.attended'
                    ), data)
                    dst.commit()
                synced += len(rows)
                break
            except Exception as e:
                errors += 1
                if attempt < 2:
                    print(f"  Retry {attempt+1} after error: {str(e)[:80]}")
                    time.sleep(3)
                else:
                    print(f"  FAILED batch at offset {offset}: {str(e)[:120]}")

        offset += CHUNK
        print(f"\r  {synced}/{total}", end="", flush=True)

print(f"\n[DONE] {synced} attendances synced | {errors} errors")

# Fix sequence
with pg_engine.connect() as dst:
    try:
        dst.execute(text("SELECT setval(pg_get_serial_sequence('attendances','id'),(SELECT MAX(id) FROM attendances),true)"))
        dst.commit()
        print("Sequence fixed.")
    except Exception as e:
        print("Sequence fix skipped:", e)

# Verify
with pg_engine.connect() as dst:
    count = dst.execute(text("SELECT COUNT(*) FROM attendances")).scalar()
    sample = dst.execute(text("SELECT webinar_id, COUNT(*) FROM attendances WHERE webinar_id=11 GROUP BY webinar_id")).fetchall()
    print(f"Total in Supabase: {count}")
    print(f"Webinar 11 attendances: {sample}")
