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


def _compute_perf_score(regs: int, att_rate: float, icp: str, has_ads: bool = False) -> int:
    """Compute 0-100 performance score. No ads: reg vol 25%, att rate 35%, ICP 20%, speaker-topic fit 15%, follow-up 5%."""
    # Registration volume score (25 pts): benchmark 150 regs = full score
    reg_score = min(25, round(regs / 150 * 25))
    # Attendance rate score (35 pts): 60%+ = full
    att_score = min(35, round(att_rate / 60 * 35))
    # ICP relevance score (20 pts): premium ICPs score higher
    icp_scores = {'Family Office': 20, 'AIF': 20, 'PMS': 18, 'NRI': 16, 'ESOPs': 15, 'Retirement Planning': 14, 'Others': 8}
    icp_score = icp_scores.get(icp or 'Others', 8)
    # Speaker-topic fit (15 pts): give 10 pts baseline (no data to distinguish)
    fit_score = 10
    # Follow-up completion (5 pts): give 3 pts baseline
    followup_score = 3
    return min(100, reg_score + att_score + icp_score + fit_score + followup_score)


def _score_label(score: int) -> str:
    if score >= 80: return "High Performing"
    if score >= 60: return "Good"
    if score >= 40: return "Average"
    return "Low Performing"


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


