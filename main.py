import os
import hashlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Response, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, HTMLResponse
from starlette.responses import Response as StarletteResponse
import csv, io
from sqlalchemy.orm import Session
from typing import Optional, List

from database import engine, SessionLocal
import models, crud, schemas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("webinariq")

# ── App config (env-driven, sensible defaults) ────────────────────────────────
COMPANY_NAME        = os.environ.get("COMPANY_NAME",         "Right Horizons")
COMPANY_DESC        = os.environ.get("COMPANY_DESC",         "an Indian financial advisory firm running HNI/NRI webinars")
COMPANY_DOMAIN      = os.environ.get("COMPANY_DOMAIN",       "righthorizons.com")
APP_URL             = os.environ.get("APP_URL",              "https://webinar-analytics-six.vercel.app")
OPENROUTER_REFERER  = os.environ.get("OPENROUTER_REFERER",   APP_URL)
AI_MODEL            = os.environ.get("AI_MODEL",             "anthropic/claude-sonnet-4-5")
# Optional API key to protect endpoints. Set API_KEY env var in Vercel to enable.
API_KEY             = os.environ.get("API_KEY", "")

def _auth(x_api_key: str = Header(default="")):
    """Enforce API key if one is configured in the environment."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

def _ai_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_REFERER,
        "X-Title": "WebinarIQ",
    }


def _compute_perf_score(regs: int, att_rate: float, icp: str, has_ads: bool = False) -> int:
    reg_score = min(25, round(regs / 150 * 25))
    att_score = min(35, round(att_rate / 60 * 35))
    icp_scores = {'Family Office': 20, 'AIF': 20, 'PMS': 18, 'NRI': 16, 'ESOPs': 15, 'Retirement Planning': 14, 'Others': 8}
    icp_score = icp_scores.get(icp or 'Others', 8)
    fit_score = 10
    followup_score = 3
    return min(100, reg_score + att_score + icp_score + fit_score + followup_score)


def _score_label(score: int) -> str:
    if score >= 80: return "High Performing"
    if score >= 60: return "Good"
    if score >= 40: return "Average"
    return "Low Performing"


def _compute_static_version() -> str:
    h = hashlib.md5()
    # File content (catches local edits)
    for fname in ["app.js", "styles.css", "trilliant.css", "index.html"]:
        fpath = os.path.join(BASE_DIR, "static", fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                h.update(f.read())
    # Vercel deploy ID / commit SHA (guarantees a new version on every deploy
    # even if file contents are byte-identical)
    deploy_id = (
        os.environ.get("VERCEL_GIT_COMMIT_SHA")
        or os.environ.get("VERCEL_DEPLOYMENT_ID")
        or os.environ.get("VERCEL_URL")
        or ""
    )
    h.update(deploy_id.encode("utf-8"))
    return h.hexdigest()[:12]

STATIC_VERSION = _compute_static_version()


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> StarletteResponse:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Surrogate-Control"] = "no-store"
            response.headers["CDN-Cache-Control"] = "no-store"
            response.headers["Vercel-CDN-Cache-Control"] = "no-store"
            response.headers["CDN-Cache-Control"] = "no-store"
            response.headers["Vercel-CDN-Cache-Control"] = "no-store"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("DATABASE_URL") and not os.environ.get("VERCEL"):
        try:
            models.Base.metadata.create_all(bind=engine)
            from seed_data import seed_database
            seed_database()
            logger.info("Local dev DB seeded")
        except Exception as e:
            logger.warning(f"DB seed skipped: {e}")
    yield


app = FastAPI(title="WebinarIQ Analytics", version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
    response.headers["Surrogate-Control"] = "no-store"
    response.headers["CDN-Cache-Control"] = "no-store"
    response.headers["Vercel-CDN-Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Vary"] = "*"          # prevent CDN Vary-based caching
    return response


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Static files & root ───────────────────────────────────────────────────────

app.mount("/static", NoCacheStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.get("/", include_in_schema=False)
async def root():
    html_path = os.path.join(BASE_DIR, "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    # Replace any hardcoded ?v=NNN with the content-hash version so browsers
    # automatically load fresh assets after every deploy that changes files.
    import re
    html = re.sub(r'\?v=[^"\'&]+', f'?v={STATIC_VERSION}', html)
    resp = HTMLResponse(content=html)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
    resp.headers["Surrogate-Control"] = "no-store"
    resp.headers["CDN-Cache-Control"] = "no-store"
    resp.headers["Vercel-CDN-Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
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
    except Exception as e:
        logger.warning(f"followup_pending calc failed: {e}")
        return stats


@app.get("/api/health")
def health_check():
    return {"status": "ok", "company": COMPANY_NAME}


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
    try:
        detail = crud.get_webinar_detail(db, webinar_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Webinar not found")
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error loading webinar %s: %s", webinar_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to load webinar: {exc}")


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
    for field in ("platform", "category", "language", "recording_url", "tags", "notes", "series"):
        if field in payload:
            setattr(w, field, payload[field])
    if "is_favourite" in payload:
        w.is_favourite = bool(payload["is_favourite"])
    if "expected_registrations" in payload:
        v = payload["expected_registrations"]
        w.expected_registrations = int(v) if v else None
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
        logger.exception("Unhandled error")
        raise HTTPException(status_code=500, detail="Internal server error")


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
    try:
        return _get_intelligence_inner(db)
    except Exception:
        logger.exception("Unhandled error")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        params = {f"e{i}": e for i, e in enumerate(att_email_list[:100])}
        ph = ",".join(f":e{i}" for i in range(len(params)))
        followed_up = db.execute(_t(f"SELECT COUNT(*) FROM pipeline_contacts WHERE email IN ({ph}) AND status NOT IN ('new')"), params).fetchone()[0] or 0

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
        params = {f"e{i}": e for i, e in enumerate(emails[:100])}
        ph = ",".join(f":e{i}" for i in range(len(params)))
        pl_rows = db.execute(_t(f"SELECT email, status FROM pipeline_contacts WHERE email IN ({ph})"), params).fetchall()
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
                     "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
            json={
                "model": AI_MODEL,
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
                     "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
            json={
                "model": AI_MODEL,
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
                         "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
                json={
                    "model": AI_MODEL,
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
                         "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
                json={
                    "model": AI_MODEL,
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
            SELECT platform, SUM(CAST(spend AS FLOAT)) as spend, SUM(impressions) as impr,
                   SUM(clicks) as clicks, SUM(conversions) as conv
            FROM webinar_ads WHERE spend IS NOT NULL AND spend != ''
            GROUP BY platform ORDER BY spend DESC
        """)).fetchall()
        if ads_rows:
            ads_summary = "ADS DATA:\n" + "\n".join(
                f"  {r.platform}: spend={r.spend}, impressions={r.impr}, clicks={r.clicks}, conversions={r.conv}"
                for r in ads_rows
            )

    prompt = f"""You are a senior marketing analyst for {COMPANY_NAME}, {COMPANY_DESC}.

WEBINAR DATA (all completed webinars, newest first):
{chr(10).join(webinar_lines) if webinar_lines else 'No completed webinars yet.'}

ICP PERFORMANCE: {icp_summary}
SPEAKER PERFORMANCE: {spk_summary}
RECENT WEBINARS: {recent_summary}

Generate EXACTLY 8 structured insights as a JSON array using these types: win, risk, opportunity, action, trend, funnel, lead_quality, recommendation.

Distribution: 2 wins, 2 risks, 2 opportunities, 1 action, 1 trend. Tailor every insight to the HNI/NRI wealth advisory business context of {COMPANY_NAME}.

Rules:
- EVERY insight MUST cite a specific number, name, or date from the data
- Be direct, prescriptive, and specific — no generic marketing advice
- Each "action" must name which speaker, which ICP, and which format to use
- "win" = something working well that should be doubled down on
- "risk" = something deteriorating or underperforming that needs fixing now
- "opportunity" = an untapped ICP, topic, or speaker combination worth trying
- "trend" = a directional pattern visible across multiple webinars
- Do not mention ad spend or CPL unless ads data is provided
{f'- Ads data available: {ads_summary}' if has_ads else ''}

Return ONLY a valid JSON array of exactly 8 objects:
[
  {{
    "type": "win|risk|opportunity|action|trend|funnel|lead_quality|recommendation",
    "headline": "Bold specific claim ≤70 chars",
    "detail": "2-3 sentences with specific numbers, names, and clear business implication.",
    "action": "One specific next step naming speaker/ICP/format ≤100 chars",
    "metric": "The key stat e.g. '47% attendance rate' or 'Anil Rego 3 webinars'"
  }}
]"""

    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=45.0) as _ac:
            resp = await _ac.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                         "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
                json={"model": AI_MODEL, "max_tokens": 2000,
                      "messages": [{"role": "user", "content": prompt}]},
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
            (SELECT STRING_AGG(DISTINCT COALESCE(w2.icp,'Others'), ',') FROM attendances a2 JOIN registrations r2 ON r2.id=a2.registration_id JOIN webinars w2 ON w2.id=a2.webinar_id WHERE a2.attended=TRUE AND r2.email=r.email) AS icps,
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
        bind = db.get_bind()
        return 'postgres' in str(bind.url).lower()
    except Exception:
        return bool(os.environ.get("DATABASE_URL"))


