"""Best time to schedule: which start time reaches the most students who'd fit and are actually free?

Uses ShowUp's own data (students' free time and interests), which no other platform has:
1. The pool: students who'd be a good match for this event if timing weren't an issue (match >= 75,
   passing every filter except their schedule).
2. For the next days at common start times, count how many of the pool are free (travel included).
3. Suggest the best few, only when they clearly beat the organizer's chosen time.
Counts only; never who. Organizers decide.
"""

import random
from datetime import datetime, time, timedelta
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import User
from ..timeutil import ist_today, ist_to_utc, to_ist, utcnow
from .feed import user_going, user_profile, user_windows
from .matching import check_event
from .ranking import score_event

DAYS_AHEAD = 10
START_HOURS = (10, 14, 16, 18)
MIN_MATCH = 75
MAX_POOL = 1500  # sample beyond this and scale, so it stays fast as ShowUp grows
MIN_GAIN = 3  # suggest only if it reaches at least this many more students...
MIN_RATIO = 1.2  # ...and at least 20% more


def _at(probe, start: datetime, duration: timedelta):
    p = SimpleNamespace(**vars(probe))
    p.start_at, p.end_at = start, start + duration
    return p


def suggest(db: Session, event_like) -> dict:
    """-> {"ready", "current", "options": [{start_at, end_at, label, count}], "pool"}."""
    from . import embeddings
    from .listing import reach_probe

    probe = reach_probe(event_like)
    if probe is None or getattr(event_like, "event_type", None) == "internship":
        return {"ready": False, "current": 0, "options": [], "pool": 0}
    try:
        return _suggest(db, probe)
    finally:
        embeddings.invalidate_event(probe.id)


def _suggest(db: Session, probe) -> dict:
    duration = probe.end_at - probe.start_at
    now = utcnow()
    students = db.scalars(select(User).where(User.role == "student")).all()
    scale = 1.0
    if len(students) > MAX_POOL:
        scale = len(students) / MAX_POOL
        students = random.Random(1).sample(students, MAX_POOL)

    # 1. Who would fit if the timing worked for them.
    pool = []
    look_from = min(now, probe.start_at - timedelta(minutes=1))
    for u in students:
        windows, going = user_windows(db, u), user_going(db, u)
        fr = check_event(u, probe, windows, look_from, going=going)
        if not (fr.passed or fr.almost):
            continue
        profile, _ = user_profile(db, u)
        if score_event(probe, u, fr, profile).match >= MIN_MATCH:
            pool.append((u, windows, going))

    def count(p) -> int:
        return round(sum(1 for u, w, g in pool if check_event(u, p, w, now, going=g).passed) * scale)

    current = count(probe) if probe.start_at > now else 0
    options = []
    first_day = ist_today() + timedelta(days=2)  # leave time to spread the word
    for d in range(DAYS_AHEAD):
        day = first_day + timedelta(days=d)
        for h in START_HOURS:
            start = ist_to_utc(day, h * 60)
            if abs((start - probe.start_at).total_seconds()) < 3600:
                continue  # that's the current time
            options.append((count(_at(probe, start, duration)), start))
    options.sort(key=lambda o: (-o[0], o[1]))
    best = []
    for n, start in options:
        if n < current + MIN_GAIN or n < current * MIN_RATIO:
            break
        # Prefer different days, so the options are real alternatives.
        if any(to_ist(start).date() == to_ist(b[1]).date() for b in best):
            continue
        best.append((n, start))
        if len(best) == 3:
            break
    return {
        "ready": True,
        "current": current,
        "pool": round(len(pool) * scale),
        "options": [{"start_at": s.isoformat() + "Z", "end_at": (s + duration).isoformat() + "Z", "count": n,
                     "label": f"{to_ist(s):%a %d %b, %I:%M %p}".replace(" 0", " ")} for n, s in best],
    }
