from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from datetime import date, datetime
from typing import List, Optional
import pandas as pd
import io
import models
import schemas


# ── Shared helpers ────────────────────────────────────────────────────────────

def _webinar_stats(db: Session, webinar_id: int) -> dict:
    """Single-query stats for one webinar (used for detail pages)."""
    sql = text("""
        SELECT
            COALESCE(r_stats.total_reg, 0)  AS total_registrations,
            COALESCE(a_stats.total_att, 0)  AS total_attendees,
            COALESCE(ul_dup.dup_removed, 0) AS duplicates_removed,
            COALESCE(ul_unm.unmatched, 0)   AS unmatched_attendees
        FROM (SELECT 1) base
        LEFT JOIN (
            SELECT COUNT(*) AS total_reg
            FROM registrations WHERE webinar_id = :wid
        ) r_stats ON TRUE
        LEFT JOIN (
            SELECT COUNT(*) AS total_att
            FROM attendances WHERE webinar_id = :wid AND attended = TRUE
        ) a_stats ON TRUE
        LEFT JOIN (
            SELECT SUM(duplicates_removed) AS dup_removed
            FROM upload_logs WHERE webinar_id = :wid
        ) ul_dup ON TRUE
        LEFT JOIN (
            SELECT SUM(unmatched_attendees) AS unmatched
            FROM upload_logs WHERE webinar_id = :wid AND file_type = 'attendees'
        ) ul_unm ON TRUE
    """)
    row = db.execute(sql, {"wid": webinar_id}).fetchone()
    total_reg = int(row.total_registrations or 0)
    total_att = int(row.total_attendees or 0)
    rate = round(total_att / total_reg * 100, 1) if total_reg > 0 else 0.0
    return {
        "total_registrations": total_reg,
        "total_attendees": total_att,
        "attendance_rate": rate,
        "duplicates_removed": int(row.duplicates_removed or 0),
        "unmatched_attendees": int(row.unmatched_attendees or 0),
    }


def _reg_by_source(db: Session, webinar_id: int) -> List[schemas.RegistrationBreakdown]:
    rows = (
        db.query(models.Registration.source, func.count(models.Registration.id).label("cnt"))
        .filter(models.Registration.webinar_id == webinar_id)
        .group_by(models.Registration.source)
        .all()
    )
    total = sum(r.cnt for r in rows)
    return [
        schemas.RegistrationBreakdown(
            source=r.source or "Unknown",
            count=r.cnt,
            percentage=round(r.cnt / total * 100, 1) if total else 0.0,
        )
        for r in rows
    ]


def _duration_breakdown(db: Session, webinar_id: int) -> List[schemas.DurationBreakdown]:
    """Use SQL aggregation — avoids loading thousands of rows into Python."""
    sql = text("""
        SELECT
            SUM(CASE WHEN COALESCE(duration_minutes, 0) < 15  THEN 1 ELSE 0 END) AS b0_15,
            SUM(CASE WHEN COALESCE(duration_minutes, 0) >= 15
                      AND COALESCE(duration_minutes, 0) < 30  THEN 1 ELSE 0 END) AS b15_30,
            SUM(CASE WHEN COALESCE(duration_minutes, 0) >= 30
                      AND COALESCE(duration_minutes, 0) < 45  THEN 1 ELSE 0 END) AS b30_45,
            SUM(CASE WHEN COALESCE(duration_minutes, 0) >= 45
                      AND COALESCE(duration_minutes, 0) < 60  THEN 1 ELSE 0 END) AS b45_60,
            SUM(CASE WHEN COALESCE(duration_minutes, 0) >= 60 THEN 1 ELSE 0 END) AS b60_plus,
            COUNT(*) AS total
        FROM attendances
        WHERE webinar_id = :wid AND attended = TRUE
    """)
    row = db.execute(sql, {"wid": webinar_id}).fetchone()
    total = int(row.total or 0)
    buckets = [
        ("0–15 min",  int(row.b0_15  or 0)),
        ("15–30 min", int(row.b15_30 or 0)),
        ("30–45 min", int(row.b30_45 or 0)),
        ("45–60 min", int(row.b45_60 or 0)),
        ("60+ min",   int(row.b60_plus or 0)),
    ]
    return [
        schemas.DurationBreakdown(
            range=label,
            count=cnt,
            percentage=round(cnt / total * 100, 1) if total else 0.0,
        )
        for label, cnt in buckets
    ]


