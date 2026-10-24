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


def fmt_range(start_local: datetime, end_local: datetime) -> str:
    """'2 to 6 PM', '11 AM to 1 PM'."""
    if (start_local.hour < 12) == (end_local.hour < 12):
        first = fmt_time(start_local).rsplit(" ", 1)[0]
    else:
        first = fmt_time(start_local)
    return f"{first} to {fmt_time(end_local)}"


def iso_utc(dt: datetime | None) -> str | None:
    return None if dt is None else dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