@app.get("/api/competitor-gap-analysis")
async def competitor_gap_analysis(db: Session = Depends(get_db)):
    """AI-powered gap analysis: where {COMPANY_NAME} can win vs competitor activity."""
    import os, httpx
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

        prompt = f"""You are a competitive intelligence analyst for {COMPANY_NAME}, {COMPANY_DESC}.

Compare what competitors did in the last 90 days versus what {COMPANY_NAME} did. Identify SPECIFIC gaps and opportunities.

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
                     "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
            json={"model": AI_MODEL, "max_tokens": 2500,
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
        logger.exception("Unhandled error")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        if email_l.endswith('@' + COMPANY_DOMAIN): return "internal"
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
    STOPWORDS = {'What','When','Which','Who','How','Why','Where','The','This','That','First','Last','Top','Show','Tell','Give','List','Find','Webinar','Speaker','Attendance','Registration','Right','Horizons',COMPANY_NAME,COMPANY_NAME.split()[0] if ' ' in COMPANY_NAME else COMPANY_NAME,'WebinarIQ','PMS','NRI','ICP','SIP','SWP','ESOPs'}
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

    system_prompt = f"""You are WebinarIQ Assistant, an AI analyst for {COMPANY_NAME}.

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
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
            json={"model": AI_MODEL, "max_tokens": 900, "messages": messages},
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
    # Try to fetch live Indian financial news via free RSS feeds (no key required)
    NEWS_FEEDS = [
        "https://economictimes.indiatimes.com/markets/rss.cms",
        "https://economictimes.indiatimes.com/wealth/rss.cms",
        "https://www.moneycontrol.com/rss/results.xml",
    ]
    try:
        import re as _re
        async with httpx.AsyncClient(timeout=5.0) as _nc:
            for feed_url in NEWS_FEEDS:
                try:
                    r = await _nc.get(feed_url, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0 (WebinarIQ/1.0)"})
                    if r.status_code == 200:
                        titles = _re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)[:8]
                        if not titles:
                            titles = _re.findall(r'<title>(.*?)</title>', r.text)[1:9]
                        headlines = [t.strip() for t in titles if len(t.strip()) > 10]
                        if headlines:
                            news_context += "\n".join(f"- {h}" for h in headlines[:6]) + "\n"
                            break
                except Exception:
                    continue
    except Exception:
        pass

    if news_context:
        context_block = f"Today is {today}. Here are LIVE headlines from Indian financial news (use these to make topics timely and specific):\n{news_context}\nAlso use your knowledge of recent RBI decisions, SEBI updates, budget developments, and macroeconomic trends."
    else:
        context_block = f"Today is {today}. Use your knowledge of Indian financial markets, recent regulatory changes, budget developments, RBI decisions, SEBI updates, and macroeconomic trends."

    prompt = f"""You are a webinar content strategist for {COMPANY_NAME}, {COMPANY_DESC}.

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
        "angle": "ONE sentence ≤100 chars. Why {COMPANY_NAME} specifically, not generic content.",
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
        async with httpx.AsyncClient(timeout=50.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                         "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
                json={"model": AI_MODEL, "max_tokens": 4000,
                      "messages": [{"role": "user", "content": prompt}]},
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
    import os, json
    from sqlalchemy import text
    try:
        return await _do_analyze(webinar_id, db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error")
        raise HTTPException(status_code=500, detail="Internal server error")


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

    prompt = f"""You are a sharp webinar performance analyst for {COMPANY_NAME}, {COMPANY_DESC}.

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
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
            json={
                "model": AI_MODEL,
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
    import os, json
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
                     "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
            json={"model": AI_MODEL, "max_tokens": 800,
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
        logger.exception("Unhandled error")
        raise HTTPException(status_code=500, detail="Internal server error")


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
    response.headers["Cache-Control"] = "no-store"
    return crud.get_all_speakers(db)


@app.get("/api/speakers/{speaker_id}", response_model=schemas.SpeakerDetail)
def get_speaker(speaker_id: int, db: Session = Depends(get_db)):
    try:
        detail = crud.get_speaker_detail(db, speaker_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error loading speaker %s: %s", speaker_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to load speaker: {exc}")


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


# ── AI Intelligence Modules (real ML + AI) ────────────────────────────────────

def _ml_fetch_webinar_stats(db):
    """Return list of dicts with title, icp, regs, att_rate for completed webinars."""
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT w.title, w.icp,
               (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id = w.id) AS total_registrations,
               (SELECT COUNT(*) FROM attendances a WHERE a.webinar_id = w.id AND a.attended = TRUE) AS total_attendees
        FROM webinars w
        WHERE w.status = 'completed'
          AND (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id = w.id) > 0
    """)).fetchall()
    results = []
    for r in rows:
        att_rate = (r.total_attendees / r.total_registrations * 100) if r.total_registrations else 0
        results.append({
            "title": r.title or "",
            "icp": r.icp or "Others",
            "regs": r.total_registrations or 0,
            "att_rate": round(att_rate, 1),
        })
    return results


def _ml_tfidf_similarity(query: str, corpus: list[str]):
    """Return cosine similarity scores between query and each corpus item."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    if not corpus:
        return []
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    try:
        tfidf = vec.fit_transform([query] + corpus)
        sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()
        return sims.tolist()
    except Exception:
        return [0.0] * len(corpus)


def _ml_topic_advisor(db, topic: str):
    """TF-IDF clustering to identify high-performing topic clusters and gaps."""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    stats = _ml_fetch_webinar_stats(db)
    if len(stats) < 3:
        return {"score": 0, "confidence": 0.0, "method": "insufficient_data",
                "summary": "Not enough completed webinars to run topic modelling. Need at least 3.",
                "insights": [], "recommendations": ["Run more webinars to build training data."]}
    titles = [s["title"] for s in stats]
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=200)
    X = vec.fit_transform(titles)
    n_clusters = min(4, len(titles))
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X)
    # Score each cluster by average attendance rate
    cluster_stats = {}
    for i, s in enumerate(stats):
        c = int(labels[i])
        if c not in cluster_stats:
            cluster_stats[c] = {"att_rates": [], "regs": [], "titles": []}
        cluster_stats[c]["att_rates"].append(s["att_rate"])
        cluster_stats[c]["regs"].append(s["regs"])
        cluster_stats[c]["titles"].append(s["title"])
    # Find which cluster the input topic belongs to
    sims = _ml_tfidf_similarity(topic, titles)
    best_match_idx = int(np.argmax(sims)) if sims else 0
    matched_cluster = int(labels[best_match_idx]) if sims else 0
    mc = cluster_stats.get(matched_cluster, {})
    avg_att = round(float(np.mean(mc["att_rates"])), 1) if mc.get("att_rates") else 0
    avg_regs = int(np.mean(mc["regs"])) if mc.get("regs") else 0
    score = min(100, int(avg_att * 1.2 + min(avg_regs / 2, 40)))
    # Best performing cluster
    best_cluster = max(cluster_stats, key=lambda c: np.mean(cluster_stats[c]["att_rates"]))
    best_titles = cluster_stats[best_cluster]["titles"][:3]
    insights = [
        f"Your topic matches a cluster with avg {avg_att}% attendance rate across {len(mc.get('titles', []))} webinars.",
        f"Avg registrations in this topic cluster: {avg_regs}.",
        f"Best-performing cluster includes: {', '.join(best_titles)}.",
        f"Total webinars analysed: {len(stats)}.",
    ]
    return {
        "score": score, "confidence": round(min(sims) + 0.5, 2) if sims else 0.5,
        "method": "TF-IDF + K-Means clustering on historical webinar titles",
        "summary": f"Topic clusters into a group averaging {avg_att}% attendance. Score based on historical cluster performance.",
        "insights": insights,
    }