def _get_ads(db: Session, webinar_id: int) -> List[schemas.WebinarAdOut]:
    ads = (
        db.query(models.WebinarAd)
        .filter(models.WebinarAd.webinar_id == webinar_id)
        .order_by(models.WebinarAd.created_at.desc())
        .all()
    )
    return [schemas.WebinarAdOut.model_validate(a) for a in ads]


def _upload_logs(db: Session, webinar_id: int) -> List[schemas.UploadLogOut]:
    logs = db.query(models.UploadLog).filter(
        models.UploadLog.webinar_id == webinar_id
    ).order_by(models.UploadLog.uploaded_at.desc()).all()
    return [schemas.UploadLogOut.model_validate(l) for l in logs]


def _has_data(db: Session, webinar_id: int, file_type: str) -> bool:
    if file_type == "registrations":
        return db.query(models.Registration).filter(
            models.Registration.webinar_id == webinar_id
        ).first() is not None
    else:
        return db.query(models.Attendance).filter(
            models.Attendance.webinar_id == webinar_id,
            models.Attendance.attended == True,
        ).first() is not None


def _to_summary(db: Session, w: models.Webinar) -> schemas.WebinarSummary:
    s = _webinar_stats(db, w.id)
    return schemas.WebinarSummary(
        id=w.id,
        title=w.title,
        date=w.date,
        time=w.time,
        speaker_name=w.speaker.name if w.speaker else "Unknown",
        speaker_id=w.speaker_id or 0,
        total_registrations=s["total_registrations"],
        total_attendees=s["total_attendees"],
        attendance_rate=s["attendance_rate"],
        status=w.status,
        icp=getattr(w, 'icp', None) or 'Others',
        has_registration_data=_has_data(db, w.id, "registrations"),
        has_attendee_data=_has_data(db, w.id, "attendees"),
    )


def _to_detail(db: Session, w: models.Webinar) -> schemas.WebinarDetail:
    s = _webinar_stats(db, w.id)
    return schemas.WebinarDetail(
        id=w.id,
        title=w.title,
        date=w.date,
        time=w.time,
        description=w.description,
        speaker_name=w.speaker.name if w.speaker else "Unknown",
        speaker_id=w.speaker_id or 0,
        total_registrations=s["total_registrations"],
        total_attendees=s["total_attendees"],
        attendance_rate=s["attendance_rate"],
        no_shows=s["total_registrations"] - s["total_attendees"],
        duplicates_removed=s["duplicates_removed"],
        unmatched_attendees=s["unmatched_attendees"],
        status=w.status,
        has_registration_data=_has_data(db, w.id, "registrations"),
        has_attendee_data=_has_data(db, w.id, "attendees"),
        registration_by_source=_reg_by_source(db, w.id),
        duration_breakdown=_duration_breakdown(db, w.id),
        upload_logs=_upload_logs(db, w.id),
        ads=_get_ads(db, w.id),
    )


# ── Webinar CRUD ──────────────────────────────────────────────────────────────

def create_webinar(db: Session, webinar_in: schemas.WebinarCreate) -> models.Webinar:
    speaker = db.query(models.Speaker).filter(
        func.lower(models.Speaker.name) == webinar_in.speaker_name.strip().lower()
    ).first()
    if not speaker:
        speaker = models.Speaker(
            name=webinar_in.speaker_name.strip(),
            email=webinar_in.speaker_email,
        )
        db.add(speaker)
        db.flush()

    webinar = models.Webinar(
        title=webinar_in.title.strip(),
        date=webinar_in.date,
        time=webinar_in.time,
        description=webinar_in.description,
        speaker_id=speaker.id,
        status=webinar_in.status,
    )
    db.add(webinar)
    db.commit()
    db.refresh(webinar)
    return webinar


def get_webinars_by_date(db: Session, date_str: str) -> List[schemas.WebinarSummary]:
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return []
    webinars = db.query(models.Webinar).filter(models.Webinar.date == d).all()
    return [_to_summary(db, w) for w in webinars]


def get_webinars_by_name(db: Session, name: str) -> List[schemas.WebinarSummary]:
    webinars = (
        db.query(models.Webinar)
        .filter(models.Webinar.title.ilike(f"%{name}%"))
        .order_by(models.Webinar.date.desc())
        .all()
    )
    return [_to_summary(db, w) for w in webinars]


