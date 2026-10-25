"""A single-event iCalendar file (RFC 5545) for "Add to calendar"."""

from ..timeutil import utcnow


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fmt(dt) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")  # stored naive UTC


def _fold(line: str) -> str:
    """Lines over 75 octets continue on the next line with a leading space."""
    out, raw = [], line.encode()
    while len(raw) > 75:
        cut = 75
        while (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode())
        raw = b" " + raw[cut:]
    out.append(raw.decode())
    return "\r\n".join(out)


def event_ics(event, url: str) -> str:
    location = ", ".join(x for x in (event.venue_name, event.address) if x) or "Online"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ShowUp//Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event.id}@showup",
        f"DTSTAMP:{_fmt(utcnow())}",
        f"DTSTART:{_fmt(event.start_at)}",
        f"DTEND:{_fmt(event.end_at)}",
        f"SUMMARY:{_esc(event.title)}",
        f"DESCRIPTION:{_esc((event.description or '') + chr(10) + url)}",
        f"LOCATION:{_esc(location)}",
        f"URL:{url}",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:Event reminder",
        "TRIGGER:-PT2H",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
