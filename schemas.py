from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime as _dt


# ── Breakdowns ────────────────────────────────────────────────────────────────

class RegistrationBreakdown(BaseModel):
    source: str
    count: int
    percentage: float


class DurationBreakdown(BaseModel):
    range: str
    count: int
    percentage: float


# ── Upload log ────────────────────────────────────────────────────────────────

class UploadLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_type: str
    filename: Optional[str] = None
    original_count: int
    final_count: int
    duplicates_removed: int
    unmatched_attendees: int
    uploaded_at: _dt


class UploadResult(BaseModel):
    original_count: int
    final_count: int
    duplicates_removed: int
    unmatched_attendees: int
    message: str


# ── Ad Creative ──────────────────────────────────────────────────────────────

class WebinarAdCreate(BaseModel):
    title: str
    platform: Optional[str] = None
    ad_type: Optional[str] = None
    creative_image: Optional[str] = None   # base64 data URI
    creative_url: Optional[str] = None
    headline: Optional[str] = None
    description: Optional[str] = None
    cta_text: Optional[str] = None
    landing_url: Optional[str] = None
    budget: Optional[str] = None
    spend: Optional[str] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "active"
    notes: Optional[str] = None


class WebinarAdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    webinar_id: int
    title: str
    platform: Optional[str] = None
    ad_type: Optional[str] = None
    creative_image: Optional[str] = None
    creative_url: Optional[str] = None
    headline: Optional[str] = None
    description: Optional[str] = None
    cta_text: Optional[str] = None
    landing_url: Optional[str] = None
    budget: Optional[str] = None
    spend: Optional[str] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    notes: Optional[str] = None
    created_at: _dt


# ── Webinar ───────────────────────────────────────────────────────────────────

class WebinarCreate(BaseModel):
    title: str
    date: date
    time: Optional[str] = None
    description: Optional[str] = None
    speaker_name: str
    speaker_email: Optional[str] = None
    status: str = "upcoming"
    icp: Optional[str] = "Others"
    platform: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    recording_url: Optional[str] = None
    tags: Optional[str] = None
    expected_registrations: Optional[int] = None
    notes: Optional[str] = None
    series: Optional[str] = None
    is_favourite: Optional[bool] = False


class WebinarSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: date
    time: Optional[str] = None
    speaker_name: str
    speaker_id: int
    co_speaker_name: Optional[str] = ""
    total_registrations: int
    total_attendees: int
    attendance_rate: float
    status: str
    icp: Optional[str] = "Others"
    has_registration_data: bool
    has_attendee_data: bool
    platform: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    recording_url: Optional[str] = None
    tags: Optional[str] = None
    expected_registrations: Optional[int] = None
    notes: Optional[str] = None
    series: Optional[str] = None
    is_favourite: Optional[bool] = False


class WebinarDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: date
    time: Optional[str] = None
    description: Optional[str] = None
    speaker_name: str
    speaker_id: int
    total_registrations: int
    total_attendees: int
    attendance_rate: float
    no_shows: int
    duplicates_removed: int
    unmatched_attendees: int
    status: str
    icp: Optional[str] = "Others"
    has_registration_data: bool
    has_attendee_data: bool
    registration_by_source: List[RegistrationBreakdown]
    duration_breakdown: List[DurationBreakdown]
    upload_logs: List[UploadLogOut]
    ads: List[WebinarAdOut] = []


# ── Speaker ───────────────────────────────────────────────────────────────────

class Speaker(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: Optional[str] = None
    bio: Optional[str] = None
    total_webinars: int


class WebinarInSpeaker(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: date
    time: Optional[str] = None
    description: Optional[str] = None
    total_registrations: int
    total_attendees: int
    attendance_rate: float
    no_shows: int
    duplicates_removed: int
    status: str
    registration_by_source: List[RegistrationBreakdown]
    duration_breakdown: List[DurationBreakdown]


class SpeakerDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: Optional[str] = None
    bio: Optional[str] = None
    total_webinars: int
    webinars: List[WebinarInSpeaker]


# ── Platform stats ────────────────────────────────────────────────────────────

class PlatformStats(BaseModel):
    total_webinars: int
    total_speakers: int
    total_registrations: int
    total_attendees: int
    upcoming_webinars: int
    overall_attendance_rate: float


# ── Leaderboard ───────────────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    webinars_attended: int
    total_duration_minutes: int
    score: int
    # Phase 1: Meeting Readiness + Lead Qualification
    avg_minutes: float = 0
    last_attended_date: Optional[str] = None
    days_since_last: Optional[int] = None
    icp_diversity: int = 0          # how many distinct ICPs this person attended
    readiness: str = "cold"          # hot | warm | cold | customer | internal
    tag: Optional[str] = None        # manual override: customer | prospect | partner | employee | meeting_ready


# ── Attendee profile ──────────────────────────────────────────────────────────

class AttendeeWebinarItem(BaseModel):
    webinar_id: int
    title: str
    date: date
    time: Optional[str] = None
    speaker_name: str
    icp: Optional[str] = "Others"
    duration_minutes: Optional[int] = None


class AttendeeProfile(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    webinars_attended: int
    total_duration_minutes: int
    score: int
    webinars: List[AttendeeWebinarItem]
