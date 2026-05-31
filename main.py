import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from starlette.responses import Response as StarletteResponse
import csv, io
from sqlalchemy.orm import Session
from typing import Optional, List

from database import engine, SessionLocal
import models, crud, schemas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Static files with long-lived cache headers so browsers cache CSS/JS for 1 year.
# The ?v=XX query string in index.html handles cache-busting on deploy.
class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> StarletteResponse:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only seed in local dev; production (VERCEL / DATABASE_URL) is pre-seeded
    if not os.environ.get("DATABASE_URL") and not os.environ.get("VERCEL"):
        try:
            models.Base.metadata.create_all(bind=engine)
            from seed_data import seed_database
            seed_database()
        except Exception:
            pass
    yield


app = FastAPI(title="WebinarIQ Analytics", version="2.0.0", lifespan=lifespan)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Static files & root ───────────────────────────────────────────────────────

app.mount("/static", CachedStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


# ── Platform stats ────────────────────────────────────────────────────────────

@app.get("/api/stats", response_model=schemas.PlatformStats)
def platform_stats(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=20, stale-while-revalidate=60"
    return crud.get_platform_stats(db)


# ── Webinars ──────────────────────────────────────────────────────────────────

@app.get("/api/webinars", response_model=List[schemas.WebinarSummary])
def list_webinars(
    response: Response,
    date: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    speaker_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "public, max-age=15, stale-while-revalidate=45"
    if date:
        return crud.get_webinars_by_date(db, date)
    if name:
        return crud.get_webinars_by_name(db, name)
    webinars = crud.get_all_webinars(db)
    if speaker_id:
        webinars = [w for w in webinars if w.speaker_id == speaker_id]
    return webinars


@app.post("/api/webinars", response_model=schemas.WebinarSummary, status_code=201)
def create_webinar(webinar: schemas.WebinarCreate, db: Session = Depends(get_db)):
    w = crud.create_webinar(db, webinar)
    return crud._to_summary(db, w)


@app.get("/api/webinars/{webinar_id}", response_model=schemas.WebinarDetail)
def get_webinar(webinar_id: int, db: Session = Depends(get_db)):
    detail = crud.get_webinar_detail(db, webinar_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Webinar not found")
    return detail


@app.patch("/api/webinars/{webinar_id}", response_model=schemas.WebinarSummary)
def update_webinar(webinar_id: int, payload: dict, db: Session = Depends(get_db)):
    """Update title, speaker, time, description, or status of a webinar."""
    from sqlalchemy import func as _func
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")
    if "title" in payload:
        w.title = payload["title"].strip()
    if "time" in payload:
        w.time = payload["time"]
    if "description" in payload:
        w.description = payload["description"]
    if "status" in payload:
        w.status = payload["status"]
    if "speaker_name" in payload:
        sp_name = payload["speaker_name"].strip()
        speaker = db.query(models.Speaker).filter(
            _func.lower(models.Speaker.name) == sp_name.lower()
        ).first()
        if not speaker:
            speaker = models.Speaker(name=sp_name)
            db.add(speaker)
            db.flush()
        w.speaker_id = speaker.id
    db.commit()
    db.refresh(w)
    return crud._to_summary(db, w)


@app.delete("/api/webinars/{webinar_id}", status_code=204)
def delete_webinar(webinar_id: int, db: Session = Depends(get_db)):
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")
    db.delete(w)
    db.commit()


@app.post("/api/webinars/{webinar_id}/upload/registrations", response_model=schemas.UploadResult)
async def upload_registrations(
    webinar_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")
    content = await file.read()
    try:
        return crud.process_registration_upload(db, webinar_id, content, file.filename or "upload.csv")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/webinars/{webinar_id}/upload/attendees", response_model=schemas.UploadResult)
async def upload_attendees(
    webinar_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")
    content = await file.read()
    try:
        return crud.process_attendee_upload(db, webinar_id, content, file.filename or "upload.csv")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=traceback.format_exc())


# ── Registrations download ───────────────────────────────────────────────────

@app.get("/api/webinars/{webinar_id}/registrations/download")
def download_registrations(webinar_id: int, db: Session = Depends(get_db)):
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")

    regs = (
        db.query(models.Registration)
        .filter(models.Registration.webinar_id == webinar_id)
        .order_by(models.Registration.registered_at)
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Email", "Phone", "Source", "Registered At"])
    for r in regs:
        writer.writerow([
            r.attendee_name or "",
            r.email or "",
            r.phone or "",
            r.source or "",
            r.registered_at.isoformat() if r.registered_at else "",
        ])

    # utf-8-sig adds BOM so Excel opens it correctly
    data = buf.getvalue().encode("utf-8-sig")
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in w.title)[:40].strip("_")
    filename = f"registrations_{safe}_{w.date}.csv"

    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Platform-wide attendees download (Analytics page) ────────────────────────

@app.get("/api/attendees/download")
def download_all_attendees(
    speaker_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Download all attendees across every webinar as a single CSV."""
    from sqlalchemy import text as _text

    extra_where = ""
    params: dict = {}
    if speaker_id:
        extra_where = "AND w.speaker_id = :speaker_id"
        params["speaker_id"] = speaker_id

    sql = _text(f"""
        SELECT
            r.attendee_name,
            r.email,
            r.phone,
            w.title       AS webinar_title,
            w.date        AS webinar_date,
            COALESCE(s.name, 'Unknown') AS speaker_name,
            a.joined_at,
            a.left_at,
            a.duration_minutes
        FROM attendances a
        JOIN registrations r ON r.id = a.registration_id
        JOIN webinars w      ON w.id = a.webinar_id
        LEFT JOIN speakers s ON s.id = w.speaker_id
        WHERE a.attended = TRUE {extra_where}
        ORDER BY w.date DESC, r.attendee_name
    """)
    rows = db.execute(sql, params).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Email", "Phone", "Webinar", "Webinar Date",
                     "Speaker", "Joined At", "Left At", "Duration (minutes)"])
    for row in rows:
        writer.writerow([
            row.attendee_name or "",
            row.email or "",
            row.phone or "",
            row.webinar_title or "",
            str(row.webinar_date) if row.webinar_date else "",
            row.speaker_name or "",
            row.joined_at.isoformat() if row.joined_at else "",
            row.left_at.isoformat() if row.left_at else "",
            row.duration_minutes if row.duration_minutes is not None else "",
        ])

    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="all_attendees.csv"'},
    )


# ── Attendees download ───────────────────────────────────────────────────────

@app.get("/api/webinars/{webinar_id}/attendees/download")
def download_attendees(webinar_id: int, db: Session = Depends(get_db)):
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")

    rows = (
        db.query(models.Attendance, models.Registration)
        .outerjoin(models.Registration, models.Attendance.registration_id == models.Registration.id)
        .filter(models.Attendance.webinar_id == webinar_id, models.Attendance.attended == True)
        .order_by(models.Attendance.joined_at)
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Email", "Phone", "Joined At", "Left At", "Duration (minutes)"])
    for att, reg in rows:
        writer.writerow([
            reg.attendee_name if reg else "",
            reg.email if reg else "",
            reg.phone if reg else "",
            att.joined_at.isoformat() if att.joined_at else "",
            att.left_at.isoformat() if att.left_at else "",
            att.duration_minutes if att.duration_minutes is not None else "",
        ])

    data = buf.getvalue().encode("utf-8-sig")
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in w.title)[:40].strip("_")
    filename = f"attendees_{safe}_{w.date}.csv"

    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Ad Creatives ──────────────────────────────────────────────────────────────

@app.get("/api/webinars/{webinar_id}/ads", response_model=List[schemas.WebinarAdOut])
def list_webinar_ads(webinar_id: int, db: Session = Depends(get_db)):
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")
    return crud.get_webinar_ads(db, webinar_id)


@app.post("/api/webinars/{webinar_id}/ads", response_model=schemas.WebinarAdOut, status_code=201)
def create_webinar_ad(
    webinar_id: int,
    ad: schemas.WebinarAdCreate,
    db: Session = Depends(get_db),
):
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")
    created = crud.create_webinar_ad(db, webinar_id, ad)
    return schemas.WebinarAdOut.model_validate(created)


@app.delete("/api/webinars/{webinar_id}/ads/{ad_id}", status_code=204)
def delete_webinar_ad(webinar_id: int, ad_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_webinar_ad(db, ad_id, webinar_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ad not found")


# ── Speakers ──────────────────────────────────────────────────────────────────

@app.get("/api/speakers", response_model=List[schemas.Speaker])
def list_speakers(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=120"
    return crud.get_all_speakers(db)


@app.get("/api/speakers/{speaker_id}", response_model=schemas.SpeakerDetail)
def get_speaker(speaker_id: int, db: Session = Depends(get_db)):
    detail = crud.get_speaker_detail(db, speaker_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return detail


# ── Attendee profile ──────────────────────────────────────────────────────────

@app.get("/api/attendee", response_model=schemas.AttendeeProfile)
def get_attendee(email: str = Query(...), db: Session = Depends(get_db)):
    profile = crud.get_attendee_profile(db, email)
    if not profile:
        raise HTTPException(status_code=404, detail="Attendee not found")
    return profile


# ── Leaderboard ───────────────────────────────────────────────────────────────

@app.get("/api/leaderboard", response_model=List[schemas.LeaderboardEntry])
def get_leaderboard(
    response: Response,
    speaker_id: Optional[int] = Query(None),
    webinar_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "public, max-age=20, stale-while-revalidate=60"
    return crud.get_leaderboard(db, speaker_id=speaker_id, webinar_id=webinar_id, limit=limit)


# ── Admin: fix out-of-sync sequences ─────────────────────────────────────────

@app.post("/api/admin/bulk-update-webinars")
def bulk_update_webinars(payload: dict, db: Session = Depends(get_db)):
    """Update title + speaker for multiple webinars by date in one transaction.
    Body: {"updates": [{"date": "YYYY-MM-DD", "title": "...", "speaker_name": "..."}, ...]}
    """
    from sqlalchemy import func as _func, text as _t
    updates = payload.get("updates", [])
    updated = 0
    for item in updates:
        date   = item.get("date")
        title  = item.get("title", "").strip()
        sp_raw = item.get("speaker_name", "").strip()
        if not date:
            continue
        # find webinar by date
        w = db.query(models.Webinar).filter(models.Webinar.date == date).first()
        if not w:
            continue
        if title:
            w.title = title
        if sp_raw:
            speaker = db.query(models.Speaker).filter(
                _func.lower(models.Speaker.name) == sp_raw.lower()
            ).first()
            if not speaker:
                speaker = models.Speaker(name=sp_raw)
                db.add(speaker)
                db.flush()
            w.speaker_id = speaker.id
        updated += 1
    db.commit()
    return {"updated": updated}


@app.post("/api/admin/bulk-delete-webinars")
def bulk_delete_webinars(payload: dict, db: Session = Depends(get_db)):
    """Delete a list of webinar IDs and all their cascaded data in one transaction."""
    from sqlalchemy import text as _t
    ids = payload.get("ids", [])
    if not ids:
        return {"deleted": 0}
    id_list = ",".join(str(int(i)) for i in ids)
    db.execute(_t(f"DELETE FROM upload_logs   WHERE webinar_id IN ({id_list})"))
    db.execute(_t(f"DELETE FROM webinar_ads   WHERE webinar_id IN ({id_list})"))
    db.execute(_t(f"DELETE FROM attendances   WHERE webinar_id IN ({id_list})"))
    db.execute(_t(f"DELETE FROM registrations WHERE webinar_id IN ({id_list})"))
    db.execute(_t(f"DELETE FROM webinars      WHERE id          IN ({id_list})"))
    db.commit()
    return {"deleted": len(ids)}


@app.post("/api/admin/fix-sequences")
def fix_sequences(db: Session = Depends(get_db)):
    """One-time fix for PostgreSQL sequences that fell behind explicit-ID bulk imports."""
    from sqlalchemy import text as _t
    results = {}
    for table, seq in [
        ("registrations", "registrations_id_seq"),
        ("attendances",   "attendances_id_seq"),
        ("upload_logs",   "upload_logs_id_seq"),
        ("webinars",      "webinars_id_seq"),
        ("speakers",      "speakers_id_seq"),
    ]:
        try:
            db.execute(_t(
                f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1))"
            ))
            results[seq] = "ok"
        except Exception as e:
            results[seq] = str(e)
    db.commit()
    return results


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