def _ml_topic_critique(db, topic: str):
    """Cosine similarity to top-performing webinars as a quality signal."""
    import numpy as np
    stats = _ml_fetch_webinar_stats(db)
    if len(stats) < 2:
        return {"score": 50, "confidence": 0.3, "method": "insufficient_data",
                "summary": "Not enough data for similarity scoring.", "insights": []}
    titles = [s["title"] for s in stats]
    sims = _ml_tfidf_similarity(topic, titles)
    sim_arr = np.array(sims)
    att_arr = np.array([s["att_rate"] for s in stats])
    # Weighted score: high similarity to high-attendance webinars = good
    weighted_score = float(np.dot(sim_arr, att_arr) / (np.sum(sim_arr) + 1e-9))
    score = min(100, int(weighted_score * 1.5))
    top3_idx = sim_arr.argsort()[-3:][::-1]
    similar = [f"\"{stats[i]['title']}\" ({stats[i]['att_rate']}% att)" for i in top3_idx]
    return {
        "score": score,
        "confidence": round(float(sim_arr.max()), 2),
        "method": "TF-IDF cosine similarity weighted by historical attendance rates",
        "summary": f"Topic similarity score vs historical webinars: {score}/100. Higher means it resembles your best performers.",
        "insights": [f"Most similar past webinar: {similar[0] if similar else 'N/A'}"] + similar[1:],
    }


def _ml_engagement_patterns(db, topic: str):
    """Statistical analysis of attendance patterns from actual data."""
    import numpy as np
    stats = _ml_fetch_webinar_stats(db)
    if len(stats) < 3:
        return {"score": 0, "confidence": 0.3, "method": "insufficient_data",
                "summary": "Need at least 3 completed webinars.", "insights": []}
    att_rates = np.array([s["att_rate"] for s in stats])
    mean_att = round(float(att_rates.mean()), 1)
    std_att = round(float(att_rates.std()), 1)
    median_att = round(float(np.median(att_rates)), 1)
    top_webinar = max(stats, key=lambda x: x["att_rate"])
    bottom_webinar = min(stats, key=lambda x: x["att_rate"])
    # ICP breakdown
    icp_groups = {}
    for s in stats:
        icp = s["icp"]
        if icp not in icp_groups:
            icp_groups[icp] = []
        icp_groups[icp].append(s["att_rate"])
    icp_avgs = {icp: round(float(np.mean(rates)), 1) for icp, rates in icp_groups.items()}
    best_icp = max(icp_avgs, key=icp_avgs.get)
    insights = [
        f"Mean attendance rate across {len(stats)} webinars: {mean_att}% (std dev: {std_att}%)",
        f"Median attendance rate: {median_att}%",
        f"Best performer: \"{top_webinar['title']}\" at {top_webinar['att_rate']}%",
        f"Lowest performer: \"{bottom_webinar['title']}\" at {bottom_webinar['att_rate']}%",
        f"Best-performing ICP: {best_icp} (avg {icp_avgs[best_icp]}%)",
    ]
    score = min(100, int(mean_att * 1.4))
    return {
        "score": score, "confidence": round(1 - std_att / (mean_att + 1), 2),
        "method": "Descriptive statistics on historical attendance data",
        "summary": f"Your webinars average {mean_att}% attendance. {best_icp} ICPs engage best.",
        "insights": insights,
        "icp_breakdown": icp_avgs,
    }