@app.middleware("http")
async def no_cache_api_middleware(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


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
    resp = FileResponse(os.path.join(BASE_DIR, "static", "index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


# ── Platform stats ────────────────────────────────────────────────────────────

@app.get("/api/stats")
def platform_stats(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    stats = crud.get_platform_stats(db)
    # Add follow-up pending: attendees not yet in pipeline or still 'new'
    try:
        from sqlalchemy import text as _t
        fp = db.execute(_t("""
            SELECT COUNT(DISTINCT r.email) FROM attendances a
            JOIN registrations r ON r.id=a.registration_id
            WHERE a.attended=TRUE AND r.email IS NOT NULL
            AND r.email NOT IN (SELECT email FROM pipeline_contacts WHERE status != 'new')
        """)).fetchone()[0] or 0
        result = stats.dict() if hasattr(stats, 'dict') else dict(stats)
        result['followup_pending'] = int(fp)
        return result
    except Exception:
        return stats


# ── Webinars ──────────────────────────────────────────────────────────────────

@app.get("/api/webinars")
def list_webinars(
    response: Response,
    date: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    speaker_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    if date:
        webinars = crud.get_webinars_by_date(db, date)
    elif name:
        webinars = crud.get_webinars_by_name(db, name)
    else:
        webinars = crud.get_all_webinars(db)
        if speaker_id:
            webinars = [w for w in webinars if w.speaker_id == speaker_id]
    result = []
    for w in webinars:
        d = w.dict() if hasattr(w, 'dict') else dict(w)
        if d.get('status') == 'completed':
            regs = d.get('total_registrations') or 0
            att_rate = d.get('attendance_rate') or 0
            icp = d.get('icp') or 'Others'
            score = _compute_perf_score(regs, att_rate, icp)
            d['performance_score'] = score
            d['score_label'] = _score_label(score)
        result.append(d)
    return result


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
    if "date" in payload:
        from datetime import date as _date
        d = payload["date"]
        w.date = _date.fromisoformat(d) if isinstance(d, str) else d
    if "icp" in payload:
        w.icp = payload["icp"] or "Others"
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


# ── Webinar Notes (Human Knowledge) ──────────────────────────────────────────

@app.get("/api/webinars/{webinar_id}/notes")
def list_notes(webinar_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _text
    rows = db.execute(_text("""
        SELECT id, author, category, content, created_at
        FROM webinar_notes WHERE webinar_id = :w
        ORDER BY created_at DESC
    """), {"w": webinar_id}).fetchall()
    return [{
        "id": r.id, "author": r.author, "category": r.category,
        "content": r.content, "created_at": str(r.created_at)
    } for r in rows]


@app.post("/api/webinars/{webinar_id}/notes", status_code=201)
def add_note(webinar_id: int, payload: dict, db: Session = Depends(get_db)):
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    note = models.WebinarNote(
        webinar_id=webinar_id,
        author=(payload.get("author") or "Team").strip()[:100],
        category=(payload.get("category") or "observation"),
        content=content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id, "author": note.author, "category": note.category,
        "content": note.content, "created_at": str(note.created_at)
    }


@app.delete("/api/webinars/{webinar_id}/notes/{note_id}", status_code=204)
def delete_note(webinar_id: int, note_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _text
    db.execute(_text("DELETE FROM webinar_notes WHERE id = :nid AND webinar_id = :w"),
               {"nid": note_id, "w": webinar_id})
    db.commit()


# ── Intelligence Dashboard (Phase 2) ─────────────────────────────────────────

@app.get("/api/intelligence")
def get_intelligence(db: Session = Depends(get_db)):
    """Combined intelligence: topic performance, speaker deep-dive, campaign, ICP refinement."""
    import traceback
    try:
        return _get_intelligence_inner(db)
    except Exception:
        raise HTTPException(status_code=500, detail=traceback.format_exc()[-1500:])


def _get_intelligence_inner(db: Session):
    from sqlalchemy import text as _t

    # ── 1. Topic / ICP performance ──
    topic_perf = db.execute(_t("""
        SELECT
            COALESCE(w.icp, 'Others') AS icp,
            COUNT(*) AS webinar_count,
            COALESCE(SUM(reg.cnt), 0) AS total_regs,
            COALESCE(SUM(att.cnt), 0) AS total_att
        FROM webinars w
        LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM registrations GROUP BY webinar_id) reg ON reg.webinar_id = w.id
        LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM attendances WHERE attended=TRUE GROUP BY webinar_id) att ON att.webinar_id = w.id
        GROUP BY w.icp
        ORDER BY total_regs DESC
    """)).fetchall()

    icp_rows = []
    for r in topic_perf:
        regs = int(r.total_regs or 0)
        att = int(r.total_att or 0)
        rate = round(att / regs * 100, 1) if regs else 0
        icp_rows.append({
            "icp": r.icp,
            "webinar_count": int(r.webinar_count or 0),
            "total_regs": regs,
            "total_att": att,
            "attendance_rate": rate,
        })

    # ── 2. Speaker deep performance ──
    speaker_perf = db.execute(_t("""
        SELECT
            s.id, s.name,
            COUNT(DISTINCT w.id) AS webinars,
            COALESCE(SUM(reg.cnt), 0) AS total_regs,
            COALESCE(SUM(att.cnt), 0) AS total_att,
            AVG(reg.cnt) AS avg_regs_per_webinar
        FROM speakers s
        JOIN webinars w ON w.speaker_id = s.id OR w.co_speaker_id = s.id
        LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM registrations GROUP BY webinar_id) reg ON reg.webinar_id = w.id
        LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM attendances WHERE attended=TRUE GROUP BY webinar_id) att ON att.webinar_id = w.id
        WHERE w.status = 'completed'
        GROUP BY s.id, s.name
        HAVING COUNT(DISTINCT w.id) >= 2
        ORDER BY total_regs DESC
    """)).fetchall()

    spk_rows = []
    for r in speaker_perf:
        regs = int(r.total_regs or 0)
        att = int(r.total_att or 0)
        rate = round(att / regs * 100, 1) if regs else 0
        spk_rows.append({
            "id": r.id,
            "name": r.name,
            "webinars": int(r.webinars or 0),
            "total_regs": regs,
            "total_att": att,
            "attendance_rate": rate,
            "avg_regs_per_webinar": round(float(r.avg_regs_per_webinar or 0), 0),
        })

    # ── 3. Campaign learning: best day/time + budget tier ──
    # Best day of week
    day_rows = db.execute(_t("""
        SELECT w.date, COALESCE(reg.cnt, 0) AS regs, COALESCE(att.cnt, 0) AS att
        FROM webinars w
        LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM registrations GROUP BY webinar_id) reg ON reg.webinar_id = w.id
        LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM attendances WHERE attended=TRUE GROUP BY webinar_id) att ON att.webinar_id = w.id
        WHERE w.status = 'completed' AND w.date IS NOT NULL
    """)).fetchall()

    day_buckets: dict = {}  # day_of_week -> {regs, att, count}
    from datetime import date as _date, datetime as _dt
    for r in day_rows:
        try:
            d = r.date if hasattr(r.date, 'weekday') else _dt.fromisoformat(str(r.date).split(' ')[0]).date()
            dow = d.strftime("%A")
            if dow not in day_buckets:
                day_buckets[dow] = {"regs": 0, "att": 0, "count": 0}
            day_buckets[dow]["regs"] += int(r.regs or 0)
            day_buckets[dow]["att"]  += int(r.att or 0)
            day_buckets[dow]["count"] += 1
        except Exception:
            pass
    day_perf = [
        {
            "day": d,
            "webinars": v["count"],
            "avg_regs": round(v["regs"] / v["count"], 0) if v["count"] else 0,
            "avg_att": round(v["att"] / v["count"], 0) if v["count"] else 0,
            "attendance_rate": round(v["att"] / v["regs"] * 100, 1) if v["regs"] else 0,
        }
        for d, v in day_buckets.items()
    ]
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    day_perf.sort(key=lambda x: day_order.index(x["day"]))

    # ── 4. ICP refinement: email-domain analysis (Python-side aggregation) ──
    all_emails = db.execute(_t("""
        SELECT r.email, r.webinar_id
        FROM registrations r
        WHERE r.email IS NOT NULL AND r.email LIKE '%@%'
          AND r.email NOT LIKE '%@rhorizon.in'
    """)).fetchall()

    domain_buckets: dict = {}
    for row in all_emails:
        em = row.email.lower().strip()
        if '@' not in em: continue
        dom = em.split('@', 1)[1]
        if dom not in domain_buckets:
            domain_buckets[dom] = {"emails": set(), "webinars": set()}
        domain_buckets[dom]["emails"].add(em)
        domain_buckets[dom]["webinars"].add(row.webinar_id)

    domain_perf_list = sorted(
        [(d, len(v["emails"]), len(v["webinars"])) for d, v in domain_buckets.items() if len(v["emails"]) >= 3],
        key=lambda x: -x[1]
    )[:25]
    domain_perf = [type('R', (), {'domain': d, 'people': p, 'webinars_touched': w})() for d, p, w in domain_perf_list]

    domains = []
    for r in domain_perf:
        d = r.domain
        # Classify
        if d in ('gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'rediffmail.com', 'yahoo.co.in', 'yahoo.in', 'icloud.com'):
            kind = 'consumer'
        elif any(x in d for x in ('.gov.', '.gov', 'gov.in')):
            kind = 'government'
        elif any(x in d for x in ('.edu', '.ac.in', 'university')):
            kind = 'education'
        else:
            kind = 'business'
        domains.append({"domain": d, "people": int(r.people), "webinars": int(r.webinars_touched), "kind": kind})

    # Source breakdown (proxy for channel performance)
    source_perf = db.execute(_t("""
        SELECT
            COALESCE(r.source, 'unknown') AS source,
            COUNT(*) AS regs,
            COUNT(DISTINCT a.id) AS atts
        FROM registrations r
        LEFT JOIN attendances a ON a.registration_id = r.id AND a.attended = TRUE
        GROUP BY r.source
        ORDER BY regs DESC
    """)).fetchall()
    sources = []
    for r in source_perf:
        rg = int(r.regs); at = int(r.atts)
        sources.append({
            "source": r.source,
            "regs": rg,
            "atts": at,
            "rate": round(at/rg*100, 1) if rg else 0,
        })

    return {
        "topic_intelligence": icp_rows,
        "speaker_performance": spk_rows,
        "day_performance": day_perf,
        "domain_analysis": domains,
        "source_performance": sources,
        "total_webinars": sum(r["webinar_count"] for r in icp_rows),
    }


@app.get("/api/webinar-funnel/{webinar_id}")
def get_webinar_funnel(webinar_id: int, db: Session = Depends(get_db)):
    """Return funnel data for a single webinar: regs -> attendees -> follow-up."""
    from sqlalchemy import text as _t
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")

    regs = db.execute(_t("SELECT COUNT(*) FROM registrations WHERE webinar_id=:w"), {"w": webinar_id}).fetchone()[0]
    att = db.execute(_t("SELECT COUNT(*) FROM attendances WHERE webinar_id=:w AND attended=TRUE"), {"w": webinar_id}).fetchone()[0]

    # Check if ads exist for this webinar
    ads = db.execute(_t("SELECT SUM(impressions), SUM(clicks) FROM webinar_ads WHERE webinar_id=:w"), {"w": webinar_id}).fetchone()
    impressions = int(ads[0] or 0)
    clicks = int(ads[1] or 0)

    regs = int(regs or 0)
    att = int(att or 0)
    no_show = max(0, regs - att)

    # Pipeline follow-up count for attendees who have email
    att_emails = db.execute(_t("""
        SELECT r.email FROM attendances a
        JOIN registrations r ON r.id = a.registration_id
        WHERE a.webinar_id=:w AND a.attended=TRUE AND r.email IS NOT NULL
    """), {"w": webinar_id}).fetchall()
    att_email_list = [r.email for r in att_emails]

    followed_up = 0
    if att_email_list:
        placeholders = ','.join([f"'{e}'" for e in att_email_list[:100]])
        followed_up = db.execute(_t(f"SELECT COUNT(*) FROM pipeline_contacts WHERE email IN ({placeholders}) AND status NOT IN ('new')")).fetchone()[0] or 0

    stages = []
    if impressions > 0:
        stages.append({"label": "Impressions", "count": impressions, "pct": 100})
        click_pct = round(clicks/impressions*100, 1) if impressions else 0
        stages.append({"label": "Clicks", "count": clicks, "pct": click_pct, "drop": round(100-click_pct, 1)})
        reg_pct = round(regs/clicks*100, 1) if clicks else 0
        stages.append({"label": "Registrations", "count": regs, "pct": reg_pct, "drop": round(100-reg_pct, 1)})
    else:
        stages.append({"label": "Registrations", "count": regs, "pct": 100})

    att_pct = round(att/regs*100, 1) if regs else 0
    stages.append({"label": "Attendees", "count": att, "pct": att_pct, "drop": round(100-att_pct, 1)})

    fu_pct = round(followed_up/att*100, 1) if att else 0
    stages.append({"label": "Followed Up", "count": followed_up, "pct": fu_pct, "drop": round(100-fu_pct, 1)})

    # Generate insight
    insight = ""
    if att_pct < 25 and regs > 50:
        insight = f"Registrations are strong ({regs}), but only {att_pct}% attended. Review reminder timing and audience commitment."
    elif att_pct >= 50:
        insight = f"Excellent attendance rate of {att_pct}%. This webinar had strong audience commitment."
    elif att_pct >= 35:
        insight = f"Good attendance rate of {att_pct}%. Consider improving pre-webinar reminders to push above 50%."
    else:
        insight = f"Attendance rate of {att_pct}% is below target. Review topic relevance and reminder sequence."

    return {"webinar_id": webinar_id, "title": w.title, "stages": stages, "insight": insight, "has_ads": impressions > 0}


@app.get("/api/repeat-audience")
def get_repeat_audience(db: Session = Depends(get_db)):
    """Track first-time vs repeat registrants and attendees."""
    from sqlalchemy import text as _t

    # People who attended multiple webinars
    repeat_attendees = db.execute(_t("""
        SELECT r.email, r.attendee_name,
               COUNT(DISTINCT a.webinar_id) AS webinar_count,
               MAX(a.joined_at) AS last_seen
        FROM attendances a
        JOIN registrations r ON r.id = a.registration_id
        WHERE a.attended = TRUE AND r.email IS NOT NULL AND r.email NOT LIKE '%@rhorizon%'
        GROUP BY r.email, r.attendee_name
        HAVING COUNT(DISTINCT a.webinar_id) >= 2
        ORDER BY webinar_count DESC
        LIMIT 50
    """)).fetchall()

    # Total unique registrants
    total_unique_regs = db.execute(_t("""
        SELECT COUNT(DISTINCT email) FROM registrations WHERE email IS NOT NULL
    """)).fetchone()[0] or 0

    # Total unique attendees
    total_unique_att = db.execute(_t("""
        SELECT COUNT(DISTINCT r.email) FROM attendances a
        JOIN registrations r ON r.id = a.registration_id
        WHERE a.attended = TRUE AND r.email IS NOT NULL
    """)).fetchone()[0] or 0

    # People who registered but never attended
    never_attended = db.execute(_t("""
        SELECT COUNT(DISTINCT r.email) FROM registrations r
        WHERE r.email IS NOT NULL
        AND r.email NOT IN (
            SELECT DISTINCT r2.email FROM attendances a
            JOIN registrations r2 ON r2.id = a.registration_id
            WHERE a.attended = TRUE AND r2.email IS NOT NULL
        )
    """)).fetchone()[0] or 0

    repeat_list = [{
        "email": r.email,
        "name": r.attendee_name,
        "webinar_count": int(r.webinar_count),
        "last_seen": str(r.last_seen)[:10] if r.last_seen else None,
    } for r in repeat_attendees]

    repeat_count = len(repeat_list)

    return {
        "total_unique_registrants": int(total_unique_regs),
        "total_unique_attendees": int(total_unique_att),
        "repeat_attendees_count": repeat_count,
        "never_attended_count": int(never_attended),
        "repeat_attendees": repeat_list,
    }


@app.get("/api/topic-performance")
def get_topic_performance(db: Session = Depends(get_db)):
    """Per-ICP topic performance with best speaker and sub-topic suggestions."""
    from sqlalchemy import text as _t

    # Per ICP: webinar count, regs, attendees, attendance rate, best speaker
    icp_rows = db.execute(_t("""
        SELECT
            COALESCE(w.icp, 'Others') AS icp,
            COUNT(DISTINCT w.id) AS webinar_count,
            COALESCE(SUM(reg.cnt), 0) AS total_regs,
            COALESCE(SUM(att.cnt), 0) AS total_att,
            s.name AS top_speaker_name,
            s.id AS top_speaker_id
        FROM webinars w
        LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM registrations GROUP BY webinar_id) reg ON reg.webinar_id = w.id
        LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM attendances WHERE attended=TRUE GROUP BY webinar_id) att ON att.webinar_id = w.id
        LEFT JOIN speakers s ON s.id = w.speaker_id
        WHERE w.status = 'completed'
        GROUP BY w.icp
        ORDER BY total_att DESC
    """)).fetchall()

    # For each ICP, find the best speaker (highest att rate for that ICP)
    icp_data = []
    for r in icp_rows:
        regs = int(r.total_regs or 0)
        att = int(r.total_att or 0)
        rate = round(att/regs*100, 1) if regs else 0

        # Best speaker for this ICP
        best_spk = db.execute(_t("""
            SELECT s.name,
                   SUM(att.cnt) as total_att,
                   SUM(reg.cnt) as total_regs
            FROM webinars w
            JOIN speakers s ON s.id = w.speaker_id
            LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM registrations GROUP BY webinar_id) reg ON reg.webinar_id = w.id
            LEFT JOIN (SELECT webinar_id, COUNT(*) AS cnt FROM attendances WHERE attended=TRUE GROUP BY webinar_id) att ON att.webinar_id = w.id
            WHERE w.status='completed' AND COALESCE(w.icp,'Others')=:icp AND reg.cnt > 0
            GROUP BY s.name
            ORDER BY (CAST(att.cnt AS FLOAT)/reg.cnt) DESC
            LIMIT 1
        """), {"icp": r.icp or 'Others'}).fetchone()

        # Recent webinars for this ICP
        recent = db.execute(_t("""
            SELECT w.title, w.date, s.name as speaker,
                   (SELECT COUNT(*) FROM registrations WHERE webinar_id=w.id) as regs,
                   (SELECT COUNT(*) FROM attendances WHERE webinar_id=w.id AND attended=TRUE) as att
            FROM webinars w LEFT JOIN speakers s ON s.id=w.speaker_id
            WHERE COALESCE(w.icp,'Others')=:icp AND w.status='completed'
            ORDER BY w.date DESC LIMIT 3
        """), {"icp": r.icp or 'Others'}).fetchall()

        grade = 'A' if rate >= 40 else 'B' if rate >= 30 else 'C' if rate >= 20 else 'D'

        icp_data.append({
            "icp": r.icp or 'Others',
            "webinar_count": int(r.webinar_count or 0),
            "total_regs": regs,
            "total_att": att,
            "attendance_rate": rate,
            "grade": grade,
            "best_speaker": best_spk.name if best_spk else None,
            "recent_webinars": [
                {"title": x.title, "date": str(x.date), "speaker": x.speaker,
                 "regs": int(x.regs or 0), "att": int(x.att or 0),
                 "rate": round(int(x.att or 0)/int(x.regs or 1)*100, 1)}
                for x in recent
            ]
        })

    return {"topics": icp_data}


@app.get("/api/lead-quality")
def get_lead_quality(db: Session = Depends(get_db)):
    """Score each attendee by ICP match, attendance count, repeat attendance, follow-up status."""
    from sqlalchemy import text as _t

    rows = db.execute(_t("""
        SELECT r.email, r.attendee_name,
               COUNT(DISTINCT a.webinar_id) AS webinar_count,
               AVG(a.duration_minutes) AS avg_duration,
               MAX(COALESCE(w.icp,'Others')) AS primary_icp,
               MAX(a.joined_at) AS last_seen
        FROM attendances a
        JOIN registrations r ON r.id = a.registration_id
        JOIN webinars w ON w.id = a.webinar_id
        WHERE a.attended = TRUE AND r.email IS NOT NULL AND r.email NOT LIKE '%@rhorizon%'
        GROUP BY r.email, r.attendee_name
        ORDER BY webinar_count DESC, avg_duration DESC
        LIMIT 100
    """)).fetchall()

    # Get pipeline status for these emails
    emails = [r.email for r in rows]
    pipeline_map = {}
    if emails:
        placeholders = ','.join([f"'{e}'" for e in emails[:100]])
        pl_rows = db.execute(_t(f"SELECT email, status FROM pipeline_contacts WHERE email IN ({placeholders})")).fetchall()
        pipeline_map = {r.email: r.status for r in pl_rows}

    premium_icps = {'Family Office', 'AIF', 'PMS', 'NRI', 'ESOPs'}
    leads = []
    for r in rows:
        webinar_count = int(r.webinar_count or 0)
        avg_dur = float(r.avg_duration or 0)
        icp = r.primary_icp or 'Others'
        pl_status = pipeline_map.get(r.email, 'none')

        # Score 0-100
        score = 0
        score += min(30, webinar_count * 10)  # repeat attendance: up to 30
        score += min(25, round(avg_dur / 60 * 25)) if avg_dur else 0  # duration: up to 25
        score += 25 if icp in premium_icps else 10  # ICP: 25 for premium, 10 for others
        score += 20 if pl_status in ('meeting_booked', 'converted') else 10 if pl_status == 'contacted' else 0  # follow-up
        score = min(100, score)

        if score >= 70: quality = "High Quality"
        elif score >= 45: quality = "Medium Quality"
        elif score >= 25: quality = "Low Quality"
        else: quality = "Needs Review"

        leads.append({
            "email": r.email,
            "name": r.attendee_name,
            "webinar_count": webinar_count,
            "avg_duration_min": round(avg_dur, 0),
            "primary_icp": icp,
            "last_seen": str(r.last_seen)[:10] if r.last_seen else None,
            "pipeline_status": pl_status,
            "score": score,
            "quality": quality,
        })

    leads.sort(key=lambda x: -x['score'])
    return {"leads": leads, "total": len(leads)}


@app.get("/api/speaker-insights")
def get_speaker_insights(db: Session = Depends(get_db)):
    """Per-speaker: best topics, best ICP, performance trend."""
    from sqlalchemy import text as _t

    speakers = db.execute(_t("SELECT id, name, bio FROM speakers ORDER BY name")).fetchall()
    result = []

    for spk in speakers:
        # All completed webinars for this speaker
        webinars = db.execute(_t("""
            SELECT w.id, w.title, w.icp, w.date,
                   (SELECT COUNT(*) FROM registrations WHERE webinar_id=w.id) as regs,
                   (SELECT COUNT(*) FROM attendances WHERE webinar_id=w.id AND attended=TRUE) as att
            FROM webinars w
            WHERE (w.speaker_id=:id OR w.co_speaker_id=:id) AND w.status='completed'
            ORDER BY w.date DESC
        """), {"id": spk.id}).fetchall()

        if not webinars:
            continue

        wlist = []
        for w in webinars:
            regs = int(w.regs or 0); att = int(w.att or 0)
            rate = round(att/regs*100, 1) if regs else 0
            wlist.append({"id": w.id, "title": w.title, "icp": w.icp or 'Others',
                          "date": str(w.date), "regs": regs, "att": att, "rate": rate})

        # Best ICP (highest avg attendance rate)
        icp_map = {}
        for w in wlist:
            icp = w["icp"]
            if icp not in icp_map: icp_map[icp] = {"total": 0, "count": 0}
            icp_map[icp]["total"] += w["rate"]
            icp_map[icp]["count"] += 1
        best_icp = max(icp_map, key=lambda k: icp_map[k]["total"]/icp_map[k]["count"]) if icp_map else None

        # Best webinars (top 3 by rate)
        best_webinars = sorted(wlist, key=lambda x: -x["rate"])[:3]
        # Weak webinars (bottom 2 by rate with enough regs)
        weak_webinars = sorted([w for w in wlist if w["regs"] >= 30], key=lambda x: x["rate"])[:2]

        avg_rate = round(sum(w["rate"] for w in wlist) / len(wlist), 1) if wlist else 0
        total_regs = sum(w["regs"] for w in wlist)
        total_att = sum(w["att"] for w in wlist)

        result.append({
            "id": spk.id,
            "name": spk.name,
            "webinar_count": len(wlist),
            "total_regs": total_regs,
            "total_att": total_att,
            "avg_attendance_rate": avg_rate,
            "best_icp": best_icp,
            "best_webinars": best_webinars,
            "weak_webinars": weak_webinars,
            "recent_webinars": wlist[:5],
        })

    result.sort(key=lambda x: -x["avg_attendance_rate"])
    return {"speakers": result}


# ── Competitor Intelligence (Phase 3) ────────────────────────────────────────

@app.get("/api/competitors")
def list_competitors(db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT c.id, c.name, c.focus, c.website, c.color_hex,
               (SELECT COUNT(*) FROM competitor_activity ca WHERE ca.competitor_id = c.id) AS activity_count,
               (SELECT MAX(activity_date) FROM competitor_activity ca WHERE ca.competitor_id = c.id) AS last_activity
        FROM competitors c
        ORDER BY c.name
    """)).fetchall()
    return [{
        "id": r.id, "name": r.name, "focus": r.focus, "website": r.website,
        "color_hex": r.color_hex, "activity_count": int(r.activity_count or 0),
        "last_activity": str(r.last_activity) if r.last_activity else None,
    } for r in rows]


@app.get("/api/competitor-activity")
def list_competitor_activity(
    competitor_id: Optional[int] = Query(None),
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    from sqlalchemy import text as _t
    from datetime import date as _date, timedelta as _td
    cutoff = _date.today() - _td(days=days)
    where = "WHERE ca.activity_date >= :cutoff"
    params = {"cutoff": cutoff}
    if competitor_id:
        where += " AND ca.competitor_id = :cid"
        params["cid"] = competitor_id
    rows = db.execute(_t(f"""
        SELECT ca.id, ca.competitor_id, c.name AS competitor_name, c.color_hex,
               ca.activity_date, ca.format, ca.topic, ca.speaker,
               ca.audience_focus, ca.messaging_angle, ca.cta, ca.link, ca.notes
        FROM competitor_activity ca
        JOIN competitors c ON c.id = ca.competitor_id
        {where}
        ORDER BY ca.activity_date DESC, ca.id DESC
    """), params).fetchall()
    return [{
        "id": r.id, "competitor_id": r.competitor_id, "competitor": r.competitor_name,
        "color": r.color_hex, "date": str(r.activity_date), "format": r.format,
        "topic": r.topic, "speaker": r.speaker, "audience_focus": r.audience_focus,
        "messaging_angle": r.messaging_angle, "cta": r.cta, "link": r.link, "notes": r.notes,
    } for r in rows]


@app.post("/api/competitor-activity", status_code=201)
def add_competitor_activity(payload: dict, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    required = ("competitor_id", "activity_date", "topic")
    for k in required:
        if not payload.get(k):
            raise HTTPException(status_code=400, detail=f"{k} required")
    row = db.execute(_t("""
        INSERT INTO competitor_activity
        (competitor_id, activity_date, format, topic, speaker, audience_focus, messaging_angle, cta, link, notes)
        VALUES (:c, :d, :f, :t, :s, :a, :m, :ct, :l, :n)
        RETURNING id
    """) if _is_pg(db) else _t("""
        INSERT INTO competitor_activity
        (competitor_id, activity_date, format, topic, speaker, audience_focus, messaging_angle, cta, link, notes)
        VALUES (:c, :d, :f, :t, :s, :a, :m, :ct, :l, :n)
    """), {
        "c": int(payload["competitor_id"]),
        "d": payload["activity_date"],
        "f": payload.get("format") or "webinar",
        "t": payload["topic"].strip(),
        "s": (payload.get("speaker") or "").strip() or None,
        "a": payload.get("audience_focus") or None,
        "m": payload.get("messaging_angle") or None,
        "ct": payload.get("cta") or None,
        "l": (payload.get("link") or "").strip() or None,
        "n": (payload.get("notes") or "").strip() or None,
    })
    db.commit()
    return {"ok": True}


@app.post("/api/competitors", status_code=201)
def add_competitor(payload: dict, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    if _is_pg(db):
        row = db.execute(_t("INSERT INTO competitors (name, focus, website, color_hex) VALUES (:n,:f,:w,:c) RETURNING id"),
                         {"n": name, "f": payload.get("focus") or "", "w": payload.get("website") or "", "c": payload.get("color_hex") or "#6366f1"})
        cid = row.fetchone().id
    else:
        db.execute(_t("INSERT INTO competitors (name, focus, website, color_hex) VALUES (:n,:f,:w,:c)"),
                   {"n": name, "f": payload.get("focus") or "", "w": payload.get("website") or "", "c": payload.get("color_hex") or "#6366f1"})
        cid = db.execute(_t("SELECT last_insert_rowid()")).scalar()
    db.commit()
    return {"id": cid, "name": name}


@app.post("/api/competitor-research")
async def auto_research_competitor(payload: dict, db: Session = Depends(get_db)):
    """Use Perplexity web search to auto-research a competitor's recent webinar & content activity."""
    import os, json, httpx
    from datetime import date as _date, datetime as _dt

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

    from sqlalchemy import text as _t
    competitor_id = payload.get("competitor_id")
    if not competitor_id:
        raise HTTPException(status_code=400, detail="competitor_id required")

    comp = db.execute(_t("SELECT id, name, focus, website FROM competitors WHERE id = :id"), {"id": competitor_id}).fetchone()
    if not comp:
        raise HTTPException(status_code=404, detail="Competitor not found")

    today = _date.today().strftime("%B %d, %Y")
    site_hint = f"site:{comp.website}" if comp.website else ""

    try:
        search_resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content":
                    f"""Today is {today}. Based on your knowledge, describe the Indian financial advisory company "{comp.name}" ({comp.website or ''}).

What do you know about their recent webinars, events, content, or thought leadership from the past 6 months?

For each item describe:
- Approximate date or timeframe
- Topic/title
- Speaker name (if known)
- Target audience (HNI, NRI, retail, women, etc.)
- Key messaging angle or hook
- CTA or format (register, watch, download, webinar, LinkedIn post, etc.)

Also note: What topics are they pushing hardest? What audience segments? What differentiates them?

Be honest about what you know vs don't know. Only report what you are reasonably confident about."""}]
            },
            timeout=40.0
        )
        search_resp.raise_for_status()
        raw_research = search_resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    # Parse research into structured activity entries with Claude
    try:
        parse_resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content":
                    f"""Extract structured activity records from this research about "{comp.name}":

{raw_research}

Return a JSON array. Each item:
{{
  "activity_date": "YYYY-MM-DD",
  "format": "webinar|linkedin|youtube|report|event|other",
  "topic": "exact topic/title (max 120 chars)",
  "speaker": "name or null",
  "audience_focus": "HNI|NRI|retail|women|etc or null",
  "messaging_angle": "their key hook/angle in ≤80 chars or null",
  "cta": "register|watch|download|etc or null",
  "link": "URL or null",
  "notes": "one line summary of what makes this notable or null"
}}

If date is unknown, use today: {today[:10] if len(today) > 10 else _date.today().isoformat()}.
If fewer than 3 items found, still return what you found. Return [] if nothing concrete found.
Return ONLY valid JSON array."""}]
            },
            timeout=30.0
        )
        parse_resp.raise_for_status()
        raw2 = parse_resp.json()["choices"][0]["message"]["content"].strip()
        activities = _extract_json(raw2)
        if not isinstance(activities, list):
            activities = []
    except Exception:
        activities = []

    # Save to DB
    saved = 0
    for act in activities:
        try:
            db.execute(_t("""
                INSERT INTO competitor_activity
                (competitor_id, activity_date, format, topic, speaker, audience_focus, messaging_angle, cta, link, notes)
                VALUES (:c, :d, :f, :t, :s, :a, :m, :ct, :l, :n)
            """), {
                "c": competitor_id,
                "d": act.get("activity_date") or _date.today().isoformat(),
                "f": act.get("format") or "other",
                "t": (act.get("topic") or "")[:120],
                "s": act.get("speaker"),
                "a": act.get("audience_focus"),
                "m": act.get("messaging_angle"),
                "ct": act.get("cta"),
                "l": act.get("link"),
                "n": act.get("notes"),
            })
            saved += 1
        except Exception:
            continue
    db.commit()

    return {
        "competitor": comp.name,
        "activities_found": len(activities),
        "activities_saved": saved,
        "raw_research": raw_research,
    }


@app.get("/api/competitor-research/weekly")
async def weekly_competitor_research(db: Session = Depends(get_db)):
    """Vercel cron endpoint — runs every Monday to auto-research all competitors."""
    import os, json, httpx
    from datetime import date as _date, datetime as _dt
    from sqlalchemy import text as _t

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "OPENROUTER_API_KEY not configured"}

    comps = db.execute(_t("SELECT id, name, website, focus FROM competitors ORDER BY name")).fetchall()
    results = []

    for comp in comps:
        today = _date.today().strftime("%B %d, %Y")
        try:
            search_resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                         "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
                json={
                    "model": "anthropic/claude-sonnet-4-5",
                    "max_tokens": 1200,
                    "messages": [{"role": "user", "content":
                        f"""Today is {today}. Based on your knowledge, describe "{comp.name}" ({comp.website or ''}).

What recent webinars, events, content or thought leadership have they done in the past 3 months? Focus: Indian wealth advisory, HNI/NRI, PMS, financial planning.

For each item describe: approximate date, topic/title, target audience, key messaging angle.

Only report what you are reasonably confident about. Keep it concise."""}]
                },
                timeout=30.0
            )
            search_resp.raise_for_status()
            raw_research = search_resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            results.append({"competitor": comp.name, "error": str(e)})
            continue

        try:
            parse_resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                         "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
                json={
                    "model": "anthropic/claude-sonnet-4-5",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content":
                        f"""Extract activity records from this research about "{comp.name}":

{raw_research}

Return JSON array. Each item:
{{"activity_date":"YYYY-MM-DD","format":"webinar|linkedin|youtube|report|event|other","topic":"title max 120 chars","speaker":null,"audience_focus":"HNI|NRI|retail|etc","messaging_angle":"key hook max 80 chars","cta":null,"link":null,"notes":"one line"}}

Use today {_date.today().isoformat()} if date unknown. Return [] if nothing concrete. ONLY valid JSON array."""}]
                },
                timeout=25.0
            )
            parse_resp.raise_for_status()
            raw2 = parse_resp.json()["choices"][0]["message"]["content"].strip()
            activities = _extract_json(raw2)
            if not isinstance(activities, list):
                activities = []
        except Exception:
            activities = []

        saved = 0
        for act in activities:
            try:
                existing = db.execute(_t(
                    "SELECT id FROM competitor_activity WHERE competitor_id=:cid AND topic=:t AND activity_date=:d"
                ), {"cid": comp.id, "t": str(act.get("topic",""))[:200], "d": str(act.get("activity_date",""))}).fetchone()
                if existing:
                    continue
                db.execute(_t("""
                    INSERT INTO competitor_activity
                    (competitor_id, activity_date, format, topic, speaker, audience_focus, messaging_angle, cta, link, notes)
                    VALUES (:cid,:d,:fmt,:topic,:spk,:aud,:angle,:cta,:link,:notes)
                """), {
                    "cid": comp.id,
                    "d": str(act.get("activity_date",""))[:10] or str(_date.today()),
                    "fmt": str(act.get("format","other"))[:50],
                    "topic": str(act.get("topic",""))[:200],
                    "spk": str(act.get("speaker",""))[:100] if act.get("speaker") else None,
                    "aud": str(act.get("audience_focus",""))[:100] if act.get("audience_focus") else None,
                    "angle": str(act.get("messaging_angle",""))[:200] if act.get("messaging_angle") else None,
                    "cta": str(act.get("cta",""))[:100] if act.get("cta") else None,
                    "link": str(act.get("link",""))[:500] if act.get("link") else None,
                    "notes": str(act.get("notes",""))[:500] if act.get("notes") else None,
                })
                db.commit()
                saved += 1
            except Exception:
                db.rollback()

        results.append({"competitor": comp.name, "found": len(activities), "saved": saved})

    return {"ran_at": _date.today().isoformat(), "results": results}