def get_all_webinars(db: Session) -> List[schemas.WebinarSummary]:
    """
    Single bulk query replaces 62 × 6 = 372 individual queries.
    All stats fetched in one round-trip via LEFT JOINs.
    """
    sql = text("""
        SELECT
            w.id,
            w.title,
            w.date,
            w.time,
            w.status,
            COALESCE(w.icp, 'Others')            AS icp,
            COALESCE(w.speaker_id, 0)           AS speaker_id,
            COALESCE(s.name, 'Unknown')          AS speaker_name,
            COALESCE(r_stats.total_reg,  0)      AS total_registrations,
            COALESCE(a_stats.total_att,  0)      AS total_attendees,
            CASE WHEN real_r.real_reg  > 0 THEN 1 ELSE 0 END AS has_reg,
            CASE WHEN real_a.real_att  > 0 THEN 1 ELSE 0 END AS has_att
        FROM webinars w
        LEFT JOIN speakers s ON s.id = w.speaker_id
        LEFT JOIN (
            SELECT webinar_id, COUNT(*) AS total_reg
            FROM registrations
            GROUP BY webinar_id
        ) r_stats ON r_stats.webinar_id = w.id
        LEFT JOIN (
            SELECT webinar_id, COUNT(*) AS total_att
            FROM attendances
            WHERE attended = TRUE
            GROUP BY webinar_id
        ) a_stats ON a_stats.webinar_id = w.id
        LEFT JOIN (
            SELECT webinar_id, COUNT(*) AS real_reg
            FROM registrations
            WHERE email NOT LIKE '%@rhorizon.in'
            GROUP BY webinar_id
        ) real_r ON real_r.webinar_id = w.id
        LEFT JOIN (
            SELECT a.webinar_id, COUNT(*) AS real_att
            FROM attendances a
            JOIN registrations r ON r.id = a.registration_id
            WHERE a.attended = TRUE AND r.email NOT LIKE '%@rhorizon.in'
            GROUP BY a.webinar_id
        ) real_a ON real_a.webinar_id = w.id
        ORDER BY w.date DESC
    """)
    rows = db.execute(sql).fetchall()
    result = []
    for row in rows:
        reg  = int(row.total_registrations or 0)
        att  = int(row.total_attendees or 0)
        rate = round(att / reg * 100, 1) if reg > 0 else 0.0
        result.append(schemas.WebinarSummary(
            id=row.id,
            title=row.title,
            date=row.date,
            time=row.time,
            speaker_name=row.speaker_name,
            speaker_id=int(row.speaker_id or 0),
            total_registrations=reg,
            total_attendees=att,
            attendance_rate=rate,
            status=row.status,
            icp=getattr(row, 'icp', None) or 'Others',
            has_registration_data=bool(row.has_reg),
            has_attendee_data=bool(row.has_att),
        ))
    return result


def get_webinar_detail(db: Session, webinar_id: int) -> Optional[schemas.WebinarDetail]:
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    return _to_detail(db, w) if w else None


# ── Speaker CRUD ──────────────────────────────────────────────────────────────

def get_all_speakers(db: Session) -> List[schemas.Speaker]:
    speakers = db.query(models.Speaker).order_by(models.Speaker.name).all()
    result = []
    for sp in speakers:
        count = db.query(func.count(models.Webinar.id)).filter(
            models.Webinar.speaker_id == sp.id
        ).scalar() or 0
        result.append(
            schemas.Speaker(id=sp.id, name=sp.name, email=sp.email, bio=sp.bio, total_webinars=count)
        )
    return result


def get_speaker_detail(db: Session, speaker_id: int) -> Optional[schemas.SpeakerDetail]:
    sp = db.query(models.Speaker).filter(models.Speaker.id == speaker_id).first()
    if not sp:
        return None

    webinars = (
        db.query(models.Webinar)
        .filter(models.Webinar.speaker_id == speaker_id)
        .order_by(models.Webinar.date.desc())
        .all()
    )

    webinar_list = []
    for w in webinars:
        s = _webinar_stats(db, w.id)
        webinar_list.append(
            schemas.WebinarInSpeaker(
                id=w.id,
                title=w.title,
                date=w.date,
                time=w.time,
                description=w.description,
                total_registrations=s["total_registrations"],
                total_attendees=s["total_attendees"],
                attendance_rate=s["attendance_rate"],
                no_shows=s["total_registrations"] - s["total_attendees"],
                duplicates_removed=s["duplicates_removed"],
                status=w.status,
                registration_by_source=_reg_by_source(db, w.id),
                duration_breakdown=_duration_breakdown(db, w.id),
            )
        )

    return schemas.SpeakerDetail(
        id=sp.id,
        name=sp.name,
        email=sp.email,
        bio=sp.bio,
        total_webinars=len(webinars),
        webinars=webinar_list,
    )


