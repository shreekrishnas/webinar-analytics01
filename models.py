from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    email = Column(String)
    bio = Column(Text)

    webinars = relationship("Webinar", foreign_keys="[Webinar.speaker_id]", back_populates="speaker")


class Webinar(Base):
    __tablename__ = "webinars"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    time = Column(String)
    speaker_id = Column(Integer, ForeignKey("speakers.id"))
    description = Column(Text)
    status        = Column(String, default="completed")
    icp           = Column(String, default="Others")
    co_speaker_id = Column(Integer, ForeignKey("speakers.id"), nullable=True)

    speaker    = relationship("Speaker", foreign_keys="[Webinar.speaker_id]", back_populates="webinars")
    co_speaker = relationship("Speaker", foreign_keys="[Webinar.co_speaker_id]")
    registrations = relationship("Registration", back_populates="webinar", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="webinar", cascade="all, delete-orphan")
    upload_logs = relationship("UploadLog", back_populates="webinar", cascade="all, delete-orphan")
    ads = relationship("WebinarAd", back_populates="webinar", cascade="all, delete-orphan")


class Registration(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    webinar_id = Column(Integer, ForeignKey("webinars.id"))
    attendee_name = Column(String, nullable=False)
    email = Column(String, index=True)
    phone = Column(String, nullable=True)
    source = Column(String)  # email, social, direct, referral, upload
    registered_at = Column(DateTime, default=datetime.utcnow)

    webinar = relationship("Webinar", back_populates="registrations")
    attendance = relationship("Attendance", back_populates="registration", uselist=False)


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    webinar_id = Column(Integer, ForeignKey("webinars.id"))
    registration_id = Column(Integer, ForeignKey("registrations.id"), nullable=True)
    joined_at = Column(DateTime)
    left_at = Column(DateTime)
    duration_minutes = Column(Integer)
    attended = Column(Boolean, default=True)

    webinar = relationship("Webinar", back_populates="attendances")
    registration = relationship("Registration", back_populates="attendance")


class UploadLog(Base):
    __tablename__ = "upload_logs"

    id = Column(Integer, primary_key=True, index=True)
    webinar_id = Column(Integer, ForeignKey("webinars.id"))
    file_type = Column(String, nullable=False)   # "registrations" or "attendees"
    filename = Column(String)
    original_count = Column(Integer, default=0)
    final_count = Column(Integer, default=0)
    duplicates_removed = Column(Integer, default=0)
    unmatched_attendees = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    webinar = relationship("Webinar", back_populates="upload_logs")


class WebinarNote(Base):
    """Human knowledge/comments for a webinar — used by AI in analysis."""
    __tablename__ = "webinar_notes"

    id = Column(Integer, primary_key=True, index=True)
    webinar_id = Column(Integer, ForeignKey("webinars.id", ondelete="CASCADE"), index=True)
    author = Column(String, default="Team")
    category = Column(String, default="observation")  # observation | speaker_feedback | tech_issue | content_quality | promotion
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PipelineContact(Base):
    """Sales pipeline: tracks hot leads from webinars through to meeting/conversion."""
    __tablename__ = "pipeline_contacts"

    email = Column(String, primary_key=True, index=True)
    status = Column(String, default="new")   # new | contacted | meeting_booked | converted | not_interested
    assigned_to = Column(String)
    notes = Column(Text)
    follow_up_date = Column(Date, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebinarAd(Base):
    __tablename__ = "webinar_ads"

    id = Column(Integer, primary_key=True, index=True)
    webinar_id = Column(Integer, ForeignKey("webinars.id", ondelete="CASCADE"))
    title = Column(String, nullable=False)
    platform = Column(String)          # Facebook, Instagram, Google, LinkedIn, etc.
    ad_type = Column(String)           # Image, Video, Carousel, Story, Reel, Banner
    creative_image = Column(Text)      # base64 data URI (data:image/…;base64,…)
    creative_url = Column(String)      # alternative: URL to hosted image
    headline = Column(String)
    description = Column(Text)
    cta_text = Column(String)          # e.g. "Register Now"
    landing_url = Column(String)
    budget = Column(String)            # stored as free-form string (e.g. "₹5,000")
    spend = Column(String)
    impressions = Column(Integer)
    clicks = Column(Integer)
    conversions = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String, default="active")   # active | paused | completed
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    webinar = relationship("Webinar", back_populates="ads")