@app.get("/api/intelligence/insights")
async def get_intelligence_insights(db: Session = Depends(get_db)):
    """AI-generated written insights from the intelligence data."""
    import os, httpx
    from sqlalchemy import text as _t

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

    # Pull key metrics for AI to analyze
    top_icp = db.execute(_t("""
        SELECT COALESCE(w.icp,'Others') AS icp, COUNT(*) AS webinars,
               SUM((SELECT COUNT(*) FROM registrations r WHERE r.webinar_id=w.id)) AS regs,
               SUM((SELECT COUNT(*) FROM attendances a WHERE a.webinar_id=w.id AND a.attended=TRUE)) AS att
        FROM webinars w WHERE w.status='completed' GROUP BY w.icp ORDER BY regs DESC
    """)).fetchall()

    top_speakers = db.execute(_t("""
        SELECT s.name,
               COUNT(w.id) AS webinars,
               SUM((SELECT COUNT(*) FROM registrations r WHERE r.webinar_id=w.id)) AS regs,
               SUM((SELECT COUNT(*) FROM attendances a WHERE a.webinar_id=w.id AND a.attended=TRUE)) AS att
        FROM speakers s JOIN webinars w ON w.speaker_id=s.id WHERE w.status='completed'
        GROUP BY s.name ORDER BY att DESC
    """)).fetchall()

    recent = db.execute(_t("""
        SELECT w.title, w.date,
               (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id=w.id) AS regs,
               (SELECT COUNT(*) FROM attendances a WHERE a.webinar_id=w.id AND a.attended=TRUE) AS att
        FROM webinars w WHERE w.status='completed' ORDER BY w.date DESC LIMIT 5
    """)).fetchall()

    icp_summary = "; ".join(
        f"{r.icp}: {r.webinars} webinars, {r.regs} regs, {r.att} att ({round(r.att/r.regs*100,1) if r.regs else 0}% rate)"
        for r in top_icp
    )
    spk_summary = "; ".join(
        f"{r.name}: {r.webinars} webinars, {r.regs} regs, {r.att} att ({round(r.att/r.regs*100,1) if r.regs else 0}% rate)"
        for r in top_speakers
    )
    recent_summary = "; ".join(
        f"[{r.date}] {r.title}: {r.regs} regs, {r.att} att ({round(r.att/r.regs*100,1) if r.regs else 0}%)"
        for r in recent
    )

    # Pull all data needed for comprehensive insights
    # Top webinars by score
    all_webinars = db.execute(_t("""
        SELECT w.id, w.title, w.icp, w.date, s.name as speaker_name,
               (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id=w.id) AS regs,
               (SELECT COUNT(*) FROM attendances a WHERE a.webinar_id=w.id AND a.attended=TRUE) AS att
        FROM webinars w LEFT JOIN speakers s ON s.id=w.speaker_id
        WHERE w.status='completed'
        ORDER BY w.date DESC
    """)).fetchall()

    webinar_lines = []
    for r in all_webinars:
        regs = int(r.regs or 0); att = int(r.att or 0)
        rate = round(att/regs*100,1) if regs else 0
        score = _compute_perf_score(regs, rate, r.icp or 'Others')
        webinar_lines.append(f"  [{r.date}] \"{r.title}\" | ICP:{r.icp or 'Others'} | Speaker:{r.speaker_name or 'Unknown'} | Regs:{regs} | Att:{att} | Rate:{rate}% | Score:{score}/100")

    # Check ads data
    has_ads = db.execute(_t("SELECT COUNT(*) FROM webinar_ads")).fetchone()[0] > 0
    ads_summary = ""
    if has_ads:
        ads_rows = db.execute(_t("""
            SELECT platform, SUM(spend::numeric) as spend, SUM(impressions) as impr,
                   SUM(clicks) as clicks, SUM(conversions) as conv
            FROM webinar_ads WHERE spend IS NOT NULL AND spend != ''
            GROUP BY platform ORDER BY spend DESC
        """)).fetchall()
        if ads_rows:
            ads_summary = "ADS DATA:\n" + "\n".join(
                f"  {r.platform}: spend={r.spend}, impressions={r.impr}, clicks={r.clicks}, conversions={r.conv}"
                for r in ads_rows
            )

    prompt = f"""You are a senior marketing analyst for Right Horizons, an Indian financial advisory firm running HNI/NRI webinars.

WEBINAR DATA (all completed webinars, newest first):
{chr(10).join(webinar_lines) if webinar_lines else 'No completed webinars yet.'}

ICP PERFORMANCE: {icp_summary}
SPEAKER PERFORMANCE: {spk_summary}
RECENT WEBINARS: {recent_summary}

Generate EXACTLY 4 structured insights as a JSON array with these exact types in this order:
1. type="overall" — Where the biggest drop happens in the programme funnel. Cite specific numbers.
2. type="funnel" — Registration vs attendance pattern. Which ICPs or webinars convert best vs worst.
3. type="lead_quality" — Comment on audience profile quality based on ICP data. Are the right HNI/NRI segments attending?
4. type="recommendation" — One clear action on the weakest stage. Be specific: topic, ICP, format, or channel to fix.

Rules:
- Every insight MUST cite a specific number from the data
- Be direct and prescriptive for an HNI wealth advisory context
- Do not mention spend, CPL, impressions, or ads unless ads data is explicitly provided
- Focus on registrations, attendance rates, ICP distribution, and speaker performance only
{f'- Ads data available: {ads_summary}' if has_ads else ''}

Return ONLY a valid JSON array of exactly 4 objects:
[
  {{
    "type": "overall|funnel|lead_quality|recommendation",
    "headline": "Bold specific claim ≤65 chars",
    "detail": "2-3 sentences with specific numbers and clear business implication.",
    "action": "One specific, actionable next step ≤90 chars",
    "metric": "The key stat e.g. '47% attendance rate'"
  }}
]"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={"model": "anthropic/claude-sonnet-4-5", "max_tokens": 1500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        insights = _extract_json(raw)
        return {"insights": insights}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insights failed: {e}")


@app.get("/api/intelligence/hot-leads")
def get_hot_leads(db: Session = Depends(get_db)):
    """Attendees who stayed 30+ min but are NOT yet in pipeline (or still status='new').
    Also returns repeat attendees (attended 2+ webinars).
    These are the highest-intent leads to follow up with."""
    from sqlalchemy import text as _t

    # Hot leads: attended 30+ min, not in pipeline (or new only)
    hot = db.execute(_t("""
        SELECT
            r.attendee_name AS name,
            r.email,
            w.title AS webinar_title,
            w.date AS webinar_date,
            COALESCE(w.icp, 'Others') AS icp,
            a.duration_minutes,
            COALESCE(p.status, 'not_added') AS pipeline_status
        FROM attendances a
        JOIN registrations r ON r.id = a.registration_id
        JOIN webinars w ON w.id = a.webinar_id
        LEFT JOIN pipeline_contacts p ON p.email = r.email
        WHERE a.attended = TRUE
          AND a.duration_minutes >= 30
          AND r.email IS NOT NULL
          AND (p.id IS NULL OR p.status = 'new')
        ORDER BY a.duration_minutes DESC, w.date DESC
        LIMIT 100
    """)).fetchall()

    # Repeat attendees: attended 2+ different webinars
    repeat = db.execute(_t("""
        SELECT
            r.attendee_name AS name,
            r.email,
            COUNT(DISTINCT a.webinar_id) AS webinar_count,
            MAX(a.duration_minutes) AS max_duration,
            (SELECT GROUP_CONCAT(DISTINCT COALESCE(w2.icp,'Others')) FROM attendances a2 JOIN registrations r2 ON r2.id=a2.registration_id JOIN webinars w2 ON w2.id=a2.webinar_id WHERE a2.attended=TRUE AND r2.email=r.email) AS icps,
            COALESCE(p.status, 'not_added') AS pipeline_status
        FROM attendances a
        JOIN registrations r ON r.id = a.registration_id
        JOIN webinars w ON w.id = a.webinar_id
        LEFT JOIN pipeline_contacts p ON p.email = r.email
        WHERE a.attended = TRUE AND r.email IS NOT NULL
        GROUP BY r.attendee_name, r.email, p.status
        HAVING COUNT(DISTINCT a.webinar_id) >= 2
        ORDER BY webinar_count DESC, max_duration DESC
        LIMIT 50
    """)).fetchall()

    # Summary stats
    total_attendees = db.execute(_t(
        "SELECT COUNT(DISTINCT r.email) FROM attendances a "
        "JOIN registrations r ON r.id=a.registration_id WHERE a.attended=TRUE AND r.email IS NOT NULL"
    )).scalar() or 0

    in_pipeline = db.execute(_t(
        "SELECT COUNT(DISTINCT email) FROM pipeline_contacts WHERE status != 'new'"
    )).scalar() or 0

    return {
        "hot_leads": [dict(r._mapping) for r in hot],
        "repeat_attendees": [dict(r._mapping) for r in repeat],
        "total_unique_attendees": total_attendees,
        "in_pipeline": in_pipeline,
    }


@app.delete("/api/competitor-activity/{activity_id}", status_code=204)
def delete_competitor_activity(activity_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    db.execute(_t("DELETE FROM competitor_activity WHERE id = :id"), {"id": activity_id})
    db.commit()


def _is_pg(db: Session) -> bool:
    try:
        return 'postgres' in str(db.bind.url).lower()
    except Exception:
        return False


@app.get("/api/competitor-gap-analysis")
async def competitor_gap_analysis(db: Session = Depends(get_db)):
    """AI-powered gap analysis: where Right Horizons can win vs competitor activity."""
    import os, httpx, traceback
    from sqlalchemy import text as _t
    from datetime import date as _date, timedelta as _td

    try:
        cutoff = _date.today() - _td(days=90)
        # Recent competitor activity
        comp_rows = db.execute(_t("""
            SELECT c.name AS competitor, ca.activity_date, ca.format, ca.topic,
                   ca.audience_focus, ca.messaging_angle, ca.cta
            FROM competitor_activity ca
            JOIN competitors c ON c.id = ca.competitor_id
            WHERE ca.activity_date >= :cutoff
            ORDER BY ca.activity_date DESC
        """), {"cutoff": cutoff}).fetchall()

        # Recent RH webinars (last 90d)
        rh_rows = db.execute(_t("""
            SELECT w.title, w.date, COALESCE(s.name, 'Unknown') AS speaker, COALESCE(w.icp, 'Others') AS icp
            FROM webinars w LEFT JOIN speakers s ON s.id = w.speaker_id
            WHERE w.date >= :cutoff AND w.status = 'completed'
            ORDER BY w.date DESC
        """), {"cutoff": cutoff}).fetchall()

        comp_block = "\n".join(
            f"  [{r.activity_date}] {r.competitor} | {r.format} | {r.topic}"
            f" | Audience: {r.audience_focus or '-'} | Angle: {r.messaging_angle or '-'} | CTA: {r.cta or '-'}"
            for r in comp_rows
        )
        rh_block = "\n".join(
            f"  [{r.date}] {r.title} | {r.speaker} | ICP: {r.icp}"
            for r in rh_rows
        )

        if not comp_rows:
            return {
                "analysis": None,
                "message": "No competitor activity logged yet. Use 'Log Competitor Activity' to add real observations. AI gap analysis requires at least 5 entries to produce useful insights.",
                "competitor_activity_count": 0,
                "rh_activity_count": len(rh_rows),
            }
        if len(comp_rows) < 5:
            return {
                "analysis": None,
                "message": f"Only {len(comp_rows)} competitor entries logged. Need at least 5 to generate meaningful gap analysis. Add more real observations.",
                "competitor_activity_count": len(comp_rows),
                "rh_activity_count": len(rh_rows),
            }

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

        prompt = f"""You are a competitive intelligence analyst for Right Horizons, an Indian wealth advisory firm.