# ── File upload processing ────────────────────────────────────────────────────

def _normalise_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase + strip column names, try to map common variants."""
    df.columns = [str(c).strip().lower().replace(' ', '_').replace('-', '_') for c in df.columns]
    rename_map = {
        'full_name': 'name', 'participant_name': 'name', 'attendee_name': 'name',
        'first_name': 'first', 'last_name': 'last',
        'email_address': 'email', 'user_email': 'email', 'e_mail': 'email',
        'phone_number': 'phone', 'mobile': 'phone', 'mobile_number': 'phone',
        'contact_number': 'phone', 'whatsapp': 'phone',
        'duration_(minutes)': 'duration_minutes', 'duration_mins': 'duration_minutes',
        'time_in_session_(minutes)': 'duration_minutes', 'duration': 'duration_minutes',
        'join_time': 'joined_at', 'join_at': 'joined_at', 'time_joined': 'joined_at',
        'leave_time': 'left_at', 'leave_at': 'left_at', 'time_left': 'left_at',
        'registration_date': 'registered_at', 'date': 'registered_at',
        'registration_source': 'source', 'channel': 'source',
    }
    df = df.rename(columns=rename_map)
    if 'name' not in df.columns and 'first' in df.columns:
        last = df.get('last', '')
        df['name'] = (df['first'].fillna('') + ' ' + last.fillna('')).str.strip()
    return df


def _dedup_df(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove duplicates; returns (clean_df, n_removed). Uses email first, then phone/name."""
    original = len(df)
    if 'email' in df.columns:
        df['_email_norm'] = df['email'].fillna('').str.lower().str.strip()
        non_empty = df[df['_email_norm'] != '']
        if 'duration_minutes' in df.columns:
            non_empty = non_empty.sort_values('duration_minutes', ascending=False)
        non_empty = non_empty.drop_duplicates(subset='_email_norm', keep='first')
        empty_email = df[df['_email_norm'] == '']
        if 'phone' in empty_email.columns:
            empty_email = empty_email.copy()
            empty_email['_phone_norm'] = empty_email['phone'].fillna('').str.strip()
            ph_nonempty = empty_email[empty_email['_phone_norm'] != ''].drop_duplicates(subset='_phone_norm', keep='first')
            ph_empty = empty_email[empty_email['_phone_norm'] == '']
            if 'name' in ph_empty.columns:
                ph_empty = ph_empty.drop_duplicates(subset='name', keep='first')
            empty_email = pd.concat([ph_nonempty, ph_empty], ignore_index=True)
        df = pd.concat([non_empty, empty_email], ignore_index=True)
        df = df.drop(columns=[c for c in ['_email_norm', '_phone_norm'] if c in df.columns])
    elif 'phone' in df.columns:
        df['_phone_norm'] = df['phone'].fillna('').str.strip()
        non_empty = df[df['_phone_norm'] != ''].drop_duplicates(subset='_phone_norm', keep='first')
        empty_ph  = df[df['_phone_norm'] == '']
        if 'name' in empty_ph.columns:
            empty_ph = empty_ph.drop_duplicates(subset='name', keep='first')
        df = pd.concat([non_empty, empty_ph], ignore_index=True)
        df = df.drop(columns=['_phone_norm'])
    elif 'name' in df.columns:
        df = df.drop_duplicates(subset='name', keep='first')

    removed = original - len(df)
    return df.reset_index(drop=True), removed


