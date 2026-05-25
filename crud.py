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
    total_reg = db.query(func.count(models.Registration.id)).filter(
        models.Registration.webinar_id == webinar_id
    ).scalar() or 0

    total_att = db.query(func.count(models.Attendance.id)).filter(
        and_(
            models.Attendance.webinar_id == webinar_id,
            models.Attendance.attended == True,
        )
    ).scalar() or 0

    rate = round(total_att / total_reg * 100, 1) if total_reg > 0 else 0.0

    # Sum duplicates removed from upload logs
    dup_log = db.query(func.sum(models.UploadLog.duplicates_removed)).filter(
        models.UploadLog.webinar_id == webinar_id
    ).scalar() or 0

    unmatched_log = db.query(func.sum(models.UploadLog.unmatched_attendees)).filter(
        models.UploadLog.webinar_id == webinar_id,
        models.UploadLog.file_type == "attendees",
    ).scalar() or 0

    return {
        "total_registrations": total_reg,
        "total_attendees": total_att,
        "attendance_rate": rate,
        "duplicates_removed": dup_log,
        "unmatched_attendees": unmatched_log,
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
    attendances = db.query(models.Attendance).filter(
        and_(
            models.Attendance.webinar_id == webinar_id,
            models.Attendance.attended == True,
        )
    ).all()

    buckets = {"0–15 min": 0, "15–30 min": 0, "30–45 min": 0, "45–60 min": 0, "60+ min": 0}
    for a in attendances:
        d = a.duration_minutes or 0
        if d < 15:
            buckets["0–15 min"] += 1
        elif d < 30:
            buckets["15–30 min"] += 1
        elif d < 45:
            buckets["30–45 min"] += 1
        elif d < 60:
            buckets["45–60 min"] += 1
        else:
            buckets["60+ min"] += 1

    total = len(attendances)
    return [
        schemas.DurationBreakdown(
            range=k,
            count=v,
            percentage=round(v / total * 100, 1) if total else 0.0,
        )
        for k, v in buckets.items()
    ]


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
    )


# ── Webinar CRUD ──────────────────────────────────────────────────────────────

def create_webinar(db: Session, webinar_in: schemas.WebinarCreate) -> models.Webinar:
    # Find or create speaker
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
    webinars = db.query(models.Webinar).order_by(models.Webinar.date.desc()).all()
    return [_to_summary(db, w) for w in webinars]


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
        # name variants
        'full_name': 'name', 'participant_name': 'name', 'attendee_name': 'name',
        'first_name': 'first', 'last_name': 'last',
        # email variants
        'email_address': 'email', 'user_email': 'email', 'e_mail': 'email',
        # phone variants
        'phone_number': 'phone', 'mobile': 'phone', 'mobile_number': 'phone',
        'contact_number': 'phone', 'whatsapp': 'phone',
        # duration variants
        'duration_(minutes)': 'duration_minutes', 'duration_mins': 'duration_minutes',
        'time_in_session_(minutes)': 'duration_minutes', 'duration': 'duration_minutes',
        # join/leave variants
        'join_time': 'joined_at', 'join_at': 'joined_at', 'time_joined': 'joined_at',
        'leave_time': 'left_at', 'leave_at': 'left_at', 'time_left': 'left_at',
        # date variants
        'registration_date': 'registered_at', 'date': 'registered_at',
        # source variants
        'registration_source': 'source', 'channel': 'source',
    }
    df = df.rename(columns=rename_map)
    # Build 'name' from first+last if not present
    if 'name' not in df.columns and 'first' in df.columns:
        last = df.get('last', '')
        df['name'] = (df['first'].fillna('') + ' ' + last.fillna('')).str.strip()
    return df