Compare what competitors did in the last 90 days versus what Right Horizons did. Identify SPECIFIC gaps and opportunities.

COMPETITOR ACTIVITY (last 90 days):
{comp_block}

RIGHT HORIZONS WEBINARS (last 90 days):
{rh_block}

Return ONLY this JSON shape (no markdown):

{{
  "topic_gaps": [
    {{ "theme": "specific theme name", "what_competitors_did": "1 sentence with examples cited from the data", "rh_did": "1 sentence on what RH did or 'nothing covered'", "recommendation": "1 specific action" }}
  ],
  "audience_gaps": [
    {{ "audience": "audience segment", "competitors_targeting": "list which competitors", "rh_targeting": "did RH target them?", "recommendation": "1 specific move" }}
  ],
  "format_gaps": [
    {{ "format": "format type", "observation": "what competitors used", "recommendation": "should RH adopt?" }}
  ],
  "speaker_positioning": "1 sentence: how should RH position its speakers vs competitor speakers, citing 1 competitor by name",
  "headline_opportunity": "ONE crisp sentence: the single biggest gap RH should attack next quarter"
}}

STRICT RULES (absolute, no exceptions):
- Use ONLY what is in the COMPETITOR ACTIVITY and RIGHT HORIZONS WEBINARS data above. NEVER assume what competitors might do, never reference public information about these firms beyond what is logged, never extrapolate to broader patterns.
- If a topic/audience/format is not represented in the logged competitor data, you MUST NOT mention it. Only analyze what is literally present in the data above.
- Every claim must cite a specific row from the data (e.g. "Nuvama Wealth ran 'AIF Cat-3 vs PMS' on 2026-05-18").
- If there are fewer than 2 examples of a pattern in the data, do NOT call it a gap. Say "insufficient data to identify a gap" instead.
- Be specific, no generic recommendations. No suggestions that aren't grounded in the data shown.
- NEVER use em dashes. Use commas, periods, colons, parentheses instead.
- Avoid filler words: consider, leverage, utilize, optimize, enhance.
- Each recommendation must propose a SPECIFIC tactic tied to a specific competitor activity row, not a generic best practice."""

        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={"model": "anthropic/claude-sonnet-4-5", "max_tokens": 2500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        try:
            analysis = _strip_em_dashes(_extract_json(raw))
        except ValueError:
            # Return raw preview so we can debug
            return {
                "analysis": None,
                "raw_preview": raw[:600],
                "competitor_activity_count": len(comp_rows),
                "rh_activity_count": len(rh_rows),
                "message": "AI response could not be parsed. Showing raw preview for debug.",
            }
        return {
            "analysis": analysis,
            "competitor_activity_count": len(comp_rows),
            "rh_activity_count": len(rh_rows),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail=traceback.format_exc()[-1500:])


# ── Lead Tags (manual classification overrides) ──────────────────────────────

@app.get("/api/lead-tags")
def list_lead_tags(db: Session = Depends(get_db)):
    from sqlalchemy import text as _text
    rows = db.execute(_text("SELECT email, tag, note, updated_at FROM lead_tags ORDER BY updated_at DESC")).fetchall()
    return [{"email": r.email, "tag": r.tag, "note": r.note, "updated_at": str(r.updated_at)} for r in rows]


@app.put("/api/lead-tags/{email}")
def upsert_lead_tag(email: str, payload: dict, db: Session = Depends(get_db)):
    from sqlalchemy import text as _text
    tag = (payload.get("tag") or "").strip().lower()
    note = (payload.get("note") or "").strip()
    if tag not in ("customer", "prospect", "partner", "employee", "internal", "meeting_ready", ""):
        raise HTTPException(status_code=400, detail="Invalid tag")
    email_l = email.lower().strip()
    if tag == "":
        db.execute(_text("DELETE FROM lead_tags WHERE email = :e"), {"e": email_l})
    else:
        # Upsert (works on both SQLite and Postgres)
        existing = db.execute(_text("SELECT id FROM lead_tags WHERE email = :e"), {"e": email_l}).fetchone()
        if existing:
            db.execute(_text("UPDATE lead_tags SET tag=:t, note=:n, updated_at=CURRENT_TIMESTAMP WHERE email=:e"),
                       {"t": tag, "n": note, "e": email_l})
        else:
            db.execute(_text("INSERT INTO lead_tags (email, tag, note) VALUES (:e, :t, :n)"),
                       {"e": email_l, "t": tag, "n": note})
    db.commit()
    return {"email": email_l, "tag": tag or None, "note": note or None}


# ── Leaderboard CSV Export ───────────────────────────────────────────────────

@app.get("/api/leaderboard/export")
def export_leaderboard(
    speaker_id: Optional[int] = Query(None),
    webinar_id: Optional[int] = Query(None),
    min_score: Optional[int] = Query(None),
    max_score: Optional[int] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    """Export leaderboard data reflecting current filters (limit, speaker, webinar, score range)."""
    from sqlalchemy import text as _text

    # Get the same data the /api/leaderboard endpoint returns
    where = ["a.attended = TRUE"]
    params: dict = {}
    if speaker_id:
        where.append("w.speaker_id = :spk")
        params["spk"] = speaker_id
    if webinar_id:
        where.append("w.id = :wid")
        params["wid"] = webinar_id

    where_clause = " AND ".join(where)

    sql = _text(f"""
        SELECT
            MIN(r.attendee_name) AS name,
            r.email,
            MIN(r.phone)         AS phone,
            COUNT(DISTINCT a.webinar_id) AS webinars_attended,
            COALESCE(SUM(a.duration_minutes), 0) AS total_duration_minutes,
            AVG(a.duration_minutes) AS avg_duration
        FROM registrations r
        JOIN attendances a ON a.registration_id = r.id
        JOIN webinars w    ON w.id = r.webinar_id
        WHERE {where_clause}
          AND r.email IS NOT NULL AND r.email <> ''
        GROUP BY r.email
        ORDER BY webinars_attended DESC, total_duration_minutes DESC
    """)
    rows = db.execute(sql, params).fetchall()

    # Calculate scores
    entries = []
    for row in rows:
        n = int(row.webinars_attended or 0)
        avg_dur = float(row.avg_duration or 0)
        bonus = 5 if avg_dur >= 60 else 3 if avg_dur >= 45 else 1 if avg_dur >= 30 else 0
        score = n * (10 + bonus)
        if min_score is not None and score < min_score: continue
        if max_score is not None and score > max_score: continue
        entries.append({
            "name": row.name or "",
            "email": row.email or "",
            "phone": row.phone or "",
            "webinars_attended": n,
            "total_min": int(row.total_duration_minutes or 0),
            "avg_min": round(avg_dur, 1),
            "score": score,
        })

    # Apply the same limit shown on the leaderboard UI
    entries = entries[:limit]

    # For each entry, fetch the actual webinar titles attended
    emails = [e["email"] for e in entries]
    webinar_titles_by_email: dict[str, list[str]] = {}
    if emails:
        # Chunk into batches for very large lists
        for i in range(0, len(emails), 200):
            batch = emails[i:i+200]
            placeholders = {f"e{k}": v for k, v in enumerate(batch)}
            ph_str = ",".join(f":e{k}" for k in range(len(batch)))
            q = _text(f"""
                SELECT r.email, w.title, w.date
                FROM registrations r
                JOIN attendances a ON a.registration_id = r.id
                JOIN webinars w    ON w.id = r.webinar_id
                WHERE a.attended = TRUE
                  AND r.email IN ({ph_str})
                ORDER BY w.date DESC
            """)
            for r in db.execute(q, placeholders).fetchall():
                webinar_titles_by_email.setdefault(r.email, []).append(f"{r.title} ({r.date})")

    # Fetch readiness + manual tags for these emails
    emails_lower = [e["email"].lower() for e in entries if e["email"]]
    tag_map: dict = {}
    if emails_lower:
        placeholders = {f"e{i}": e for i, e in enumerate(emails_lower)}
        ph_str = ",".join(f":e{i}" for i in range(len(emails_lower)))
        for t in db.execute(_text(f"SELECT email, tag FROM lead_tags WHERE email IN ({ph_str})"), placeholders).fetchall():
            tag_map[t.email.lower()] = t.tag

    from datetime import date as _date
    today = _date.today()

    def readiness_for(email_l, e):
        manual = tag_map.get(email_l)
        if manual in ('customer','internal','employee','partner'): return manual
        if email_l.endswith('@righthorizons.com'): return "internal"
        # Get last_date for this person
        avg_dur = e["avg_min"]
        att = e["webinars_attended"]
        # Approximation: we'd need to re-query for last_date but skip for export speed
        if att >= 3 and avg_dur >= 30: return "hot"
        if att >= 2 or avg_dur >= 45: return "warm"
        return "cold"

    # Build CSV
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Rank", "Name", "Email", "Phone", "Webinars Attended", "Total Minutes",
                     "Avg Minutes/Session", "Score", "Readiness", "Manual Tag", "Webinar List"])
    for idx, e in enumerate(entries, 1):
        email_l = (e["email"] or "").lower()
        readiness = readiness_for(email_l, e)
        manual_tag = tag_map.get(email_l, "")
        titles = " | ".join(webinar_titles_by_email.get(e["email"], []))
        writer.writerow([idx, e["name"], e["email"], e["phone"], e["webinars_attended"],
                         e["total_min"], e["avg_min"], e["score"], readiness, manual_tag, titles])

    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leaderboard_export.csv"'},
    )


# ── AI helpers ────────────────────────────────────────────────────────────────

def _strip_em_dashes(obj):
    """Recursively replace em dashes and en dashes with commas in any string within a JSON structure."""
    if isinstance(obj, str):
        return obj.replace("—", ", ").replace("–", ", ").replace(" - ", ", ")
    if isinstance(obj, list):
        return [_strip_em_dashes(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_em_dashes(v) for k, v in obj.items()}
    return obj


def _extract_json(text: str):
    """Robust JSON extractor: handles markdown code fences, leading text, and trailing commas."""
    import json, re
    if not text:
        raise ValueError("empty response")
    s = text.strip()
    # Strip code fences
    if s.startswith("```"):
        # Find content between first and last ```
        s = re.sub(r"^```[a-z]*\s*", "", s, count=1)
        s = re.sub(r"\s*```\s*$", "", s, count=1)
    # Find the first JSON object or array
    obj_start = s.find("{")
    arr_start = s.find("[")
    if obj_start == -1 and arr_start == -1:
        raise ValueError("no JSON found")
    if arr_start != -1 and (obj_start == -1 or arr_start < obj_start):
        start, open_c, close_c = arr_start, "[", "]"
    else:
        start, open_c, close_c = obj_start, "{", "}"
    # Walk to the matching close bracket (handles nested structures + string escapes)
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(start, len(s)):
        ch = s[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == open_c:
            depth += 1
        elif ch == close_c:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        raise ValueError("unbalanced JSON brackets")
    candidate = s[start:end]
    # Remove trailing commas before } or ]
    candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
    return json.loads(candidate)


# ── AI Chatbot ───────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(payload: dict, db: Session = Depends(get_db)):
    """Answer questions about webinar data using AI + live DB context."""
    import os, json, httpx
    from sqlalchemy import text

    question = (payload.get("question") or "").strip()
    history   = payload.get("history") or []   # list of {role, content}
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

    # ── Pull live context from DB ─────────────────────────────────────────────
    stats = db.execute(text("""
        SELECT
          COUNT(*) as total_webinars,
          SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
          SUM(CASE WHEN status='incomplete' THEN 1 ELSE 0 END) as incomplete
        FROM webinars
    """)).fetchone()

    speaker_stats = db.execute(text("""
        SELECT s.name,
          COUNT(w.id) as webinars,
          SUM((SELECT COUNT(*) FROM registrations r WHERE r.webinar_id=w.id)) as total_regs,
          SUM((SELECT COUNT(*) FROM attendances a WHERE a.webinar_id=w.id AND a.attended=TRUE)) as total_att
        FROM speakers s JOIN webinars w ON w.speaker_id=s.id
        GROUP BY s.name ORDER BY webinars DESC
    """)).fetchall()

    icp_stats = db.execute(text("""
        SELECT COALESCE(icp,'Others') as icp, COUNT(*) as cnt
        FROM webinars GROUP BY icp ORDER BY cnt DESC
    """)).fetchall()

    top_webinars = db.execute(text("""
        SELECT w.title, w.date, s.name as speaker,
          COALESCE(w.icp,'Others') as icp,
          (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id=w.id) as regs,
          (SELECT COUNT(*) FROM attendances a WHERE a.webinar_id=w.id AND a.attended=TRUE) as att
        FROM webinars w LEFT JOIN speakers s ON s.id=w.speaker_id
        ORDER BY regs DESC LIMIT 10
    """)).fetchall()

    recent = db.execute(text("""
        SELECT w.title, w.date, s.name as speaker, COALESCE(w.icp,'Others') as icp, w.status
        FROM webinars w LEFT JOIN speakers s ON s.id=w.speaker_id
        ORDER BY w.date DESC LIMIT 8
    """)).fetchall()

    # Build context string
    ctx_parts = [
        f"Platform: {stats.total_webinars} total webinars ({stats.completed} completed, {stats.incomplete} incomplete)",
        "\nSpeaker performance:",
    ]
    for sp in speaker_stats:
        att_rate = round(sp.total_att / sp.total_regs * 100, 1) if sp.total_regs else 0
        ctx_parts.append(f"  {sp.name}: {sp.webinars} webinars, {sp.total_regs} total regs, {att_rate}% avg attendance")

    ctx_parts.append("\nICP breakdown:")
    for icp in icp_stats:
        ctx_parts.append(f"  {icp.icp}: {icp.cnt} webinars")

    ctx_parts.append("\nTop 10 webinars by registrations:")
    for w in top_webinars:
        rate = round(w.att / w.regs * 100, 1) if w.regs else 0
        ctx_parts.append(f"  [{w.date}] {w.title[:55]} | Speaker: {w.speaker} | ICP: {w.icp} | Regs: {w.regs} | Att: {w.att} ({rate}%)")

    ctx_parts.append("\nMost recent 8 webinars:")
    for w in recent:
        ctx_parts.append(f"  [{w.date}] {w.title[:55]} | {w.speaker} | {w.icp} | {w.status}")

    # All webinars index (compact list so AI can answer first/last/specific date questions)
    all_webinars = db.execute(text("""
        SELECT w.title, w.date, COALESCE(s.name,'Unknown') as speaker, COALESCE(w.icp,'Others') as icp, w.status
        FROM webinars w LEFT JOIN speakers s ON s.id=w.speaker_id
        ORDER BY w.date ASC
    """)).fetchall()
    ctx_parts.append(f"\nALL {len(all_webinars)} WEBINARS (chronological, earliest first):")
    for i, w in enumerate(all_webinars, 1):
        ctx_parts.append(f"  #{i} [{w.date}] {w.title} | {w.speaker} | {w.icp}")

    # ── Person lookup: detect names/emails in the question and fetch their data
    import re
    q_lower = question.lower()
    person_block = []

    # Detect email addresses
    emails_in_q = re.findall(r'\b[\w\.\-]+@[\w\.\-]+\.\w+\b', question)

    # Detect capitalised name candidates (2+ capitalised words, or single name if context hints)
    name_candidates = re.findall(r'\b([A-Z][a-z]{2,})(?:\s+([A-Z][a-z]{2,}))?(?:\s+([A-Z][a-z]{2,}))?', question)
    # Flatten and remove empties + common false positives
    STOPWORDS = {'What','When','Which','Who','How','Why','Where','The','This','That','First','Last','Top','Show','Tell','Give','List','Find','Webinar','Speaker','Attendance','Registration','Right','Horizons','Right Horizons','WebinarIQ','PMS','NRI','ICP','SIP','SWP','ESOPs'}
    candidates = []
    for tup in name_candidates:
        parts = [p for p in tup if p and p not in STOPWORDS]
        if parts:
            full = ' '.join(parts)
            if full not in STOPWORDS:
                candidates.append(full)

    # Build search patterns
    search_terms = list(set(emails_in_q + candidates))

    found_people = []
    for term in search_terms[:5]:  # cap to 5 lookups
        term_lower = term.lower().strip()
        if len(term_lower) < 3: continue

        # Lookup by email or name match in registrations
        try:
            rows = db.execute(text("""
                SELECT
                    MIN(r.attendee_name) AS name,
                    r.email,
                    MIN(r.phone) AS phone,
                    COUNT(DISTINCT CASE WHEN a.attended=TRUE THEN a.webinar_id END) AS attended_count,
                    COUNT(DISTINCT r.webinar_id) AS registered_count
                FROM registrations r
                LEFT JOIN attendances a ON a.registration_id=r.id
                WHERE LOWER(COALESCE(r.attendee_name,'')) LIKE :pat
                   OR LOWER(COALESCE(r.email,'')) LIKE :pat
                GROUP BY r.email
                HAVING COUNT(DISTINCT CASE WHEN a.attended=TRUE THEN a.webinar_id END) > 0
                   OR COUNT(DISTINCT r.webinar_id) > 0
                ORDER BY attended_count DESC, registered_count DESC
                LIMIT 5
            """), {"pat": f"%{term_lower}%"}).fetchall()

            for row in rows:
                if not row.email: continue
                # Fetch attended webinars for this person
                attended = db.execute(text("""
                    SELECT w.title, w.date, COALESCE(s.name,'Unknown') as speaker,
                           COALESCE(w.icp,'Others') as icp, a.duration_minutes
                    FROM registrations r
                    JOIN attendances a ON a.registration_id=r.id AND a.attended=TRUE
                    JOIN webinars w ON w.id=r.webinar_id
                    LEFT JOIN speakers s ON s.id=w.speaker_id
                    WHERE LOWER(r.email) = :email
                    ORDER BY w.date ASC
                """), {"email": row.email.lower()}).fetchall()

                if not attended: continue

                first = attended[0]
                last  = attended[-1]
                total_min = sum(int(a.duration_minutes or 0) for a in attended)
                # Score calculation matches leaderboard
                avg_dur = total_min / len(attended) if attended else 0
                bonus = 5 if avg_dur >= 60 else 3 if avg_dur >= 45 else 1 if avg_dur >= 30 else 0
                score = len(attended) * (10 + bonus)

                found_people.append({
                    "name": row.name or "(no name)",
                    "email": row.email,
                    "phone": row.phone or "N/A",
                    "attended_count": len(attended),
                    "registered_count": int(row.registered_count or 0),
                    "total_minutes": total_min,
                    "avg_minutes": round(avg_dur, 1),
                    "score": score,
                    "first_webinar": {"title": first.title, "date": str(first.date), "speaker": first.speaker, "icp": first.icp, "duration_min": int(first.duration_minutes or 0)},
                    "last_webinar":  {"title": last.title,  "date": str(last.date),  "speaker": last.speaker,  "icp": last.icp,  "duration_min": int(last.duration_minutes or 0)},
                    "all_webinars": [{"title": a.title, "date": str(a.date), "speaker": a.speaker, "icp": a.icp, "duration_min": int(a.duration_minutes or 0)} for a in attended],
                })
        except Exception as e:
            print(f"Person lookup failed for '{term}': {e}")

    if found_people:
        person_block.append("\nMATCHED PEOPLE (full attendance history from the database):")
        # De-duplicate by email
        seen = set()
        unique = []
        for p in found_people:
            if p["email"].lower() in seen: continue
            seen.add(p["email"].lower())
            unique.append(p)

        for p in unique[:5]:
            person_block.append(f"\n  Person: {p['name']}")
            person_block.append(f"    Email: {p['email']} | Phone: {p['phone']}")
            person_block.append(f"    Attended: {p['attended_count']} of {p['registered_count']} registered webinars")
            person_block.append(f"    Total time: {p['total_minutes']} min | Avg: {p['avg_minutes']} min/session | Score: {p['score']}")
            person_block.append(f"    FIRST webinar attended: [{p['first_webinar']['date']}] {p['first_webinar']['title']} ({p['first_webinar']['speaker']}, ICP: {p['first_webinar']['icp']}, {p['first_webinar']['duration_min']} min)")
            person_block.append(f"    LAST webinar attended:  [{p['last_webinar']['date']}] {p['last_webinar']['title']} ({p['last_webinar']['speaker']}, ICP: {p['last_webinar']['icp']}, {p['last_webinar']['duration_min']} min)")
            person_block.append(f"    Full attendance list:")
            for i, aw in enumerate(p['all_webinars'], 1):
                person_block.append(f"      {i}. [{aw['date']}] {aw['title']} | {aw['speaker']} | {aw['icp']} | {aw['duration_min']} min")
        ctx_parts.extend(person_block)
    elif search_terms:
        ctx_parts.append(f"\nPERSON LOOKUP: searched for {search_terms} but found no matching attendee in the database.")

    context = "\n".join(ctx_parts)

    system_prompt = f"""You are WebinarIQ Assistant, an AI analyst for Right Horizons Financial Services.