def process_registration_upload(
    db: Session, webinar_id: int, content: bytes, filename: str
) -> schemas.UploadResult:
    try:
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise ValueError(f"Could not parse file: {e}")

    df = _normalise_cols(df)
    original_count = len(df)
    df, dups_removed = _dedup_df(df)

    # Raw SQL deletes — bypass ORM to avoid sequence cache issues
    db.execute(text("DELETE FROM attendances   WHERE webinar_id = :w"), {"w": webinar_id})
    db.execute(text("DELETE FROM registrations WHERE webinar_id = :w"), {"w": webinar_id})
    db.execute(text("DELETE FROM upload_logs   WHERE webinar_id = :w AND file_type = 'registrations'"), {"w": webinar_id})
    db.flush()

    now = datetime.utcnow()
    reg_rows = []
    for _, row in df.iterrows():
        name = str(row.get('name', 'Unknown')).strip() or 'Unknown'
        email = str(row.get('email', '')).strip().lower() or None
        phone = str(row.get('phone', '')).strip() or None
        source = str(row.get('source', 'upload')).strip() or 'upload'
        reg_at_raw = row.get('registered_at', None)
        try:
            reg_at = pd.to_datetime(reg_at_raw) if reg_at_raw and str(reg_at_raw).strip() else now
            if hasattr(reg_at, 'to_pydatetime'):
                reg_at = reg_at.to_pydatetime()
        except Exception:
            reg_at = now
        reg_rows.append({
            "w": webinar_id, "n": name, "e": email,
            "p": phone, "s": source, "r": reg_at,
        })

    if reg_rows:
        db.execute(
            text("INSERT INTO registrations (webinar_id, attendee_name, email, phone, source, registered_at)"
                 " VALUES (:w, :n, :e, :p, :s, :r)"),
            reg_rows,
        )

    db.execute(
        text("INSERT INTO upload_logs (webinar_id, file_type, filename, original_count,"
             " final_count, duplicates_removed, unmatched_attendees, uploaded_at)"
             " VALUES (:w, 'registrations', :fn, :oc, :fc, :dr, 0, :ua)"),
        {"w": webinar_id, "fn": filename, "oc": original_count,
         "fc": len(df), "dr": dups_removed, "ua": now},
    )
    db.commit()

    return schemas.UploadResult(
        original_count=original_count,
        final_count=len(df),
        duplicates_removed=dups_removed,
        unmatched_attendees=0,
        message=f"Imported {len(df)} registrations ({dups_removed} duplicates removed).",
    )


def process_attendee_upload(
    db: Session, webinar_id: int, content: bytes, filename: str
) -> schemas.UploadResult:
    try:
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise ValueError(f"Could not parse file: {e}")

    df = _normalise_cols(df)
    original_count = len(df)
    df, dups_removed = _dedup_df(df)

    # Raw SQL deletes — bypass ORM to avoid sequence cache issues
    db.execute(text("DELETE FROM attendances WHERE webinar_id = :w"), {"w": webinar_id})
    db.execute(text("DELETE FROM upload_logs  WHERE webinar_id = :w AND file_type = 'attendees'"), {"w": webinar_id})
    db.flush()

    # Load registrations for email matching
    reg_rows_q = db.execute(
        text("SELECT id, email FROM registrations WHERE webinar_id = :w"), {"w": webinar_id}
    ).fetchall()
    reg_by_email: dict = {}
    for r in reg_rows_q:
        if r.email:
            reg_by_email[r.email.lower().strip()] = r.id

    now = datetime.utcnow()
    unmatched = 0
    matched_att: List[dict] = []   # attendance rows for matched registrants
    ghost_rows:  List[dict] = []   # rows that need a ghost registration

    for _, row in df.iterrows():
        name  = str(row.get('name', 'Unknown')).strip() or 'Unknown'
        email = str(row.get('email', '')).strip().lower() or None
        duration = row.get('duration_minutes', None)
        try:
            duration = int(float(duration)) if duration is not None and str(duration).strip() else None
        except (ValueError, TypeError):
            duration = None

        joined_raw = row.get('joined_at', None)
        left_raw   = row.get('left_at', None)
        joined_at  = None
        left_at    = None
        try:
            if joined_raw and str(joined_raw).strip():
                j = pd.to_datetime(joined_raw)
                joined_at = j.to_pydatetime() if hasattr(j, 'to_pydatetime') else j
        except Exception:
            pass
        try:
            if left_raw and str(left_raw).strip():
                l = pd.to_datetime(left_raw)
                left_at = l.to_pydatetime() if hasattr(l, 'to_pydatetime') else l
        except Exception:
            pass

        if duration is None and joined_at and left_at:
            duration = max(0, int((left_at - joined_at).total_seconds() / 60))

        reg_id = reg_by_email.get(email) if email else None

        att_payload = {
            "w": webinar_id, "rid": None,
            "ja": joined_at, "la": left_at, "dur": duration,
        }

        if reg_id is not None:
            att_payload["rid"] = reg_id
            matched_att.append(att_payload)
        else:
            ghost_rows.append({
                "name": name, "email": email, "att": att_payload
            })
            unmatched += 1

    # Insert ghost registrations one at a time with RETURNING id (raw SQL)
    for g in ghost_rows:
        res = db.execute(
            text("INSERT INTO registrations (webinar_id, attendee_name, email, source, registered_at)"
                 " VALUES (:w, :n, :e, 'attendee_upload', :r) RETURNING id"),
            {"w": webinar_id, "n": g["name"], "e": g["email"], "r": now},
        )
        ghost_id = res.fetchone()[0]
        g["att"]["rid"] = ghost_id
        matched_att.append(g["att"])

    # Bulk insert all attendances (no id column → PostgreSQL uses sequence naturally)
    if matched_att:
        db.execute(
            text("INSERT INTO attendances (webinar_id, registration_id, joined_at, left_at, duration_minutes, attended)"
                 " VALUES (:w, :rid, :ja, :la, :dur, TRUE)"),
            matched_att,
        )

    # Update webinar status and log — still use ORM for single-row ops (fine)
    db.execute(
        text("UPDATE webinars SET status = 'completed' WHERE id = :w AND status = 'upcoming'"),
        {"w": webinar_id},
    )
    db.execute(
        text("INSERT INTO upload_logs (webinar_id, file_type, filename, original_count,"
             " final_count, duplicates_removed, unmatched_attendees, uploaded_at)"
             " VALUES (:w, 'attendees', :fn, :oc, :fc, :dr, :um, :ua)"),
        {"w": webinar_id, "fn": filename, "oc": original_count,
         "fc": len(df), "dr": dups_removed, "um": unmatched, "ua": now},
    )
    db.commit()

    return schemas.UploadResult(
        original_count=original_count,
        final_count=len(df),
        duplicates_removed=dups_removed,
        unmatched_attendees=unmatched,
        message=f"Imported {len(df)} attendees ({dups_removed} duplicates removed, {unmatched} not in registration list).",
    )