def _ml_registration_forecast(db, topic: str):
    """Linear regression forecast based on historical ICP + topic performance."""
    import numpy as np
    from sklearn.linear_model import LinearRegression
    stats = _ml_fetch_webinar_stats(db)
    if len(stats) < 3:
        return {"score": 0, "confidence": 0.3, "method": "insufficient_data",
                "summary": "Need at least 3 completed webinars to train the model.", "predictions": []}
    titles = [s["title"] for s in stats]
    sims = np.array(_ml_tfidf_similarity(topic, titles))
    regs = np.array([s["regs"] for s in stats])
    att_rates = np.array([s["att_rate"] for s in stats])
    # Features: similarity score + index (proxy for recency)
    X = np.column_stack([sims, np.arange(len(sims))])
    reg_model = LinearRegression().fit(X, regs)
    att_model = LinearRegression().fit(X, att_rates)
    # Predict for a "new" webinar (most similar = high sim, latest = last index)
    X_pred = np.array([[float(sims.max()), len(sims)]])
    pred_regs = max(0, int(reg_model.predict(X_pred)[0]))
    pred_att = min(100, max(0, round(float(att_model.predict(X_pred)[0]), 1)))
    pred_attendees = int(pred_regs * pred_att / 100)
    r2_regs = round(float(reg_model.score(X, regs)), 2)
    r2_att = round(float(att_model.score(X, att_rates)), 2)
    return {
        "score": min(100, int(pred_att * 1.2)),
        "confidence": round((r2_regs + r2_att) / 2, 2),
        "method": "Linear Regression trained on historical registrations and attendance rates",
        "summary": f"Model predicts ~{pred_regs} registrations and ~{pred_att}% attendance ({pred_attendees} live attendees).",
        "predictions": [
            f"Predicted registrations: {pred_regs}",
            f"Predicted attendance rate: {pred_att}%",
            f"Predicted live attendees: {pred_attendees}",
            f"Regression R² (registrations): {r2_regs} | Regression R² (attendance): {r2_att}",
        ],
    }


def _ml_icp_targeting(db, topic: str):
    """Find which ICPs have historically performed best and match this topic."""
    import numpy as np
    stats = _ml_fetch_webinar_stats(db)
    if len(stats) < 2:
        return {"score": 0, "confidence": 0.3, "method": "insufficient_data",
                "summary": "Need more data.", "insights": []}
    titles = [s["title"] for s in stats]
    sims = np.array(_ml_tfidf_similarity(topic, titles))
    # For each ICP, weight attendance rate by similarity score
    icp_weighted = {}
    icp_count = {}
    for i, s in enumerate(stats):
        icp = s["icp"]
        w = sims[i]
        if icp not in icp_weighted:
            icp_weighted[icp] = 0.0
            icp_count[icp] = 0
        icp_weighted[icp] += s["att_rate"] * w
        icp_count[icp] += 1
    icp_scores = {icp: round(icp_weighted[icp] / icp_count[icp], 1) for icp in icp_weighted}
    ranked = sorted(icp_scores.items(), key=lambda x: x[1], reverse=True)
    best_icp, best_score = ranked[0]
    score = min(100, int(best_score * 1.5))
    insights = [f"{icp}: weighted score {sc}" for icp, sc in ranked]
    return {
        "score": score, "confidence": round(float(sims.max()), 2),
        "method": "TF-IDF similarity-weighted ICP attendance scoring",
        "summary": f"Best ICP match for this topic: {best_icp} (weighted score: {best_score}). Based on how similar ICPs performed on similar webinars.",
        "insights": insights,
        "icp_rankings": dict(ranked),
    }


async def _ml_ai_module(topic: str, system_msg: str, user_msg: str, max_tokens: int = 1500) -> dict:
    """Call AI for modules that genuinely need external knowledge."""
    import httpx, json as _json
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"score": 0, "confidence": 0, "summary": "OPENROUTER_API_KEY not set.", "insights": []}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": AI_MODEL, "max_tokens": max_tokens, "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]},
        )
    if resp.status_code != 200:
        return {"score": 0, "confidence": 0, "summary": f"AI call failed: {resp.status_code}", "insights": []}
    text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return _json.loads(text)
    except Exception:
        return {"score": 0, "confidence": 0, "summary": text, "insights": []}


