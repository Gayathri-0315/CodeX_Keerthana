"""All datetimes are stored as naive UTC. Local (IST) is only for input and display."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_ist(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(IST)


def ist_today() -> date:
    return to_ist(utcnow()).date()


def ist_to_utc(d: date, minute_of_day: int) -> datetime:
    """Local date + minutes since local midnight -> naive UTC. 1440 means next midnight."""
    local = datetime.combine(d, time(0), tzinfo=IST) + timedelta(minutes=minute_of_day)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def fmt_time(dt_local: datetime) -> str:
    """'3 PM' or '2:25 PM'."""
    h = dt_local.hour % 12 or 12
    suffix = "AM" if dt_local.hour < 12 else "PM"
    return f"{h} {suffix}" if dt_local.minute == 0 else f"{h}:{dt_local.minute:02d} {suffix}"


def iso_utc(dt: datetime | None) -> str | None:
    return None if dt is None else dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
