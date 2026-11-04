import datetime as dt
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth ----

class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    college: str | None = Field(None, max_length=160)


class OrganizerRegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    org_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(None, max_length=32, pattern=r"^[0-9+()\- ]*$")
    college_or_company: str = Field(min_length=2, max_length=160)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    role: Literal["student", "organizer"] | None = None  # the side of the sign-in popup that was used


class VerifyIn(BaseModel):
    code: str | None = Field(None, pattern=r"^\s*\d{6}\s*$")
    token: str | None = Field(None, max_length=200)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8, max_length=128)


# ---- users ----

class InterestOut(Out):
    tag: str
    weight: int


class OrganizerOut(Out):
    id: str
    org_name: str
    trust_level: str
    college_or_company: str | None = None


class UserOut(Out):
    id: str
    name: str
    email: str
    role: str
    city: str
    home_area: str | None
    home_lat: float | None
    home_lng: float | None
    max_distance_km: int
    budget_max_inr: int | None
    format_pref: str
    skill_level: str
    eligibility_tags: list[str]
    interest_text: str
    interests: list[InterestOut]
    strict_schedule: bool
    show_almost: bool
    notif_channels: dict
    notif_max_per_week: int
    quiet_hours_start: str
    quiet_hours_end: str
    notif_paused_until: datetime | None
    onboarded: bool
    college: str | None = None
    email_verified: bool = False
    organizer: OrganizerOut | None = None


class UserPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    college: str | None = Field(None, max_length=160)
    home_area: str | None = None
    home_lat: float | None = Field(None, ge=-90, le=90)
    home_lng: float | None = Field(None, ge=-180, le=180)
    max_distance_km: int | None = Field(None, ge=1, le=100)
    budget_max_inr: int | None = Field(None, ge=0)
    format_pref: Literal["in_person", "online", "either"] | None = None
    skill_level: Literal["beginner", "intermediate", "advanced"] | None = None
    eligibility_tags: list[str] | None = None
    interest_text: str | None = Field(None, max_length=500)
    strict_schedule: bool | None = None
    show_almost: bool | None = None
    notif_channels: dict[str, bool] | None = None
    notif_max_per_week: int | None = Field(None, ge=1, le=7)
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    notif_paused_until: datetime | None = None
    onboarded: bool | None = None

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def _hhmm(cls, v: str | None) -> str | None:
        if v is not None and not HHMM.match(v):
            raise ValueError("Use 24-hour HH:MM.")
        return v


class InterestIn(BaseModel):
    tag: str = Field(min_length=1, max_length=40)
    weight: int = Field(2, ge=1, le=3)


class InterestsPut(BaseModel):
    interests: list[InterestIn] = Field(max_length=40)
    interest_text: str | None = Field(None, max_length=500)


# ---- availability ----

class SlotIn(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_min: int = Field(ge=0, le=1439)
    end_min: int = Field(ge=1, le=1440)
    recurring: bool = True
    date: dt.date | None = None
    kind: Literal["free", "busy_override"] = "free"
    source: Literal["manual", "timetable"] = "manual"

    @field_validator("end_min")
    @classmethod
    def _order(cls, v: int, info) -> int:
        if "start_min" in info.data and v <= info.data["start_min"]:
            raise ValueError("end_min must be after start_min.")
        return v


class SlotOut(SlotIn, Out):
    id: str


class AvailabilityPut(BaseModel):
    slots: list[SlotIn] = Field(max_length=2000)


class AvailabilityOut(BaseModel):
    slots: list[SlotOut]


# ---- organizer events ----

class EventIn(BaseModel):
    """The organizer's form. Lenient enough to assess a half-filled draft; publish checks completeness."""

    title: str = Field("", max_length=200)
    description: str = Field("", max_length=4000)
    category: str = Field("", max_length=60)
    tags: list[str] = Field(default_factory=list, max_length=8)
    date: dt.date | None = None
    start_time: str | None = None
    end_time: str | None = None
    mode: Literal["in_person", "online", "hybrid"] = "in_person"
    venue_name: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=300)
    area: str | None = Field(None, max_length=60)
    fee_inr: int = Field(0, ge=0, le=100_000)
    capacity: int | None = Field(None, ge=1, le=100_000)
    registration_deadline: dt.date | None = None
    eligibility_text: str | None = Field(None, max_length=200)
    eligibility_tags: list[str] = Field(default_factory=list, max_length=8)
    skill_level: Literal["beginner", "intermediate", "advanced"] | None = None
    registration_url: str | None = Field(None, max_length=500)
    poster_url: str | None = Field(None, max_length=200)
    source: Literal["web_upload", "form"] = "form"
    field_confidence: dict[str, float | None] = Field(default_factory=dict)

    @field_validator("start_time", "end_time")
    @classmethod
    def _hhmm(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if not HHMM.match(v):
            raise ValueError("Use 24-hour HH:MM.")
        return v

    @field_validator("registration_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if not re.match(r"^https?://[^\s]+$", v):
            raise ValueError("Use a full link starting with https://")
        return v

    @field_validator("poster_url")
    @classmethod
    def _poster(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if not re.match(r"^/api/files/[0-9a-f]+\.webp$", v):
            raise ValueError("Upload the poster through ShowUp.")
        return v

    @field_validator("tags", "eligibility_tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(t.strip().lower() for t in v if t.strip()))


class AppealIn(BaseModel):
    note: str = Field(min_length=5, max_length=500)


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