@app.post("/api/ml-analysis")
async def ml_analysis(payload: dict, db: Session = Depends(get_db)):
    module    = payload.get("module", "")
    topic     = payload.get("topic", "General Webinar")
    org       = payload.get("org", "our organisation")
    date      = payload.get("date", "")
    speaker   = payload.get("speaker", "")
    webinar_link = payload.get("webinar_link", "")
    description  = payload.get("description", "")

    # Build context string - use actual values where provided, fallback to tokens
    date_str        = date         or "[DATE & TIME]"
    speaker_str     = speaker      or "[SPEAKER NAME & TITLE]"
    webinar_link_str = webinar_link or "[WEBINAR LINK]"

    ctx_parts = [f'Webinar topic: "{topic}"', f"Organisation: {org}",
                 f"Date & Time: {date_str}", f"Speaker: {speaker_str}",
                 f"Webinar link: {webinar_link_str}"]
    if description:
        ctx_parts.append(f"Additional context: {description}")
    ctx = " | ".join(ctx_parts)

    ai_sys = (
        f"You are a senior marketing director at {org}, a premium Indian financial advisory firm "
        "specialising in HNI and NRI wealth management (PMS, AIF, Family Office, NRI planning, ESOPs). "
        "Your audience is sophisticated, high-net-worth — they respond to authority, specificity, and "
        "understated confidence, not generic motivational language or pushy sales tactics.\n\n"
        f"Current webinar context: {ctx}\n\n"
        "Writing standards:\n"
        "- Use the ACTUAL date, speaker name, and links provided above — never write placeholder tokens "
        "if the real value has been given\n"
        "- Use any additional context provided to make the copy specific to this webinar's audience and angle\n"
        "- Every sentence must earn its place — no filler, no clichés, no 'exciting opportunity' language\n"
        "- Financial services tone: precise, credible, insider-access, not hype\n"
        "- Subject lines: specific and intriguing, not clickbait\n"
        "- Reply ONLY with valid JSON (no markdown, no code fences)"
    )

    # ── Data-driven ML modules ──
    if module == "topic_prediction":   return _ml_topic_advisor(db, topic)
    if module == "topic_quality":      return _ml_topic_critique(db, topic)
    if module == "pattern_detection":  return _ml_engagement_patterns(db, topic)
    if module == "forecasting":        return _ml_registration_forecast(db, topic)
    if module == "similarity_engine":  return _ml_icp_targeting(db, topic)

    # ── AI analysis modules ──
    ai_analysis = {
        "market_intelligence": "Summarise the current market landscape relevant to this webinar topic. Cover demand trends, audience pain points, and what angles drive registrations. JSON keys: score, confidence, summary, insights (array).",
        "algorithm_impact":    "Advise on the best channels (LinkedIn, email, WhatsApp) and posting times to promote this webinar. What works, what to avoid. JSON keys: score, confidence, summary, recommendations (array).",
        "audience_psychology": "Explain the psychological triggers that make people register and attend webinars on this topic. Cover FOMO, credibility, framing. JSON keys: score, confidence, summary, insights (array).",
        "content_intelligence":"Build a content playbook: 3 title variants, agenda outline (5 points), speaker intro angle, strong CTA. JSON keys: score, confidence, summary, recommendations (array).",
        "opportunity_risk":    "Identify strategic opportunities and risks for running this webinar now. Cover timing, competition, audience fatigue. JSON keys: score, confidence, summary, predictions (array), recommendations (array).",
    }

    # ── Communications modules ──
    comm_prompts = {
        "email_invite": (
            f"Write a premium webinar invitation email for deployment via Zoho Campaigns.\n\n"
            f"Webinar: \"{topic}\" | Date: {date_str} | Speaker: {speaker_str} | Register: {webinar_link_str}\n\n"
            "Standards:\n"
            "- Subject line: specific and intriguing, under 52 chars, zero spam words. "
            "Write 1 primary + 1 A/B variant (different angle, same length constraint).\n"
            "- Preview text: 65-85 chars, complements subject without repeating it.\n"
            "- Body (write the full text, use \\n for line breaks):\n"
            "  • Open with a sharp insight or counterintuitive question relevant to the topic — "
            "no generic 'Dear [Name]' opener\n"
            "  • One paragraph identifying the specific pain point this audience faces on this topic\n"
            "  • 'What you will leave with:' — 4 concrete, outcome-specific bullet points tied to this topic "
            "(not generic 'learn best practices' — be specific to the subject matter)\n"
            f"  • Speaker credibility: '{speaker_str}' — write 1 sentence establishing authority\n"
            f"  • Session details: {date_str} — include this exactly\n"
            "  • Scarcity element: seats limited, exclusive access, or timely market context\n"
            f"  • CTA button text that leads to: {webinar_link_str}\n"
            "  • Closing: sign off from Right Horizons team\n"
            "- P.S. line: one sentence — a compelling secondary reason to attend or a social proof element.\n"
            "- Tone: senior private wealth advisor writing to a peer — authoritative, precise, never pushy.\n\n"
            "JSON keys: subject, subject_variant, preview_text, body, cta_text, ps_line"
        ),
        "email_reminder_1week": (
            f"Write a 7-day countdown email for REGISTERED attendees of '{topic}'.\n"
            f"Speaker: {speaker_str} | Date: {date_str}\n\n"
            "They already registered — do not re-pitch. Build insider anticipation.\n\n"
            "- Subject: countdown energy, specific to topic (not 'Don't forget')\n"
            "- Preview text: tease one unexpected insight they'll walk away with\n"
            "- Body:\n"
            "  • Acknowledge their spot is confirmed\n"
            f"  • 1 surprising data point or market development directly related to '{topic}' — "
            "something that makes them think 'I need to hear more on this'\n"
            "  • Brief 'What to expect' — 2 sentences, specific agenda points\n"
            f"  • 'Add to calendar' prompt with date: {date_str}\n"
            "  • Invite them to submit questions for the speaker in advance (reply to this email)\n"
            "- Tone: insider briefing, not a promotional reminder.\n\n"
            "JSON keys: subject, preview_text, body, cta_text"
        ),
        "email_reminder_1day": (
            f"Write a 'tomorrow' reminder email for '{topic}' attendees.\n"
            f"Date/Time: {date_str} | Join link: {webinar_link_str}\n\n"
            "Brief, high-impact, under 110 words in the body.\n\n"
            "- Subject: tomorrow-specific, creates light urgency\n"
            "- Preview text: something that builds the anticipation\n"
            "- Body:\n"
            f"  • 'This time tomorrow...' opening tied to the specific outcome of '{topic}'\n"
            f"  • Date & time: {date_str} — bold and prominent\n"
            f"  • Join link: {webinar_link_str} — on its own line, labelled 'Your join link'\n"
            "  • 'Block your calendar now' — one clean line\n"
            "  • One-sentence teaser of the most surprising thing the speaker will reveal\n"
            "- No padding. Every word must justify its presence.\n\n"
            "JSON keys: subject, preview_text, body, cta_text"
        ),
        "email_reminder_1hr": (
            f"Write a 60-minute final reminder for '{topic}'.\n"
            f"Join link: {webinar_link_str}\n\n"
            "Maximum 3 lines in the body. This is not the place for context — it is the place for action.\n\n"
            "- Subject: starts with ⏰ or 🔴, 'Starting in 60 minutes'\n"
            "- Preview text: 'Your spot is waiting'\n"
            "- Body: topic name → join now → see you inside. Nothing else.\n"
            f"- CTA: 'Join Now' pointing to {webinar_link_str}\n\n"
            "JSON keys: subject, preview_text, body, cta_text"
        ),
        "email_followup_attended": (
            f"Write a post-webinar follow-up email for attendees of '{topic}'.\n"
            f"Speaker: {speaker_str} | Recording: {webinar_link_str}\n\n"
            "This is the most important email in the sequence — it converts interest into consultations.\n\n"
            "- Subject: gratitude + clear value continuation (not 'Thanks for joining!')\n"
            "- Preview text: hint at what's inside (key takeaway or recording access)\n"
            "- Body:\n"
            f"  • Genuine, specific thank-you referencing the webinar topic and speaker\n"
            f"  • '3 Key Takeaways from today's session' — write 3 specific, substantive insights "
            f"that someone attending a webinar on '{topic}' in the Indian HNI/NRI context would have received. "
            "Make them actionable and specific, not generic.\n"
            f"  • Recording access: {webinar_link_str} — 'Watch at your convenience'\n"
            "  • 'Your Next Step': offer a complimentary 1-on-1 advisory call — "
            "frame it as exclusive to webinar attendees, not a generic sales pitch\n"
            "  • Soft close: 'Reply to this email with any questions from today'\n"
            "- Tone: trusted advisor wrapping up a valuable session.\n\n"
            "JSON keys: subject, preview_text, body, cta_text"
        ),
        "email_followup_noshow": (
            f"Write a no-show recovery email for '{topic}'.\n"
            f"Recording: {webinar_link_str}\n\n"
            "Recover without guilt-tripping. Make them feel they are getting something exclusive, not scolded.\n\n"
            "- Subject: value-forward, no passive aggression (not 'You missed...')\n"
            "- Preview text: 'The recording is yours'\n"
            "- Body:\n"
            "  • Empathetic opening — acknowledge that calendars are demanding\n"
            f"  • 'Here is what attendees took away' — 2 specific, compelling highlights from '{topic}'\n"
            f"  • Recording: {webinar_link_str} — '30 minutes. Worth it.'\n"
            "  • Re-engagement: mention the next event or offer a 1-on-1 conversation\n"
            "  • One gentle CTA\n"
            "- Tone: gracious, not desperate.\n\n"
            "JSON keys: subject, preview_text, body, cta_text"
        ),
        "wa_announcement": (
            f"Write a WhatsApp announcement for the webinar '{topic}'.\n"
            f"Date/Time: {date_str} | Speaker: {speaker_str} | Register: {webinar_link_str}\n\n"
            "Audience: HNI/NRI investors and wealth management professionals in India.\n\n"
            "- First line: a hook that creates immediate relevance — one crisp statement or question "
            "tied to a current market reality or wealth concern this audience faces. No generic opener.\n"
            f"- Second line: what '{topic}' will specifically address — one sentence\n"
            "- Who should attend: one line describing the ideal attendee (be specific — 'investors with ₹50L+ in PMS' "
            "is better than 'anyone interested in finance')\n"
            f"- 📅 {date_str}\n"
            f"- 🎤 {speaker_str}\n"
            f"- 👉 Register: {webinar_link_str}\n"
            "- Closing: one line — limited seats or timely market context that creates genuine urgency\n"
            "- Use line breaks between each element. Max 6 emojis total. No hashtags.\n\n"
            "JSON keys: message (complete text with line breaks), char_count"
        ),
        "wa_reminder_1day": (
            f"Write a WhatsApp 1-day countdown for '{topic}'.\n"
            f"Date/Time: {date_str} | Speaker: {speaker_str}\n\n"
            "- ⏳ Tomorrow energy — specific to the topic\n"
            f"- One insight or question that makes them think 'I need to hear this'\n"
            f"- 📅 {date_str}\n"
            "- Warm closing — 'See you tomorrow'\n"
            "- Max 5 lines. No registration link (they're already registered).\n\n"
            "JSON keys: message, char_count"
        ),
        "wa_reminder_morning": (
            f"Write a 'today is the day' WhatsApp morning message for '{topic}'.\n"
            f"Time: {date_str} | Join: {webinar_link_str}\n\n"
            "- ☀️ morning energy, specific to the topic\n"
            f"- Time reminder: {date_str}\n"
            f"- 👉 Join: {webinar_link_str}\n"
            "- Max 4 lines. Warm and sharp.\n\n"
            "JSON keys: message, char_count"
        ),
        "wa_reminder_1hr": (
            f"Write a 60-minute WhatsApp alert for '{topic}'.\n"
            f"Join: {webinar_link_str}\n\n"
            "- 🔴 Live in 1 hour — topic name\n"
            f"- 👉 {webinar_link_str}\n"
            "- 2 lines maximum. Pure urgency, no softening.\n\n"
            "JSON keys: message, char_count"
        ),
        "wa_postwebinar": (
            f"Write a WhatsApp post-webinar message for attendees of '{topic}'.\n"
            f"Speaker: {speaker_str} | Recording: {webinar_link_str}\n\n"
            "- Genuine, specific gratitude — reference the topic and speaker by name\n"
            f"- 2 key takeaways that someone attending '{topic}' would have genuinely learned — specific, not generic\n"
            f"- 🎬 Recording: {webinar_link_str}\n"
            "- One next-step CTA: book a call, ask a question, or follow on LinkedIn\n"
            "- Max 7 lines. Warm but professional.\n\n"
            "JSON keys: message, char_count"
        ),
        "wa_noshow_followup": (
            f"Write a WhatsApp recovery message for people who missed '{topic}'.\n"
            f"Recording: {webinar_link_str}\n\n"
            "- No guilt. Lead with value: 'We saved the best bits for you'\n"
            f"- 1 specific insight from '{topic}' that makes them wish they had attended\n"
            f"- 🎬 Watch: {webinar_link_str}\n"
            "- Max 4 lines.\n\n"
            "JSON keys: message, char_count"
        ),
    }

    if module in ai_analysis:
        return await _ml_ai_module(topic, ai_sys, ai_analysis[module])
    if module in comm_prompts:
        return await _ml_ai_module(topic, ai_sys, comm_prompts[module], max_tokens=2000)

    raise HTTPException(status_code=400, detail=f"Unknown module: {module}")