def _dedup_df(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove duplicates; returns (clean_df, n_removed). Uses email first, then phone/name."""
    original = len(df)
    if 'email' in df.columns:
        # Normalise email: lowercase + strip; keep row with longest duration if available
        df['_email_norm'] = df['email'].fillna('').str.lower().str.strip()
        non_empty = df[df['_email_norm'] != '']
        if 'duration_minutes' in df.columns:
            non_empty = non_empty.sort_values('duration_minutes', ascending=False)
        non_empty = non_empty.drop_duplicates(subset='_email_norm', keep='first')
        empty_email = df[df['_email_norm'] == '']
        # For rows without email, dedup by phone then name
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
    # Parse file
    try:
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise ValueError(f"Could not parse file: {e}")

    df = _normalise_cols(df)
    original_count = len(df)

    # Deduplicate
    df, dups_removed = _dedup_df(df)

    # Clear existing seeded/uploaded registrations for this webinar
    db.query(models.Attendance).filter(models.Attendance.webinar_id == webinar_id).delete()
    db.query(models.Registration).filter(models.Registration.webinar_id == webinar_id).delete()
    db.flush()

    # Insert registrations
    now = datetime.utcnow()
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

        db.add(models.Registration(
            webinar_id=webinar_id,
            attendee_name=name,
            email=email,
            phone=phone,
            source=source,
            registered_at=reg_at,
        ))

    # Log upload
    db.query(models.UploadLog).filter(
        models.UploadLog.webinar_id == webinar_id,
        models.UploadLog.file_type == "registrations",
    ).delete()
    db.add(models.UploadLog(
        webinar_id=webinar_id,
        file_type="registrations",
        filename=filename,
        original_count=original_count,
        final_count=len(df),
        duplicates_removed=dups_removed,
        unmatched_attendees=0,
        uploaded_at=now,
    ))
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
    # Parse file
    try:
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise ValueError(f"Could not parse file: {e}")

    df = _normalise_cols(df)
    original_count = len(df)

    # Deduplicate attendees
    df, dups_removed = _dedup_df(df)

    # Clear existing attendances
    db.query(models.Attendance).filter(models.Attendance.webinar_id == webinar_id).delete()
    db.flush()

    # Build email → registration_id lookup
    reg_by_email = {}
    for r in db.query(models.Registration).filter(models.Registration.webinar_id == webinar_id).all():
        if r.email:
            reg_by_email[r.email.lower().strip()] = r.id

    now = datetime.utcnow()
    unmatched = 0

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

        # If duration not in file but join/leave exist, compute
        if duration is None and joined_at and left_at:
            duration = max(0, int((left_at - joined_at).total_seconds() / 60))

        # Match to registration
        reg_id = reg_by_email.get(email) if email else None

        # If no match, create a ghost registration so data isn't lost
        if reg_id is None:
            ghost = models.Registration(
                webinar_id=webinar_id,
                attendee_name=name,
                email=email,
                source="attendee_upload",
                registered_at=now,
            )
            db.add(ghost)
            db.flush()
            reg_id = ghost.id
            unmatched += 1

        db.add(models.Attendance(
            webinar_id=webinar_id,
            registration_id=reg_id,
            joined_at=joined_at,
            left_at=left_at,
            duration_minutes=duration,
            attended=True,
        ))

    # Update webinar status to completed if it was upcoming
    w = db.query(models.Webinar).filter(models.Webinar.id == webinar_id).first()
    if w and w.status == "upcoming":
        w.status = "completed"

    # Log upload
    db.query(models.UploadLog).filter(
        models.UploadLog.webinar_id == webinar_id,
        models.UploadLog.file_type == "attendees",
    ).delete()
    db.add(models.UploadLog(
        webinar_id=webinar_id,
        file_type="attendees",
        filename=filename,
        original_count=original_count,
        final_count=len(df),
        duplicates_removed=dups_removed,
        unmatched_attendees=unmatched,
        uploaded_at=now,
    ))
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
    """
    Group attendees by normalised email (case-insensitive). Same person attending
    multiple webinars is counted once per webinar.

    Score per webinar attended:
      base  = 10 pts
      +5    if avg session >= 60 min
      +3    if avg session >= 45 min
      +1    if avg session >= 30 min
    """
    # Use raw SQL via text() so we can use LOWER() and proper deduplication
    # Build the WHERE clause dynamically
    where_parts = ["a.attended = 1"]
    params: dict = {"lim": limit}

    if webinar_id:
        where_parts.append("r.webinar_id = :webinar_id")
        params["webinar_id"] = webinar_id
    elif speaker_id:
        where_parts.append("""
            r.webinar_id IN (
                SELECT id FROM webinars WHERE speaker_id = :speaker_id
            )
        """)
        params["speaker_id"] = speaker_id

    where_clause = " AND ".join(where_parts)

    sql = text(f"""
        SELECT
            LOWER(TRIM(COALESCE(r.email, '')))   AS email_key,
            MIN(r.email)                          AS email,
            MIN(r.attendee_name)                  AS name,
            MIN(r.phone)                          AS phone,
            COUNT(DISTINCT r.webinar_id)          AS webinars_attended,
            COALESCE(SUM(a.duration_minutes), 0)  AS total_duration
        FROM registrations r
        JOIN attendances a ON a.registration_id = r.id
        WHERE {where_clause}
        GROUP BY
            CASE
                WHEN TRIM(COALESCE(r.email, '')) = '' THEN 'noemail_' || r.id
                ELSE LOWER(TRIM(r.email))
            END
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


# ── Platform stats ────────────────────────────────────────────────────────────

def get_platform_stats(db: Session) -> schemas.PlatformStats:
    total_webinars = db.query(func.count(models.Webinar.id)).scalar() or 0
    total_speakers = db.query(func.count(models.Speaker.id)).scalar() or 0
    total_reg = db.query(func.count(models.Registration.id)).scalar() or 0
    total_att = (
        db.query(func.count(models.Attendance.id))
        .filter(models.Attendance.attended == True)
        .scalar() or 0
    )
    upcoming = (
        db.query(func.count(models.Webinar.id))
        .filter(models.Webinar.status == "upcoming")
        .scalar() or 0
    )
    rate = round(total_att / total_reg * 100, 1) if total_reg else 0.0
    return schemas.PlatformStats(
        total_webinars=total_webinars,
        total_speakers=total_speakers,
        total_registrations=total_reg,
        total_attendees=total_att,
        upcoming_webinars=upcoming,
        overall_attendance_rate=rate,
    )