STRICT RULES (absolute, no exceptions):
1. You may ONLY use the LIVE DATA below. Never invent numbers, names, emails, dates, percentages, or facts.
2. If the user asks about something NOT in the data (e.g. external market info, world events), respond: "I can only answer questions about the webinar data shown in WebinarIQ. Try asking about speakers, ICPs, attendance, specific webinars, or specific people."
3. COMPARISONS between webinars/speakers/ICPs/people in the data are allowed and encouraged.
4. PERSON QUESTIONS: If the user asks about a specific person by name or email and they appear in 'MATCHED PEOPLE', use that data fully:
   - "First webinar" question → use the 'FIRST webinar attended' line
   - "Last webinar" question → use the 'LAST webinar attended' line
   - "Which webinars did X attend" → list them from 'Full attendance list'
   - "How long did X spend" → use 'Total time' and 'Avg' from the person block
   - "What is X's score" → use 'Score' from the person block
   - Always include email and phone if asked for contact info
5. If a person was searched but not found ('PERSON LOOKUP: ... no matching attendee'), tell the user the person is not in our attendance records.
6. Be concise: under 200 words unless the user asks for a detailed list. Use bullets and bold key numbers.
7. NEVER use em dashes. Use commas, periods, colons, or parentheses instead. Mandatory.