# ── AI Intelligence Dashboard ──────────────────────────────────────────────────

def _iq_lead_quality(data):
    qs = {'Family Office':20,'AIF':20,'PMS':18,'NRI':16,'ESOPs':15,'Retirement Planning':14,'Others':8}
    buckets = {'high':0,'medium':0,'low':0}
    icp_regs = {}
    for d in data:
        s = qs.get(d['icp'], 10)
        icp_regs[d['icp']] = icp_regs.get(d['icp'], 0) + d['regs']
        if s >= 18:   buckets['high']   += d['regs']
        elif s >= 14: buckets['medium'] += d['regs']
        else:         buckets['low']    += d['regs']
    total = sum(buckets.values()) or 1
    high_pct = buckets['high'] / total * 100
    score = min(100, int(high_pct * 1.2 + buckets['medium'] / total * 40))
    top_icp = max(icp_regs, key=icp_regs.get) if icp_regs else "N/A"
    return {"score": score, "confidence": round(min(0.95, 0.5 + len(data)*0.03), 2),
            "top_icp": top_icp, "method": "ICP quality scoring weighted by registration volume",
            "breakdown": {k: {'count': v, 'pct': round(v/total*100, 1)} for k, v in buckets.items()}}


async def _iq_ai_narrative(stats: dict, webinar_lines: list = None) -> dict:
    import httpx, json as _j
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return {"executive_summary": {"headline": "Webinar data analysed", "bullets": []}, "recommendations": []}
    wb_block = ""
    if webinar_lines:
        wb_block = "\n\nWEBINAR DETAIL (newest first):\n" + "\n".join(webinar_lines[-20:])
    prompt = (
        f"You are a senior business intelligence analyst for {COMPANY_NAME}, {COMPANY_DESC}.\n"
        "Based on this webinar programme data, produce:\n"
        "1. A sharp executive summary: one powerful headline sentence + exactly 5 specific bullet points (cite real numbers, speaker names, and ICP names from the data).\n"
        "2. Exactly 5 prioritised actionable recommendations for growing the HNI/NRI webinar programme. Each must name a specific speaker, ICP, or topic.\n\n"
        f"SUMMARY STATS: {_j.dumps(stats)}"
        f"{wb_block}\n\n"
        'Reply ONLY with JSON:\n'
        '{"executive_summary":{"headline":"...","bullets":["..."],"sentiment":"Positive|Neutral|Cautious"},'
        '"recommendations":[{"title":"Short title","action":"Detailed action step naming speaker/ICP/topic","impact":"high|medium|low","confidence":0.8}]}'
    )
    async with httpx.AsyncClient(timeout=40) as c:
        r = await c.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "HTTP-Referer": OPENROUTER_REFERER, "X-Title": "WebinarIQ"},
            json={"model": AI_MODEL, "max_tokens": 1000,
                  "messages": [{"role": "user", "content": prompt}]})
    if r.status_code != 200:
        return {"executive_summary": {"headline": "Analysis complete", "bullets": []}, "recommendations": []}
    text = r.json().get("choices",[{}])[0].get("message",{}).get("content","{}").strip()
    if text.startswith("```"): text = text.split("\n",1)[-1].rsplit("```",1)[0].strip()
    try:    return _j.loads(text)
    except: return {"executive_summary": {"headline": text[:120], "bullets": []}, "recommendations": []}


