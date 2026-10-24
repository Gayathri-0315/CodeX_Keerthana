"""Hard filters (SPEC 5.2). Ranking (5.3) builds on `check_event` results."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..timeutil import DAY_NAMES, fmt_time, to_ist
from .travel import haversine_km, travel_minutes, user_home

BUFFER_MIN = 10


@dataclass
class FilterResult:
    passed: bool
    failed_rule: str | None = None  # status | eligibility | format | budget | distance | schedule
    reason: str | None = None
    distance_km: float | None = None
    travel_min: int = 0
    window: tuple[datetime, datetime] | None = None
    waitlist: bool = False
    need_start: datetime | None = None  # when the user must be free from (start - travel - buffer)

    @property
    def almost(self) -> bool:
        return self.failed_rule == "schedule"


def _schedule_conflict(event, need_start: datetime, windows) -> str:
    start_l, end_l = to_ist(event.start_at), to_ist(event.end_at)
    day = DAY_NAMES[start_l.weekday()]
    same_day = [w for w in windows if to_ist(w[0]).date() == start_l.date() or to_ist(w[1] - timedelta(minutes=1)).date() == start_l.date()]
    if not same_day:
        return f"You're not free on {day}."

    # Pick the free window that overlaps the event most and explain the edge that breaks.
    def overlap(w):
        return (min(w[1], event.end_at) - max(w[0], need_start)).total_seconds()

    w = max(same_day, key=overlap)
    if overlap(w) <= 0:
        return f"Runs {fmt_time(start_l)} to {fmt_time(end_l)}, you're not free then on {day}."
    if event.end_at > w[1]:
        return f"Runs until {fmt_time(end_l)}, you're free until {fmt_time(to_ist(w[1]))} on {day}."
    return f"You'd need to leave by {fmt_time(to_ist(need_start))}, you're free from {fmt_time(to_ist(w[0]))} on {day}."


def check_event(user, event, windows, now: datetime, registered_count: int = 0) -> FilterResult:
    """Run the hard filters in spec order. `windows` are the user's merged free windows (naive UTC)."""
    # 1. Status, not started, deadline open.
    if event.status != "published" or event.start_at is None or event.end_at is None:
        return FilterResult(False, "status", "Not open for registration.")
    if event.start_at <= now:
        return FilterResult(False, "status", "Already started.")
    if event.registration_deadline is not None and event.registration_deadline <= now:
        return FilterResult(False, "status", "Registration closed.")

    # 2. Eligibility.
    required = (event.eligibility or {}).get("required_tags") or []
    if any(t not in (user.eligibility_tags or []) for t in required):
        return FilterResult(False, "eligibility", "You're not eligible.")

    # 3. Format.
    if user.format_pref == "in_person" and event.mode == "online":
        return FilterResult(False, "format", "Online only.")
    if user.format_pref == "online" and event.mode == "in_person":
        return FilterResult(False, "format", "In person only.")

    # 4. Budget (None = any budget).
    if user.budget_max_inr is not None and event.fee_inr > user.budget_max_inr:
        return FilterResult(False, "budget", "Over your budget.")

    # 5. Distance, for events you must travel to.
    distance = None
    travel = 0
    if event.mode == "in_person" and event.lat is not None and event.lng is not None:
        distance = haversine_km(*user_home(user), event.lat, event.lng)
        if distance > user.max_distance_km:
            return FilterResult(False, "distance", "Too far away.", distance_km=distance)
        travel = travel_minutes(distance)

    waitlist = event.capacity is not None and registered_count >= event.capacity

    # 6. Schedule fit.
    need_start = event.start_at - timedelta(minutes=travel + BUFFER_MIN)
    window = next((w for w in windows if w[0] <= need_start and w[1] >= event.end_at), None)
    if window is None:
        conflict = _schedule_conflict(event, need_start, windows)
        if user.strict_schedule:
            return FilterResult(False, "schedule", conflict, distance_km=distance, travel_min=travel,
                                waitlist=waitlist, need_start=need_start)
        # Strict schedule off: keep the event but carry the clash so the UI can flag it.
        return FilterResult(True, reason=conflict, distance_km=distance, travel_min=travel,
                            waitlist=waitlist, need_start=need_start)

    # 7. Capacity never drops an event; it only marks waitlist.
    return FilterResult(True, distance_km=distance, travel_min=travel, window=window, waitlist=waitlist,
                        need_start=need_start)
