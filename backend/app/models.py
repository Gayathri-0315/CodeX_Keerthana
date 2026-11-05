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
from sqlalchemy import false, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .timeutil import utcnow


def new_id() -> str:
    return str(uuid.uuid4())


def default_channels() -> dict:
    return {"in_app": True, "email": False}


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
    max_distance_km: Mapped[int | None] = mapped_column(Integer, default=20)  # None = anywhere
    budget_max_inr: Mapped[int | None] = mapped_column(Integer, default=200)  # None = any budget
    format_pref: Mapped[str] = mapped_column(String(16), default="either")
    skill_level: Mapped[str] = mapped_column(String(16), default="beginner")
    eligibility_tags: Mapped[list] = mapped_column(JSON, default=list)
    interest_text: Mapped[str] = mapped_column(Text, default="")
    strict_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    show_almost: Mapped[bool] = mapped_column(Boolean, default=True)
    notif_channels: Mapped[dict] = mapped_column(JSON, default=default_channels)
    notif_max_per_week: Mapped[int] = mapped_column(Integer, default=3)
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default="22:00")
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default="07:00")
    notif_paused_until: Mapped[datetime | None] = mapped_column(DateTime)
    follow_updates: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())  # "Updates from clubs I follow"
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    college: Mapped[str | None] = mapped_column(String(160))
    # Lockout after repeated failures, and a version that invalidates every session when the password changes.
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    session_version: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime)
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
    slug: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)  # /club/<slug>; stays the same after renames
    org_email_domain: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str | None] = mapped_column(String(32))
    college_or_company: Mapped[str | None] = mapped_column(String(160))
    # Organizer profile (settings group 1)
    org_type: Mapped[str | None] = mapped_column(String(20))  # college_club | department | company | community | independent
    city: Mapped[str | None] = mapped_column(String(80))
    bio: Mapped[str | None] = mapped_column(String(500))
    logo_url: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(300))
    instagram: Mapped[str | None] = mapped_column(String(300))
    linkedin: Mapped[str | None] = mapped_column(String(300))
    show_official_email: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())  # default: in-app messages only
    # Trust (group 2)
    faculty_name: Mapped[str | None] = mapped_column(String(120))
    faculty_email: Mapped[str | None] = mapped_column(String(255))
    # Notifications (group 3): which organizer alerts to get, and one daily digest instead of one per registration
    notif_prefs: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    daily_digest: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
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
    category: Mapped[str] = mapped_column(String(60), default="")  # free text from the poster or form
    # hackathon | competition | internship | workshop | conference | meetup | webinar | other (item 12).
    # Internships have an apply-by deadline instead of a time: start_at = end_at = registration_deadline.
    event_type: Mapped[str] = mapped_column(String(16), default="other", server_default="other", index=True)
    category_slug: Mapped[str | None] = mapped_column(ForeignKey("categories.slug", ondelete="SET NULL"), index=True)
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
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)  # after it ended: no-shows marked, organizer stats updated
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
    external: Mapped[bool] = mapped_column(Boolean, default=False)  # "I registered" on the organizer's own site
    group_id: Mapped[str | None] = mapped_column(String(36), index=True)  # friends going together share one

    @property
    def checkin_code(self) -> str:
        """Short code for manual check-in when the camera can't scan."""
        return self.checkin_token.replace("-", "")[:6].upper()


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


class Invite(Base):
    """'Go together': a registered student's link that lets friends join them at an event."""

    __tablename__ = "invites"

    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    registration_id: Mapped[str] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuthToken(Base):
    """One-time password-reset links. Only hashes are stored."""

    __tablename__ = "auth_tokens"
    __table_args__ = (Index("ix_auth_tokens_user_kind", "user_id", "kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 of the link token
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StoredFile(Base):
    """Uploaded poster images (EXIF-free WebP). In the database so a redeploy can't lose them."""

    __tablename__ = "stored_files"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(40))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SavedAlert(Base):
    """'Remind me of similar events' on an Almost card: the event's main tags plus the day/time it clashed with."""

    __tablename__ = "saved_alerts"
    __table_args__ = (UniqueConstraint("user_id", "source_event_id"), Index("ix_saved_alerts_user", "user_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    source_title: Mapped[str] = mapped_column(String(200))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    day_of_week: Mapped[int] = mapped_column(Integer)  # IST, Monday = 0
    start_min: Mapped[int] = mapped_column(Integer)  # IST minutes since midnight
    end_min: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Category(Base):
    """Browse-by-category cards (prompt v2, item 11). Rows are created by migration 0006."""

    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    emoji: Mapped[str] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class OrgVerificationRequest(Base):
    """'Verify organization': a college ID, faculty letter or company proof, sent to admin review."""

    __tablename__ = "org_verification_requests"
    __table_args__ = (Index("ix_org_verif_org", "organizer_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organizer_id: Mapped[str] = mapped_column(ForeignKey("organizers.id", ondelete="CASCADE"))
    document_name: Mapped[str] = mapped_column(String(64))  # a stored_files row; never served publicly
    document_type: Mapped[str] = mapped_column(String(24))  # college_id | faculty_letter | company_proof | other
    note: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | approved | rejected
    decided_by: Mapped[str | None] = mapped_column(String(36))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Follow(Base):
    """A student following a club. Organizers only ever see the count, never who."""

    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("student_id", "organizer_id"), Index("ix_follows_organizer", "organizer_id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organizer_id: Mapped[str] = mapped_column(ForeignKey("organizers.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