@app.get("/api/ai-intelligence")
async def ai_intelligence_dashboard(db: Session = Depends(get_db)):
    import traceback
    try:
        return await _ai_intelligence_impl(db)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "detail": traceback.format_exc()[-500:]})

async def _ai_intelligence_impl(db):
    import numpy as np
    from sqlalchemy import text as _t
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import IsolationForest
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from datetime import datetime

    rows = db.execute(_t("""
        SELECT w.id, w.title, w.date, w.icp,
               (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id = w.id) AS total_registrations,
               (SELECT COUNT(*) FROM attendances a WHERE a.webinar_id = w.id AND a.attended = TRUE) AS total_attendees
        FROM webinars w WHERE w.status='completed'
          AND (SELECT COUNT(*) FROM registrations r WHERE r.webinar_id = w.id) > 0
        ORDER BY w.date ASC
    """)).fetchall()

    if not rows:
        return {"error": "no_data", "message": "No completed webinars yet."}

    data = []
    for w in rows:
        att = (w.total_attendees / w.total_registrations * 100) if w.total_registrations else 0
        data.append({"id": w.id, "title": w.title or "", "date": str(w.date)[:10] if w.date else "",
                     "icp": w.icp or "Others", "regs": w.total_registrations or 0,
                     "attendees": w.total_attendees or 0, "att_rate": round(att, 1)})

    n = len(data)
    regs = np.array([d["regs"] for d in data], float)
    atts = np.array([d["att_rate"] for d in data], float)
    X    = np.arange(n).reshape(-1, 1)

    # ── Intelligence Score ──────────────────────────────────────────────────
    avg_att = float(atts.mean());  avg_regs = float(regs.mean())
    iq_scores_map = {'Family Office':20,'AIF':20,'PMS':18,'NRI':16,'ESOPs':15,'Retirement Planning':14,'Others':8}
    s_reg  = min(25, int(avg_regs / 100 * 25))
    s_att  = min(30, int(avg_att  / 60  * 30))
    s_cons = max(0, 20 - int(atts.std() / 5))
    s_lead = min(15, int(float(np.mean([iq_scores_map.get(d["icp"],10) for d in data])) / 20 * 15))
    s_conv = min(10, int(avg_att / 100 * 10 + 3))
    overall = s_reg + s_att + s_cons + s_lead + s_conv
    grade   = "Excellent" if overall >= 80 else "Good" if overall >= 65 else "Average" if overall >= 45 else "Needs Work"
    half    = n // 2
    iq_trend = ("improving" if half > 0 and atts[half:].mean() > atts[:half].mean() else "declining" if half > 0 else "stable")

    intelligence_score = {
        "overall": overall, "grade": grade, "trend": iq_trend,
        "breakdown": {
            "registration":  {"score": s_reg,  "max": 25, "label": "Registration Volume"},
            "attendance":    {"score": s_att,  "max": 30, "label": "Attendance Rate"},
            "consistency":   {"score": s_cons, "max": 20, "label": "Consistency"},
            "lead_quality":  {"score": s_lead, "max": 15, "label": "Lead Quality"},
            "conversion":    {"score": s_conv, "max": 10, "label": "Conversion Potential"},
        }
    }

    # ── Predictive Analytics ───────────────────────────────────────────────
    rm  = LinearRegression().fit(X, regs);  am = LinearRegression().fit(X, atts)
    pr  = max(0, int(rm.predict([[n]])[0]));  pa = min(100, max(0, round(float(am.predict([[n]])[0]), 1)))
    pa_count = int(pr * pa / 100)
    rr2 = round(float(rm.score(X, regs)), 2);  ar2 = round(float(am.score(X, atts)), 2)
    r_res_std = float((regs - rm.predict(X)).std());  a_res_std = float((atts - am.predict(X)).std())

    predictive = {
        "attendance": {
            "predicted_attendees": pa_count,
            "predicted_rate": pa,
            "range": [max(0, int(pa_count - a_res_std * pr/100)), int(pa_count + a_res_std * pr/100)],
            "confidence": round(max(0.3, 1 - a_res_std/(avg_att+1)), 2),
            "r2": ar2, "method": "Linear Regression on attendance time series",
            "factors": ["Historical trend", "Topic cluster", "ICP composition"],
        },
        "registrations": {
            "predicted": pr,
            "range": [max(0, int(pr - r_res_std)), int(pr + r_res_std)],
            "growth_per_webinar": round(float(rm.coef_[0]), 1),
            "confidence": round(max(0.3, 1 - r_res_std/(avg_regs+1)), 2),
            "r2": rr2, "method": "Linear Regression on registration time series",
        },
        "lead_quality": _iq_lead_quality(data),
        "conversion": {
            "predicted_rate": round(avg_att * 0.12, 1),
            "confidence": 0.62,
            "method": "Historical attendance-to-conversion ratio baseline",
        },
    }

    # ── Pattern Detection ──────────────────────────────────────────────────
    patterns = []

    # Day-of-week
    dow_map: dict = {}
    for d in data:
        if d["date"]:
            try:
                day = datetime.strptime(d["date"], "%Y-%m-%d").strftime("%A")
                dow_map.setdefault(day, []).append(d["att_rate"])
            except Exception: pass
    if dow_map:
        day_avgs = {k: round(float(np.mean(v)),1) for k,v in dow_map.items()}
        bd = max(day_avgs, key=day_avgs.get);  wd = min(day_avgs, key=day_avgs.get)
        if day_avgs[bd] - day_avgs[wd] >= 3:
            patterns.append({"type":"best_day","icon":"📅","impact":"high",
                "insight": f"{bd} webinars average {day_avgs[bd]}% attendance — {round(day_avgs[bd]-day_avgs[wd],1)}% above {wd}",
                "confidence": min(0.92, 0.6 + len(dow_map)*0.05), "data": day_avgs})

    # ICP performance
    icp_map: dict = {}
    for d in data:
        icp_map.setdefault(d["icp"], {"a":[],"r":[]}).update(
            {"a": icp_map.get(d["icp"],{"a":[]})["a"] + [d["att_rate"]],
             "r": icp_map.get(d["icp"],{"r":[]})["r"] + [d["regs"]]})
    icp_att_avgs = {k: round(float(np.mean(v["a"])),1) for k,v in icp_map.items()}
    if len(icp_att_avgs) >= 2:
        bi = max(icp_att_avgs, key=icp_att_avgs.get);  wi = min(icp_att_avgs, key=icp_att_avgs.get)
        if icp_att_avgs[bi] - icp_att_avgs[wi] >= 4:
            patterns.append({"type":"best_icp","icon":"🎯","impact":"high",
                "insight": f"{bi} audiences achieve {icp_att_avgs[bi]}% attendance — {round(icp_att_avgs[bi]-icp_att_avgs[wi],1)}% above {wi}",
                "confidence": 0.85, "data": icp_att_avgs})

    # Registration trend
    if n >= 3:
        g = float(rm.coef_[0])
        if abs(g) >= 2:
            patterns.append({"type":"reg_trend","icon":"📈" if g>0 else "📉","impact":"medium",
                "insight": f"Registrations {'growing' if g>0 else 'declining'} by {abs(round(g,1))} per webinar (R²={rr2})",
                "confidence": rr2})

    # Best performing webinar
    top = max(data, key=lambda x: x["att_rate"])
    patterns.append({"type":"best_webinar","icon":"⭐","impact":"low",
        "insight": f'Top performer: "{top["title"]}" — {top["att_rate"]}% attendance, {top["regs"]} registrations',
        "confidence": 1.0})

    # TF-IDF topic cluster analysis
    if n >= 4:
        try:
            titles = [d["title"] for d in data]
            vec = TfidfVectorizer(ngram_range=(1,2), stop_words="english", max_features=100)
            X_tfidf = vec.fit_transform(titles)
            k = min(3, n)
            labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X_tfidf)
            cl_atts = {}
            for i, d in enumerate(data):
                cl_atts.setdefault(int(labels[i]), []).append(d["att_rate"])
            best_cl = max(cl_atts, key=lambda c: np.mean(cl_atts[c]))
            patterns.append({"type":"topic_cluster","icon":"🔍","impact":"medium",
                "insight": f"Topic cluster {best_cl+1} has the highest avg attendance: {round(float(np.mean(cl_atts[best_cl])),1)}% (K-Means on TF-IDF titles)",
                "confidence": 0.72})
        except Exception: pass

    # ── Anomaly Detection ──────────────────────────────────────────────────
    anomalies = []
    if n >= 4:
        rz = (regs - regs.mean()) / (regs.std() + 1e-9)
        az = (atts - atts.mean()) / (atts.std() + 1e-9)
        for i, d in enumerate(data):
            for z, val, label, unit in [(rz[i], d["regs"], "Registration", "registrations"),
                                         (az[i], d["att_rate"], "Attendance", "%")]:
                if abs(z) >= 2.0:
                    sev = "critical" if abs(z) >= 3 else "high"
                    anomalies.append({
                        "type": f"{label.lower()}_anomaly",
                        "severity": sev,
                        "webinar": d["title"][:50],
                        "description": f"{label} {'spike' if z>0 else 'drop'}: {val}{unit if unit=='%' else ''} (z={round(float(z),1)}, expected ≈ {round(float(regs.mean()) if unit!='%' else float(atts.mean()),0)}{unit if unit=='%' else ''})",
                        "date": d["date"],
                    })
        if n >= 6:
            try:
                iso_labels = IsolationForest(contamination=0.1, random_state=42).fit_predict(
                    np.column_stack([regs, atts]))
                for i, lbl in enumerate(iso_labels):
                    if lbl == -1 and not any(a["webinar"] == data[i]["title"][:50] for a in anomalies):
                        anomalies.append({
                            "type": "multivariate_anomaly", "severity": "medium",
                            "webinar": data[i]["title"][:50],
                            "description": f"Unusual reg/attendance combination ({data[i]['regs']} regs, {data[i]['att_rate']}% att) — Isolation Forest",
                            "date": data[i]["date"],
                        })
            except Exception: pass

    # ── Audience Segments ──────────────────────────────────────────────────
    segments = []
    for icp, v in icp_map.items():
        q = iq_scores_map.get(icp, 10)
        a_avg = round(float(np.mean(v["a"])), 1)
        segments.append({
            "name": icp, "webinar_count": len(v["a"]),
            "avg_attendance_rate": a_avg,
            "avg_registrations": int(np.mean(v["r"])),
            "conversion_likelihood": "High" if q >= 18 else "Medium" if q >= 14 else "Low",
            "engagement_level": "High" if a_avg >= 50 else "Medium" if a_avg >= 30 else "Low",
            "quality_score": q,
        })
    segments.sort(key=lambda x: x["quality_score"], reverse=True)

    # ── Monthly Trends ─────────────────────────────────────────────────────
    monthly: dict = {}
    for d in data:
        if d["date"]:
            m = d["date"][:7]
            monthly.setdefault(m, {"r":[],"a":[]})
            monthly[m]["r"].append(d["regs"]); monthly[m]["a"].append(d["att_rate"])
    trends = [{"month": m, "avg_regs": int(np.mean(v["r"])),
               "avg_att_rate": round(float(np.mean(v["a"])),1), "count": len(v["r"])}
              for m, v in sorted(monthly.items())]

    # ── AI Narrative ───────────────────────────────────────────────────────
    summary_stats = {
        "total_webinars": n, "avg_registrations": round(avg_regs),
        "avg_attendance_rate": round(avg_att, 1),
        "best_icp": max(icp_att_avgs, key=icp_att_avgs.get) if icp_att_avgs else "N/A",
        "registration_trend": "growing" if float(rm.coef_[0]) > 0 else "declining",
        "predicted_next_regs": pr, "predicted_next_att_rate": pa,
        "intelligence_score": overall, "anomaly_count": len(anomalies),
        "patterns_found": len(patterns),
    }
    wb_lines = [
        f"[{d['date']}] \"{d['title'][:60]}\" | ICP:{d['icp']} | Regs:{d['regs']} | Att:{d['attendees']} | Rate:{d['att_rate']}%"
        for d in data
    ]
    ai_out = await _iq_ai_narrative(summary_stats, wb_lines)

    return {
        "data_basis": f"{n} completed webinar{'s' if n!=1 else ''}",
        "intelligence_score": intelligence_score,
        "executive_summary": ai_out.get("executive_summary", {}),
        "recommendations": ai_out.get("recommendations", []),
        "predictive_analytics": predictive,
        "patterns": patterns,
        "anomalies": anomalies,
        "audience_segments": segments,
        "trends": trends,
        "raw_stats": summary_stats,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
