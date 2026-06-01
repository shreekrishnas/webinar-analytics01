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


# ── AI helpers ────────────────────────────────────────────────────────────────

def _extract_json(text: str):
    """Robust JSON extractor — handles markdown code fences, leading text, and trailing commas."""
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

    context = "\n".join(ctx_parts)

    system_prompt = f"""You are WebinarIQ Assistant, an AI analyst for Right Horizons Financial Services.

STRICT RULES (these are absolute, no exceptions):
1. You may ONLY use the LIVE DATA below to answer questions. Never invent numbers, never use external knowledge about markets, finance, world events, or anything not in the data.
2. If the user asks about something NOT in the data (e.g. "What is PMS?", "Tell me about NIFTY", "current market trends"), respond: "I can only answer questions about the webinar data shown in WebinarIQ. Try asking about speakers, ICPs, attendance, or specific webinars."
3. For COMPARISONS between webinars/speakers/ICPs in the data, that is allowed and encouraged - that's analysis of our data.
4. NEVER make up names, emails, dates, numbers, percentages. Only use what is in LIVE DATA below.
5. Be concise: under 180 words unless the user explicitly asks for more. Use bullets and bold for key numbers.

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
            json={"model": "anthropic/claude-haiku-4.5", "max_tokens": 600, "messages": messages},
            timeout=20.0
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


# ── Weekly Topic Suggestions ─────────────────────────────────────────────────

@app.get("/api/topics")
async def get_topic_suggestions():
    """Generate fresh weekly topic suggestions per speaker using AI."""
    import os, json, httpx
    from datetime import date

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

    today = date.today().strftime("%B %d, %Y")

    prompt = f"""Today is {today}. You are a webinar content strategist for Right Horizons, a premium Indian financial advisory firm.

Generate 3 highly specific, timely, non-generic webinar topic suggestions for each of these 5 speakers.

Use their exact framing style and topic DNA:

SPEAKER PROFILES:
- Rachna Rego: Retirement income (SWP, ₹1L monthly), PMS for wealth milestones, women & finance, child education savings, behavioral finance. Frames topics as personal journeys ("How I would...", "What changes now?", "The Real Math"). Never generic.
- Anil Rego: Macro events (budget, RBI, tariffs, geopolitics), ESOPs, portfolio repositioning, market timing. Reacts to breaking news. Frames as urgent decisions ("After X, what now?", "The tax trap", "Smart money is doing this").
- Sunil Kawariya: NRI investing (GIFT City, global asset allocation), large corpus (₹10Cr+), structured products, SIF, tax-efficient wealth. Frames as exclusive insider knowledge ("The strategy most NRIs miss", "₹X Crore , what changes").
- Preethi Shukla: Special needs children financial planning (3×), SIP mechanics, tax-efficient investing, corpus building. Frames as step-by-step systems and parent-focused empathy ("The gap nobody talks about", "Step-by-step for parents").
- Prabhat Ranjan: Equity markets, small/midcap, sectoral themes, PMS strategy, FY outlook. Co-presents with Vijay Chauhan. Frames as research-driven conviction ("Hidden in the data", "3 sectors the market hasn't priced in").

CONTEXT for {today}:
- India-Pakistan tensions post-Operation Sindoor, ceasefire holding but uncertainty remains
- RBI rate cut cycle beginning, repo rate moving lower
- US-India trade deal negotiations ongoing, tariff clarity improving
- GIFT City rapidly expanding, new fund categories approved
- Nifty near all-time highs, mid/smallcaps corrected 15-20% from peaks
- SIF (Specialised Investment Funds), new SEBI category launched
- Budget FY27: higher capital gains tax on equity, new NPS rules
- Rupee stabilizing at 84-85/USD
- Gold at record highs, ₹9,000+ per gram
- NPS Vatsalya (children's NPS) gaining traction

Return a JSON array with this exact structure:
[
  {{
    "speaker": "Rachna Rego",
    "color": "#8b5cf6",
    "topics": [
      {{
        "title": "exact webinar title",
        "hook": "one sharp sentence on why this topic is urgent right now and the tension it creates",
        "angle": "the unique Right Horizons angle that makes this different from generic content",
        "expected": "High/Medium registration expected based on past patterns"
      }}
    ]
  }}
]

Rules:
- Titles must feel like Rachna/Anil/Sunil/Preethi/Prabhat would say them, use ₹ figures, timeframes, specific scenarios
- No generic titles like "How to Invest Wisely" or "Understanding Mutual Funds"
- Hook must reference something happening TODAY in markets/news
- Return ONLY valid JSON, no markdown"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={
                "model": "anthropic/claude-haiku-4.5",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        topics = _extract_json(raw)
        return {"topics": topics, "generated_on": today}
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

Webinar data:
{json.dumps(metrics, indent=2, default=lambda o: float(o) if hasattr(o,'__float__') else str(o))}

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
                "model": "anthropic/claude-haiku-4.5",
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=25.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        analysis = _extract_json(raw)
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

Return ONLY the JSON, no markdown, no preamble."""

        import httpx
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://webinar-analytics-six.vercel.app", "X-Title": "WebinarIQ"},
            json={"model": "anthropic/claude-haiku-4.5", "max_tokens": 800,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=25.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        analysis = _extract_json(raw)

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
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=120"
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
