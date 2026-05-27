import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from database import engine, SessionLocal
import models, crud, schemas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


# ── Platform stats ────────────────────────────────────────────────────────────

@app.get("/api/stats", response_model=schemas.PlatformStats)
def platform_stats(db: Session = Depends(get_db)):
    return crud.get_platform_stats(db)


# ── Webinars ──────────────────────────────────────────────────────────────────

@app.get("/api/webinars", response_model=List[schemas.WebinarSummary])
def list_webinars(
    date: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    speaker_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
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


# ── Speakers ──────────────────────────────────────────────────────────────────

@app.get("/api/speakers", response_model=List[schemas.Speaker])
def list_speakers(db: Session = Depends(get_db)):
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
    speaker_id: Optional[int] = Query(None),
    webinar_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return crud.get_leaderboard(db, speaker_id=speaker_id, webinar_id=webinar_id, limit=limit)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