# ── Leaderboard ───────────────────────────────────────────────────────────────

def get_leaderboard(
    db: Session,
    speaker_id: Optional[int] = None,
    webinar_id: Optional[int] = None,
    limit: int = 50,
) -> List[schemas.LeaderboardEntry]:
    extra_where = ""
    params: dict = {"lim": limit}

    if webinar_id:
        extra_where = "AND r.webinar_id = :webinar_id"
        params["webinar_id"] = webinar_id
    elif speaker_id:
        extra_where = "AND r.webinar_id IN (SELECT id FROM webinars WHERE speaker_id = :speaker_id)"
        params["speaker_id"] = speaker_id

    # CTE normalises the email_key once so GROUP BY can reference it by name —
    # required by PostgreSQL strict GROUP BY rules (SQLite allowed the alias).
    sql = text(f"""
        WITH norm AS (
            SELECT
                r.email,
                r.attendee_name,
                r.phone,
                r.webinar_id,
                a.duration_minutes,
                CASE
                    WHEN TRIM(COALESCE(r.email, '')) = ''
                    THEN 'noemail_' || CAST(r.id AS VARCHAR)
                    ELSE LOWER(TRIM(r.email))
                END AS email_key
            FROM registrations r
            JOIN attendances a ON a.registration_id = r.id
            WHERE a.attended = TRUE {extra_where}
        )
        SELECT
            email_key,
            MIN(email)            AS email,
            MIN(attendee_name)    AS name,
            MIN(phone)            AS phone,
            COUNT(DISTINCT webinar_id)          AS webinars_attended,
            COALESCE(SUM(duration_minutes), 0)  AS total_duration
        FROM norm
        GROUP BY email_key
        ORDER BY webinars_attended DESC, total_duration DESC
        LIMIT :lim
    """)

    rows = db.execute(sql, params).fetchall()

    result = []
    for i, row in enumerate(rows):
        webinars_att = row.webinars_attended or 0
        total_dur    = row.total_duration or 0
        avg_dur      = total_dur / webinars_att if webinars_att else 0
        bonus        = 5 if avg_dur >= 60 else 3 if avg_dur >= 45 else 1 if avg_dur >= 30 else 0
        score        = webinars_att * (10 + bonus)
        result.append(schemas.LeaderboardEntry(
            rank=i + 1,
            name=row.name or "Unknown",
            email=row.email or None,
            phone=row.phone or None,
            webinars_attended=webinars_att,
            total_duration_minutes=total_dur,
            score=score,
        ))

    return result


