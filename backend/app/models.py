import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .timeutil import utcnow


def new_id() -> str:
    return str(uuid.uuid4())


def default_channels() -> dict:
    return {"in_app": True, "telegram": False, "email": False}


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16), default="student")
    city: Mapped[str] = mapped_column(String(80), default="Coimbatore")
    home_area: Mapped[str | None] = mapped_column(String(120))
    home_lat: Mapped[float | None] = mapped_column(Float)
    home_lng: Mapped[float | None] = mapped_column(Float)
    max_distance_km: Mapped[int] = mapped_column(Integer, default=20)
    budget_max_inr: Mapped[int | None] = mapped_column(Integer, default=200)  # None = any budget
    format_pref: Mapped[str] = mapped_column(String(16), default="either")
    skill_level: Mapped[str] = mapped_column(String(16), default="beginner")
    eligibility_tags: Mapped[list] = mapped_column(JSON, default=list)
    interest_text: Mapped[str] = mapped_column(Text, default="")
    strict_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    show_almost: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64))
    notif_channels: Mapped[dict] = mapped_column(JSON, default=default_channels)
    notif_max_per_week: Mapped[int] = mapped_column(Integer, default=3)
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default="22:00")
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default="07:00")
    notif_paused_until: Mapped[datetime | None] = mapped_column(DateTime)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    interests: Mapped[list["UserInterest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    organizer: Mapped["Organizer | None"] = relationship(back_populates="user", uselist=False)


class UserInterest(Base):
    __tablename__ = "user_interests"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(40), primary_key=True)
    weight: Mapped[int] = mapped_column(Integer, default=2)

    user: Mapped[User] = relationship(back_populates="interests")


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    __table_args__ = (Index("ix_slots_user", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day_of_week: Mapped[int] = mapped_column(Integer)  # Monday = 0
    start_min: Mapped[int] = mapped_column(Integer)
    end_min: Mapped[int] = mapped_column(Integer)  # exclusive; 1440 = midnight
    recurring: Mapped[bool] = mapped_column(Boolean, default=True)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)  # set for one-off slots
    kind: Mapped[str] = mapped_column(String(16), default="free")  # free | busy_override
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | timetable
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Organizer(Base):
    __tablename__ = "organizers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    org_name: Mapped[str] = mapped_column(String(160))
    org_email_domain: Mapped[str] = mapped_column(String(120), default="")
    trust_level: Mapped[str] = mapped_column(String(16), default="new")  # new | verified | trusted
    verified_by: Mapped[str | None] = mapped_column(String(36))
    past_events_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_attendance_rate: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="organizer")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_status_start", "status", "start_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organizer_id: Mapped[str | None] = mapped_column(ForeignKey("organizers.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    mode: Mapped[str] = mapped_column(String(16), default="in_person")
    venue_name: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    fee_inr: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int | None] = mapped_column(Integer)
    eligibility: Mapped[dict] = mapped_column(JSON, default=dict)  # {"required_tags": [], "text": ""}
    skill_level: Mapped[str | None] = mapped_column(String(16))
    registration_url: Mapped[str | None] = mapped_column(String(500))
    poster_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    verification_label: Mapped[str] = mapped_column(String(24), default="unverified")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_reasons: Mapped[list] = mapped_column(JSON, default=list)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    source: Mapped[str] = mapped_column(String(16), default="form")
    field_confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    duplicate_of: Mapped[str | None] = mapped_column(String(36))
    appeal_note: Mapped[str | None] = mapped_column(String(500))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)  # last admin decision; older reports are settled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    organizer: Mapped[Organizer | None] = relationship(lazy="joined")


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        Index("ix_reg_event_status", "event_id", "status"),
        Index("ix_reg_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="registered")
    waitlist_position: Mapped[int | None] = mapped_column(Integer)
    promotion_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    checkin_token: Mapped[str] = mapped_column(String(36), default=new_id, unique=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime)
    showup_likelihood: Mapped[float | None] = mapped_column(Float)
    reminder_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notif_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(24))
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    channel_sent: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("event_id", "reporter_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SavedEvent(Base):
    __tablename__ = "saved_events"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExtractionCache(Base):
    """AI results keyed by file hash (SPEC 6.4), plus geocoder results keyed by address."""

    __tablename__ = "extraction_cache"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)  # "<kind>:<sha256>"
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TelegramLink(Base):
    __tablename__ = "telegram_links"

    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
