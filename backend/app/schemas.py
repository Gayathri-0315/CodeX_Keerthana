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


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class DemoLoginIn(BaseModel):
    role: Literal["student", "organizer", "admin"] = "student"


# ---- users ----

class InterestOut(Out):
    tag: str
    weight: int


class OrganizerOut(Out):
    id: str
    org_name: str
    trust_level: str


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
    telegram_linked: bool = False
    notif_channels: dict
    notif_max_per_week: int
    quiet_hours_start: str
    quiet_hours_end: str
    notif_paused_until: datetime | None
    onboarded: bool
    organizer: OrganizerOut | None = None


class UserPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
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
