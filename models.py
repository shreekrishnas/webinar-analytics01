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

    webinars = relationship("Webinar", back_populates="speaker")


class Webinar(Base):
    __tablename__ = "webinars"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    time = Column(String)
    speaker_id = Column(Integer, ForeignKey("speakers.id"))
    description = Column(Text)
    status = Column(String, default="completed")

    speaker = relationship("Speaker", back_populates="webinars")
    registrations = relationship("Registration", back_populates="webinar", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="webinar", cascade="all, delete-orphan")
    upload_logs = relationship("UploadLog", back_populates="webinar", cascade="all, delete-orphan")


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