LIVE DATA (the ONLY source of truth):
{context}

Remember: nothing outside this data exists for you. You are a closed-book analyst."""

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-6:]:  # last 6 turns for context
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": question})

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={"model": "anthropic/claude-sonnet-4-5", "max_tokens": 900, "messages": messages},
            timeout=30.0
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()
        answer = answer.replace("—", ", ").replace("–", ", ")
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


# ── Weekly Topic Suggestions ─────────────────────────────────────────────────

@app.get("/api/topics")
async def get_topic_suggestions():
    """Generate fresh weekly topic suggestions per speaker using live market news + AI."""
    import os, json, httpx
    from datetime import date

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

    today = date.today().strftime("%B %d, %Y")

    # Use Claude Sonnet to generate speaker topics based on its training knowledge
    news_context = ""
    context_block = f"Today is {today}. Use your knowledge of Indian financial markets, recent regulatory changes, budget developments, RBI decisions, SEBI updates, and macroeconomic trends."

    prompt = f"""You are a webinar content strategist for Right Horizons, a premium Indian financial advisory firm.

{context_block}

Generate 3 highly specific, timely, non-generic webinar topic suggestions for each of these 5 speakers. Each topic MUST be directly connected to something in the live news above — not general advice.

SPEAKER PROFILES:
- Rachna Rego: Retirement income (SWP, ₹1L monthly), PMS for wealth milestones, women & finance, child education savings, behavioral finance. Frames topics as personal journeys ("How I would...", "What changes now?", "The Real Math"). Never generic.
- Anil Rego: Macro events (budget, RBI, tariffs, geopolitics), ESOPs, portfolio repositioning, market timing. Reacts to breaking news. Frames as urgent decisions ("After X, what now?", "The tax trap", "Smart money is doing this").
- Sunil Kawariya: NRI investing (GIFT City, global asset allocation), large corpus (₹10Cr+), structured products, SIF, tax-efficient wealth. Frames as exclusive insider knowledge ("The strategy most NRIs miss", "₹X Crore, what changes").
- Preethi Shukla: Special needs children financial planning, SIP mechanics, tax-efficient investing, corpus building. Frames as step-by-step systems and parent-focused empathy ("The gap nobody talks about", "Step-by-step for parents").
- Prabhat Ranjan: Equity markets, small/midcap, sectoral themes, PMS strategy, FY outlook. Frames as research-driven conviction ("Hidden in the data", "3 sectors the market hasn't priced in").

Return a JSON array with this exact structure:
[
  {{
    "speaker": "Rachna Rego",
    "color": "#8b5cf6",
    "topics": [
      {{
        "title": "TIGHT webinar title - MUST be ≤80 characters",
        "hook": "ONE sentence ≤120 chars referencing the specific news event driving urgency",
        "angle": "ONE sentence ≤100 chars. Why Right Horizons specifically, not generic content.",
        "expected": "High|Medium|Low",
        "news_link": "which news item from above inspired this topic (1-2 words)"
      }}
    ]
  }}
]