# ── Attendee profile ─────────────────────────────────────────────────────────

def get_attendee_profile(db: Session, email: str) -> Optional[schemas.AttendeeProfile]:
    """Return all webinars attended by a person identified by email."""
    email_norm = email.lower().strip()
    sql = text("""
        SELECT
            MIN(r.attendee_name)  AS name,
            r.email,
            MIN(r.phone)          AS phone,
            w.id                  AS webinar_id,
            w.title,
            w.date,
            w.time,
            COALESCE(s.name, 'Unknown') AS speaker_name,
            a.duration_minutes
        FROM registrations r
        JOIN attendances a ON a.registration_id = r.id
        JOIN webinars w    ON w.id = r.webinar_id
        LEFT JOIN speakers s ON s.id = w.speaker_id
        WHERE LOWER(TRIM(COALESCE(r.email, ''))) = :email
          AND a.attended = TRUE
        GROUP BY r.email, w.id, w.title, w.date, w.time, s.name, a.duration_minutes
        ORDER BY w.date DESC
    """)
    rows = db.execute(sql, {"email": email_norm}).fetchall()
    if not rows:
        return None

    webinar_list = [
        schemas.AttendeeWebinarItem(
            webinar_id=row.webinar_id,
            title=row.title,
            date=row.date,
            time=row.time,
            speaker_name=row.speaker_name,
            duration_minutes=row.duration_minutes,
        )
        for row in rows
    ]

    total_dur = sum(w.duration_minutes or 0 for w in webinar_list)
    n = len(webinar_list)
    avg_dur = total_dur / n if n else 0
    bonus = 5 if avg_dur >= 60 else 3 if avg_dur >= 45 else 1 if avg_dur >= 30 else 0
    score = n * (10 + bonus)

    return schemas.AttendeeProfile(
        name=rows[0].name or "Unknown",
        email=rows[0].email,
        phone=rows[0].phone,
        webinars_attended=n,
        total_duration_minutes=total_dur,
        score=score,
        webinars=webinar_list,
    )


# ── Ad Creative CRUD ─────────────────────────────────────────────────────────

def create_webinar_ad(
    db: Session, webinar_id: int, ad_in: schemas.WebinarAdCreate
) -> models.WebinarAd:
    ad = models.WebinarAd(webinar_id=webinar_id, **ad_in.model_dump())
    db.add(ad)
    db.commit()
    db.refresh(ad)
    return ad


def get_webinar_ads(db: Session, webinar_id: int) -> List[schemas.WebinarAdOut]:
    return _get_ads(db, webinar_id)


def delete_webinar_ad(db: Session, ad_id: int, webinar_id: int) -> bool:
    ad = db.query(models.WebinarAd).filter(
        models.WebinarAd.id == ad_id,
        models.WebinarAd.webinar_id == webinar_id,
    ).first()
    if not ad:
        return False
    db.delete(ad)
    db.commit()
    return True


# ── Platform stats ────────────────────────────────────────────────────────────

def get_platform_stats(db: Session) -> schemas.PlatformStats:
    """Single query for all platform-level counts."""
    sql = text("""
        SELECT
            (SELECT COUNT(*) FROM webinars)                            AS total_webinars,
            (SELECT COUNT(*) FROM speakers)                            AS total_speakers,
            (SELECT COUNT(*) FROM registrations)                       AS total_reg,
            (SELECT COUNT(*) FROM attendances WHERE attended = TRUE)   AS total_att,
            (SELECT COUNT(*) FROM webinars WHERE status = 'upcoming')  AS upcoming
    """)
    row = db.execute(sql).fetchone()
    total_reg = int(row.total_reg or 0)
    total_att = int(row.total_att or 0)
    rate = round(total_att / total_reg * 100, 1) if total_reg else 0.0
    return schemas.PlatformStats(
        total_webinars=int(row.total_webinars or 0),
        total_speakers=int(row.total_speakers or 0),
        total_registrations=total_reg,
        total_attendees=total_att,
        upcoming_webinars=int(row.upcoming or 0),
        overall_attendance_rate=rate,
    )
