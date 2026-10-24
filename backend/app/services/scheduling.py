"""Free-time model (SPEC 5.1).

A date's free time = recurring free slots for its weekday + one-off `free` slots on that date,
minus one-off `busy_override` slots on that date. Windows are returned merged, sorted, in naive UTC.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from ..timeutil import ist_to_utc

Interval = tuple[int, int]  # minutes since local midnight, end exclusive


def merge(intervals: Iterable[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for s, e in sorted(i for i in intervals if i[1] > i[0]):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def subtract(base: list[Interval], cut: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for s, e in base:
        pieces = [(s, e)]
        for cs, ce in cut:
            nxt = []
            for ps, pe in pieces:
                if ce <= ps or cs >= pe:
                    nxt.append((ps, pe))
                    continue
                if cs > ps:
                    nxt.append((ps, cs))
                if ce < pe:
                    nxt.append((ce, pe))
            pieces = nxt
        out.extend(pieces)
    return out


def day_intervals(slots, d: date) -> list[Interval]:
    """Free intervals (local minutes) for one date. `slots` are AvailabilitySlot-like objects."""
    free: list[Interval] = []
    busy: list[Interval] = []
    for s in slots:
        if s.recurring and s.date is None:
            if s.day_of_week == d.weekday() and s.kind == "free":
                free.append((s.start_min, s.end_min))
        elif s.date == d:
            (free if s.kind == "free" else busy).append((s.start_min, s.end_min))
    return merge(subtract(merge(free), merge(busy)))


def free_windows(slots, start: date, end: date) -> list[tuple[datetime, datetime]]:
    """Merged free windows (naive UTC) for every date in [start, end]."""
    windows: list[tuple[datetime, datetime]] = []
    d = start
    while d <= end:
        for s, e in day_intervals(slots, d):
            ws, we = ist_to_utc(d, s), ist_to_utc(d, e)
            if windows and ws <= windows[-1][1]:  # joins across midnight
                windows[-1] = (windows[-1][0], max(windows[-1][1], we))
            else:
                windows.append((ws, we))
        d += timedelta(days=1)
    return windows


def gaps_from_periods(periods_by_day: dict[int, list[Interval]], day_start: int, day_end: int) -> dict[int, list[Interval]]:
    """Timetable import: busy class periods -> free gaps inside [day_start, day_end] per weekday."""
    out: dict[int, list[Interval]] = defaultdict(list)
    for dow in range(7):
        out[dow] = subtract([(day_start, day_end)], merge(periods_by_day.get(dow, [])))
    return dict(out)