HARD RULES:
1. Title ≤80 characters. Count them.
2. Hook ≤120 characters. Must name a specific recent event/number.
3. Angle ≤100 characters.
4. NEVER use em dashes. Use commas, colons, parentheses instead.
5. Every title must have ₹ figures OR timeframes OR specific scenarios.
6. NO generic titles like "How to Invest Wisely".
7. Return ONLY valid JSON, no markdown."""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={"model": "anthropic/claude-sonnet-4-5", "max_tokens": 4000,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=45.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        topics = _strip_em_dashes(_extract_json(raw))
        return {"topics": topics, "generated_on": today, "news_context": news_context or None}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Topic generation failed: {e}")


# ── AI Webinar Analysis ───────────────────────────────────────────────────────

@app.post("/api/webinars/{webinar_id}/analyze")
async def analyze_webinar(webinar_id: int, db: Session = Depends(get_db)):  # noqa: C901
    """Run AI-powered analysis on a webinar using Claude."""
    import os, json, traceback
    from sqlalchemy import text
    try:
        return await _do_analyze(webinar_id, db)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=traceback.format_exc())


async def _do_analyze(webinar_id: int, db):
    import os, json
    from sqlalchemy import text

    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Webinar not found")

    speaker = db.query(models.Speaker).filter(models.Speaker.id == w.speaker_id).first()
    speaker_name = speaker.name if speaker else "Unknown"

    # ── Gather metrics ────────────────────────────────────────────────────────
    reg_count = db.execute(
        text("SELECT COUNT(*) FROM registrations WHERE webinar_id=:wid"), {"wid": webinar_id}
    ).scalar() or 0

    att_count = db.execute(
        text("SELECT COUNT(*) FROM attendances WHERE webinar_id=:wid AND attended=true"), {"wid": webinar_id}
    ).scalar() or 0

    att_rate = round(att_count / reg_count * 100, 1) if reg_count else 0

    # Duration breakdown
    durations = db.execute(
        text("SELECT duration_minutes FROM attendances WHERE webinar_id=:wid AND attended=true AND duration_minutes IS NOT NULL"),
        {"wid": webinar_id}
    ).fetchall()
    dur_vals = [r[0] for r in durations if r[0] is not None]
    avg_duration = round(sum(dur_vals) / len(dur_vals), 1) if dur_vals else 0
    engaged     = sum(1 for d in dur_vals if d >= 45)   # stayed 45+ min
    moderate    = sum(1 for d in dur_vals if 15 <= d < 45)
    dropped     = sum(1 for d in dur_vals if d < 15)
    pct_engaged = round(engaged / len(dur_vals) * 100, 1) if dur_vals else 0

    # Source breakdown
    sources = db.execute(
        text("SELECT source, COUNT(*) FROM registrations WHERE webinar_id=:wid GROUP BY source"),
        {"wid": webinar_id}
    ).fetchall()
    source_breakdown = {r[0]: r[1] for r in sources}
    top_source = max(source_breakdown, key=source_breakdown.get) if source_breakdown else "direct"

    # Registration timeline: days before webinar
    reg_times = db.execute(
        text("SELECT registered_at FROM registrations WHERE webinar_id=:wid ORDER BY registered_at"),
        {"wid": webinar_id}
    ).fetchall()
    last_day_regs = 0
    if reg_times and w.date:
        from datetime import datetime, date
        webinar_date = datetime.fromisoformat(str(w.date)).date() if isinstance(w.date, str) else w.date
        for (rt,) in reg_times:
            try:
                reg_date = datetime.fromisoformat(str(rt)).date() if rt else None
                if reg_date and (webinar_date - reg_date).days <= 1:
                    last_day_regs += 1
            except Exception:
                pass
    pct_lastday = round(last_day_regs / reg_count * 100, 1) if reg_count else 0

    # Platform benchmarks (all completed webinars)
    bench = db.execute(text("""
        SELECT
          AVG(att_c * 1.0 / NULLIF(reg_c,0)) as avg_rate,
          AVG(reg_c) as avg_regs
        FROM (
          SELECT w2.id,
            (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id=w2.id) as reg_c,
            (SELECT COUNT(*) FROM attendances a WHERE a.webinar_id=w2.id AND a.attended=true) as att_c
          FROM webinars w2 WHERE w2.status='completed'
        ) x WHERE reg_c > 0
    """)).fetchone()
    platform_avg_rate = round(float(bench[0] or 0) * 100, 1)
    platform_avg_regs = round(float(bench[1] or 0))

    # Speaker benchmarks (this speaker's other webinars)
    spk_bench = db.execute(text("""
        SELECT
          AVG(att_c * 1.0 / NULLIF(reg_c,0)) as spk_avg_rate,
          AVG(reg_c) as spk_avg_regs,
          COUNT(*) as spk_webinar_count
        FROM (
          SELECT w2.id,
            (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id=w2.id) as reg_c,
            (SELECT COUNT(*) FROM attendances a WHERE a.webinar_id=w2.id AND a.attended=true) as att_c
          FROM webinars w2
          WHERE w2.speaker_id=:spk_id AND w2.id != :wid AND w2.status='completed'
        ) x WHERE reg_c > 0
    """), {"spk_id": w.speaker_id, "wid": webinar_id}).fetchone()
    spk_avg_rate = round(float(spk_bench[0]) * 100, 1) if spk_bench[0] else None
    spk_avg_regs = round(float(spk_bench[1])) if spk_bench[1] else None
    spk_webinar_count = spk_bench[2] or 0

    # Performance grade
    if att_rate >= 50: grade = "A"
    elif att_rate >= 35: grade = "B"
    elif att_rate >= 20: grade = "C"
    else: grade = "D"

    # ── Build Claude prompt ───────────────────────────────────────────────────
    metrics = {
        "webinar_title": w.title,
        "date": str(w.date),
        "speaker": speaker_name,
        "topic": w.description or "",
        "registrations": reg_count,
        "attendees": att_count,
        "no_shows": reg_count - att_count,
        "attendance_rate_pct": att_rate,
        "platform_avg_attendance_rate_pct": platform_avg_rate,
        "platform_avg_registrations": platform_avg_regs,
        "performance_grade": grade,
        "avg_session_duration_min": avg_duration,
        "engaged_45plus_min": {"count": engaged, "pct": pct_engaged},
        "moderate_15_44_min": {"count": moderate},
        "dropped_under_15_min": {"count": dropped},
        "registration_sources": source_breakdown,
        "top_source": top_source,
        "last_day_registrations_pct": pct_lastday,
        "speaker_other_webinars": spk_webinar_count,
        "speaker_avg_attendance_rate_pct": spk_avg_rate,
        "speaker_avg_registrations": spk_avg_regs,
    }

    # ── Fetch human notes for this webinar (if any) ───────────────────────────
    notes_rows = db.execute(text("""
        SELECT author, category, content, created_at
        FROM webinar_notes WHERE webinar_id = :w
        ORDER BY created_at DESC
    """), {"w": webinar_id}).fetchall()

    if notes_rows:
        notes_list = "\n".join(
            f"  [{n.category}] {n.author}: {n.content}"
            for n in notes_rows
        )
        human_notes_block = f"""HUMAN OBSERVATIONS (the team has added these notes about this webinar). Treat them as critical context. Reference at least one of them in your analysis if relevant:
{notes_list}"""
    else:
        human_notes_block = "(No human notes have been logged for this webinar.)"

    prompt = f"""You are a sharp webinar performance analyst for Right Horizons, an Indian financial advisory firm.

STRICT RULES:
- Use ONLY the numbers in 'Webinar data' below. Never fabricate numbers, names, or comparisons.
- Every insight must reference a specific number from the data with the actual figure shown.
- Recommendations must be SPECIFIC and ACTIONABLE - no generic phrases like "improve marketing" or "engage audience". Tie each to ONE concrete number in the data.
- Tone: direct, expert, no fluff. Skip throat-clearing intros.

Return ONLY a JSON object with this exact shape:

{{
  "grade": "A|B|C|D",
  "grade_label": "Excellent|Good|Needs Work|Poor",
  "score_summary": "12-word verdict, lead with the most striking number",
  "sections": [
    {{
      "title": "Audience Reach",
      "icon": "single emoji",
      "insight": "2 sentences citing specific numbers from data. State the delta vs platform avg in absolute terms (eg '337 above platform avg of 244')",
      "highlight": "max 8 words, end with a number"
    }},
    {{ "title": "Engagement Quality", "icon": "...", "insight": "cite attendance rate AND avg duration AND engaged 45m+ count. Compare to platform avg.", "highlight": "..." }},
    {{ "title": "Registration Channels", "icon": "...", "insight": "name the dominant source with % share. Flag if any source under-performs.", "highlight": "..." }},
    {{ "title": "Speaker Performance", "icon": "...", "insight": "compare to speaker's own avg (if available) AND platform avg. State delta in pp.", "highlight": "..." }},
    {{ "title": "Timing & Momentum", "icon": "...", "insight": "cite last-day registration % and registration window length. Flag if momentum was concentrated.", "highlight": "..." }}
  ],
  "recommendations": [
    "ONE sharp, non-generic move tied to a specific weakness in THIS webinar's numbers. Format: 'Action verb + specific tactic + expected lift'. Example: 'Send 24h reminder SMS to no-shows - based on 64% no-show rate, recovering 10% adds 37 attendees'",
    "Second strategy - must propose a SPECIFIC experiment or channel/format shift, not 'try X harder'",
    "Third strategy - reference one of the strong metrics and how to EXPLOIT it for the next webinar"
  ],
  "verdict": "3 sentences. Sentence 1: the single best number. Sentence 2: the single worst number with the gap to fix. Sentence 3: one concrete experiment to run next webinar with expected outcome."
}}

Avoid words: 'consider', 'leverage', 'utilize', 'engage', 'optimize', 'maximize', 'enhance' (these are generic filler).
Prefer: specific verbs (test, send, replace, swap, drop, double, halve, A/B, schedule).
NEVER use em dashes. Use commas, periods, colons, or parentheses instead. This rule is absolute.

Webinar data:
{json.dumps(metrics, indent=2, default=lambda o: float(o) if hasattr(o,'__float__') else str(o))}

{human_notes_block}

Return ONLY the JSON object, nothing before or after, no markdown fences."""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

    try:
        import httpx
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=35.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        analysis = _strip_em_dashes(_extract_json(raw))
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")

    return {
        "webinar_id": webinar_id,
        "metrics": metrics,
        "analysis": analysis
    }


# ── Webinar vs Previous Comparison ────────────────────────────────────────────

@app.post("/api/webinars/{webinar_id}/compare")
async def compare_webinar(webinar_id: int, db: Session = Depends(get_db)):
    """Compare this webinar to the most recent previous webinar by same speaker (fallback: same ICP, then platform avg)."""
    import os, json, traceback
    from sqlalchemy import text as _text
    try:
        w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
        if not w:
            raise HTTPException(status_code=404, detail="Webinar not found")

        def stats_for(wid):
            r = db.execute(_text(
                "SELECT (SELECT COUNT(*) FROM registrations WHERE webinar_id=:w) AS regs, "
                "(SELECT COUNT(*) FROM attendances WHERE webinar_id=:w AND attended=TRUE) AS att, "
                "(SELECT AVG(duration_minutes) FROM attendances WHERE webinar_id=:w AND attended=TRUE) AS avg_dur, "
                "(SELECT COUNT(*) FROM attendances WHERE webinar_id=:w AND attended=TRUE AND duration_minutes>=45) AS engaged"
            ), {"w": wid}).fetchone()
            regs = int(r.regs or 0); att = int(r.att or 0)
            avg_dur = round(float(r.avg_dur or 0), 1)
            engaged = int(r.engaged or 0)
            rate = round(att/regs*100, 1) if regs else 0
            return {"registrations": regs, "attendees": att, "attendance_rate": rate,
                    "avg_duration_min": avg_dur, "engaged_45plus": engaged}

        this_stats = stats_for(webinar_id)
        this_meta = {
            "id": webinar_id, "title": w.title, "date": str(w.date),
            "speaker": w.speaker.name if w.speaker else "Unknown",
            "icp": w.icp or "Others",
            **this_stats,
        }

        # Find best comparison target — prefer same speaker, fallback same ICP
        prev = db.execute(_text("""
            SELECT id, title, date, speaker_id, icp
            FROM webinars
            WHERE date < :d AND status='completed' AND speaker_id = :spk
            ORDER BY date DESC LIMIT 1
        """), {"d": w.date, "spk": w.speaker_id}).fetchone()

        comparison_basis = "same speaker"
        if not prev:
            prev = db.execute(_text("""
                SELECT id, title, date, speaker_id, icp
                FROM webinars
                WHERE date < :d AND status='completed' AND COALESCE(icp,'Others') = :icp
                ORDER BY date DESC LIMIT 1
            """), {"d": w.date, "icp": w.icp or "Others"}).fetchone()
            comparison_basis = "same ICP"
        if not prev:
            prev = db.execute(_text("""
                SELECT id, title, date, speaker_id, icp FROM webinars
                WHERE date < :d AND status='completed'
                ORDER BY date DESC LIMIT 1
            """), {"d": w.date}).fetchone()
            comparison_basis = "most recent prior webinar"
        if not prev:
            raise HTTPException(status_code=404, detail="No previous webinar available to compare.")

        prev_speaker_row = db.execute(_text("SELECT name FROM speakers WHERE id=:s"), {"s": prev.speaker_id}).fetchone()
        prev_meta = {
            "id": prev.id, "title": prev.title, "date": str(prev.date),
            "speaker": prev_speaker_row.name if prev_speaker_row else "Unknown",
            "icp": prev.icp or "Others",
            **stats_for(prev.id),
        }

        # Compute deltas
        def delta(a, b):
            if b == 0: return {"abs": a, "pct": None}
            return {"abs": round(a - b, 1), "pct": round((a - b)/b * 100, 1)}
        deltas = {
            "registrations": delta(this_stats["registrations"], prev_meta["registrations"]),
            "attendees": delta(this_stats["attendees"], prev_meta["attendees"]),
            "attendance_rate": delta(this_stats["attendance_rate"], prev_meta["attendance_rate"]),
            "avg_duration_min": delta(this_stats["avg_duration_min"], prev_meta["avg_duration_min"]),
            "engaged_45plus": delta(this_stats["engaged_45plus"], prev_meta["engaged_45plus"]),
        }

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

        prompt = f"""You are a webinar performance analyst. Compare these two webinars and return a JSON object.

Comparison basis: {comparison_basis}

CURRENT WEBINAR:
{json.dumps(this_meta, indent=2)}

PREVIOUS WEBINAR:
{json.dumps(prev_meta, indent=2)}

COMPUTED DELTAS (current vs previous):
{json.dumps(deltas, indent=2)}

Return JSON with this exact shape:

{{
  "headline": "single sentence verdict (max 18 words), lead with the biggest swing in absolute or %",
  "key_wins": ["2-3 strings, each a specific metric where current beat previous, format: 'Metric: from X to Y (+Z%)'"],
  "key_losses": ["2-3 strings, each a specific metric where current was worse, same format"],
  "diagnosis": "2-3 sentences explaining the likely cause based on title/ICP/speaker differences in the data above",
  "next_action": "ONE specific tactic for the next webinar, tied to the biggest gap. Format: 'Action verb + tactic + expected lift'"
}}

Rules:
- Use ONLY the numbers in the data above. No invented figures.
- Be direct. No filler. No 'consider', 'leverage', 'utilize'.
- Numbers must match the deltas shown exactly.
- NEVER use em dashes. Use commas, periods, colons, or parentheses instead.

Return ONLY the JSON, no markdown, no preamble."""

        import httpx
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={"model": "anthropic/claude-sonnet-4-5", "max_tokens": 800,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=25.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        analysis = _strip_em_dashes(_extract_json(raw))

        return {
            "current": this_meta,
            "previous": prev_meta,
            "deltas": deltas,
            "comparison_basis": comparison_basis,
            "analysis": analysis,
        }
    except HTTPException:
        raise
    except Exception:
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

    if not regs:
        raise HTTPException(status_code=404, detail="No registration data available for this webinar.")

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
        .filter(
            models.Attendance.webinar_id == webinar_id,
            models.Attendance.attended == True,
        )
        .order_by(models.Attendance.joined_at)
        .all()
    )

    if not rows:
        raise HTTPException(status_code=404, detail="No attendance data available for this webinar.")

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
    import traceback
    response.headers["Cache-Control"] = "no-store"
    try:
        return crud.get_all_speakers(db)
    except Exception:
        raise HTTPException(status_code=500, detail=traceback.format_exc())


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
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return crud.get_leaderboard(db, speaker_id=speaker_id, webinar_id=webinar_id, limit=limit)


# ── Meeting Pipeline ─────────────────────────────────────────────────────────

PIPELINE_STATUSES = {"new", "contacted", "meeting_booked", "converted", "not_interested"}


@app.get("/api/pipeline")
def list_pipeline(db: Session = Depends(get_db)):
    """Return all pipeline contacts enriched with leaderboard data."""
    from sqlalchemy import text as _text
    contacts = db.execute(_text(
        "SELECT email, status, assigned_to, notes, follow_up_date, added_at, updated_at FROM pipeline_contacts ORDER BY updated_at DESC"
    )).fetchall()

    # Build leaderboard lookup: email → {name, total_webinars, total_duration, readiness, last_webinar}
    lb_rows = db.execute(_text("""
        SELECT
            r.email,
            r.attendee_name AS name,
            COUNT(DISTINCT a.webinar_id) AS total_webinars,
            COALESCE(SUM(a.duration_minutes), 0) AS total_duration,
            MAX(w.date) AS last_webinar
        FROM registrations r
        JOIN attendances a ON a.registration_id = r.id AND a.attended = TRUE
        JOIN webinars w ON w.id = a.webinar_id
        GROUP BY r.email, r.attendee_name
    """)).fetchall()
    lb_map = {}
    for row in lb_rows:
        # Keep highest total_duration per email (in case of duplicates)
        if row.email not in lb_map or row.total_duration > lb_map[row.email]['total_duration']:
            lb_map[row.email] = {
                "name": row.name,
                "total_webinars": row.total_webinars,
                "total_duration": row.total_duration,
                "last_webinar": str(row.last_webinar) if row.last_webinar else None,
            }

    # Lead tags lookup (table may not exist in all environments)
    try:
        tags = db.execute(_text("SELECT email, tag FROM lead_tags")).fetchall()
        tag_map = {t.email: t.tag for t in tags}
    except Exception:
        tag_map = {}

    result = []
    for c in contacts:
        lb = lb_map.get(c.email, {})
        result.append({
            "email": c.email,
            "name": lb.get("name") or c.email,
            "status": c.status,
            "assigned_to": c.assigned_to,
            "notes": c.notes,
            "follow_up_date": str(c.follow_up_date) if c.follow_up_date else None,
            "added_at": str(c.added_at) if c.added_at else None,
            "updated_at": str(c.updated_at) if c.updated_at else None,
            "total_webinars": lb.get("total_webinars", 0),
            "total_duration": lb.get("total_duration", 0),
            "last_webinar": lb.get("last_webinar"),
            "lead_tag": tag_map.get(c.email, ""),
        })
    return result


@app.put("/api/pipeline/{email}", status_code=200)
def upsert_pipeline(email: str, payload: dict, db: Session = Depends(get_db)):
    """Add or update a contact in the pipeline."""
    from sqlalchemy import text as _text
    from datetime import datetime as _dt

    status = payload.get("status", "new")
    if status not in PIPELINE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(sorted(PIPELINE_STATUSES))}")

    assigned_to   = (payload.get("assigned_to") or "").strip() or None
    notes         = (payload.get("notes") or "").strip() or None
    follow_up_raw = (payload.get("follow_up_date") or "").strip() or None
    now = _dt.utcnow().isoformat(sep=" ", timespec="seconds")

    # Check if exists (SQLite vs PostgreSQL upsert compatible pattern)
    existing = db.execute(_text("SELECT email FROM pipeline_contacts WHERE email = :e"), {"e": email}).fetchone()
    if existing:
        db.execute(_text("""
            UPDATE pipeline_contacts
            SET status=:s, assigned_to=:a, notes=:n, follow_up_date=:f, updated_at=:u
            WHERE email=:e
        """), {"s": status, "a": assigned_to, "n": notes, "f": follow_up_raw, "u": now, "e": email})
    else:
        db.execute(_text("""
            INSERT INTO pipeline_contacts (email, status, assigned_to, notes, follow_up_date, added_at, updated_at)
            VALUES (:e, :s, :a, :n, :f, :u, :u)
        """), {"e": email, "s": status, "a": assigned_to, "n": notes, "f": follow_up_raw, "u": now})
    db.commit()
    return {"email": email, "status": status}


@app.delete("/api/pipeline/{email}", status_code=204)
def remove_pipeline(email: str, db: Session = Depends(get_db)):
    from sqlalchemy import text as _text
    db.execute(_text("DELETE FROM pipeline_contacts WHERE email = :e"), {"e": email})
    db.commit()


@app.get("/api/pipeline/export")
def export_pipeline(db: Session = Depends(get_db)):
    """Download full pipeline as CSV."""
    from sqlalchemy import text as _text
    contacts = db.execute(_text(
        "SELECT email, status, assigned_to, notes, follow_up_date, added_at FROM pipeline_contacts ORDER BY updated_at DESC"
    )).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Email", "Status", "Assigned To", "Notes", "Follow Up Date", "Added At"])
    for c in contacts:
        writer.writerow([
            c.email, c.status or "", c.assigned_to or "",
            c.notes or "", str(c.follow_up_date) if c.follow_up_date else "", str(c.added_at) if c.added_at else "",
        ])
    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="pipeline.csv"'},
    )


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


@app.get("/api/new-registrants-per-webinar")
def get_new_registrants_per_webinar(db: Session = Depends(get_db)):
    """For each webinar (sorted by date), count how many registrant emails appear for the FIRST time."""
    from sqlalchemy import text as _t

    rows = db.execute(_t("""
        SELECT w.id AS webinar_id, w.title, w.date, r.email
        FROM webinars w
        JOIN registrations r ON r.webinar_id = w.id
        WHERE r.email IS NOT NULL AND r.email != ''
        ORDER BY w.date ASC, w.id ASC
    """)).fetchall()

    seen = set()
    webinar_map = {}
    for row in rows:
        wid = row.webinar_id
        if wid not in webinar_map:
            webinar_map[wid] = {"webinar_id": wid, "title": row.title, "date": str(row.date)[:10] if row.date else None, "new_count": 0, "repeat_count": 0}
        email = (row.email or "").lower().strip()
        if email in seen:
            webinar_map[wid]["repeat_count"] += 1
        else:
            seen.add(email)
            webinar_map[wid]["new_count"] += 1

    result = sorted(webinar_map.values(), key=lambda x: x["date"] or "")
    return {"webinars": result}


# ── ML Analysis Endpoint ──────────────────────────────────────────────────────

ML_MODULE_PROMPTS = {
    "topic_prediction": "Predict the top 5 best-performing webinar topics for HNI wealth advisory in India. Score each 0-100 for predicted registration pull, attendance rate, and conversion potential. Return JSON with keys: score, confidence, summary, predictions (array of strings).",
    "topic_quality": "Evaluate the given webinar topic for quality, relevance to Indian HNIs, and differentiation from competitors. Return JSON with keys: score (0-100), confidence (0-1), summary, insights (array of strings).",
    "pattern_detection": "Analyse engagement patterns for Indian HNI wealth webinars. Identify drop-off points, peak engagement windows, and optimal duration. Return JSON with keys: score, confidence, summary, insights (array of strings), recommendations (array of strings).",
    "forecasting": "Forecast registration and attendance numbers for the given webinar topic targeting Indian HNIs. Consider seasonality, market conditions, and topic appeal. Return JSON with keys: score, confidence, summary, predictions (array of strings).",
    "market_intelligence": "Provide market intelligence on the Indian HNI wealth advisory space. Cover trends in PMS, AIF, Family Office, and NRI segments. Return JSON with keys: score, confidence, summary, insights (array of strings).",
    "algorithm_impact": "Assess how platform algorithms (LinkedIn, email, WhatsApp) affect webinar reach for Indian HNI audiences. Return JSON with keys: score, confidence, summary, insights (array of strings), recommendations (array of strings).",
    "audience_psychology": "Analyse the psychology of Indian HNI investors when deciding to attend wealth advisory webinars. Cover trust factors, FOMO triggers, and credibility signals. Return JSON with keys: score, confidence, summary, insights (array of strings).",
    "content_intelligence": "Optimise webinar content structure for maximum conversion among Indian HNIs. Cover title framing, agenda design, and CTA placement. Return JSON with keys: score, confidence, summary, recommendations (array of strings).",
    "similarity_engine": "Identify audience segments with high affinity for the given webinar topic. Cluster by ICP (PMS, AIF, Family Office, NRI, ESOPs), geography, and investment size. Return JSON with keys: score, confidence, summary, insights (array of strings).",
    "opportunity_risk": "Surface opportunities and risk flags for the given webinar topic in the Indian HNI space. Cover timing risks, competitor overlap, and market saturation. Return JSON with keys: score, confidence, summary, predictions (array of strings), recommendations (array of strings).",
}

@app.post("/api/ml-analysis")
async def ml_analysis(payload: dict):
    import httpx, json as _json
    module = payload.get("module", "")
    topic = payload.get("topic", "General HNI Wealth Advisory")
    if module not in ML_MODULE_PROMPTS:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module}")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")
    system_prompt = f"You are an expert AI analyst for Right Horizons Financial Services, specialising in Indian HNI wealth advisory webinars. The user topic is: {topic}. Respond ONLY with valid JSON, no markdown."
    user_prompt = ML_MODULE_PROMPTS[module]
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "anthropic/claude-sonnet-4-5", "max_tokens": 2000, "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"OpenRouter returned {resp.status_code}")
        data = resp.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return _json.loads(text)
    except _json.JSONDecodeError:
        return {"summary": text, "score": 0, "confidence": 0}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
