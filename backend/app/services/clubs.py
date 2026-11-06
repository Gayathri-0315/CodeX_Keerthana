"""Club pages and follow (feature 5)."""

import re
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Event, Follow, Organizer, User
from ..timeutil import DAY_NAMES, fmt_time, to_ist, utcnow

MIN_COMPLETED_FOR_STATS = 3


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:60] or "club"


def unique_slug(db: Session, name: str, exclude_id: str | None = None) -> str:
    base, n = slugify(name), 1
    slug = base
    while db.scalar(select(Organizer.id).where(Organizer.slug == slug, Organizer.id != (exclude_id or ""))):
        n += 1
        slug = f"{base}-{n}"
    return slug


def ensure_slug(db: Session, org: Organizer) -> str:
    if not org.slug:
        org.slug = unique_slug(db, org.org_name, org.id)
        db.commit()
    return org.slug


def follower_count(db: Session, org_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Follow).where(Follow.organizer_id == org_id)) or 0


def follower_growth(db: Session, org_id: str, weeks: int = 8) -> list[int]:
    """Followers at the end of each of the last `weeks` weeks (oldest first). Counts only, never who."""
    now = utcnow()
    times = sorted(db.scalars(select(Follow.created_at).where(Follow.organizer_id == org_id)))
    return [sum(1 for t in times if t <= now - timedelta(weeks=weeks - 1 - k)) for k in range(weeks)]


def is_clean(event: Event) -> bool:
    return event.status == "published" and event.verification_label != "unverified" and event.risk_score < 30


def notify_followers(db: Session, event: Event, now: datetime | None = None) -> int:
    """'<Club> just posted: <event>' to followers who want club updates. It need not fit their free time.

    Same weekly cap, quiet hours, pause and dedupe as other suggestions; never for flagged or blocked events.
    """
    from . import notify
    from .feed import evaluate_one

    now = now or utcnow()
    if not is_clean(event) or event.organizer is None:
        return 0
    org = event.organizer
    sent = 0
    followers = db.scalars(select(User).join(Follow, Follow.student_id == User.id).where(Follow.organizer_id == org.id)).all()
    for user in followers:
        if not user.follow_updates or notify.is_paused(user, now) or not notify.any_channel(user):
            continue
        if any(notify.already_sent(db, user, event.id, k) for k in ("club_post", "match", "similar")):
            continue
        if not notify.cap_allows(db, user, "club_post", now):
            continue
        start = to_ist(event.start_at)
        when = f"Apply by {DAY_NAMES[start.weekday()][:3]}" if event.event_type == "internship" else f"{DAY_NAMES[start.weekday()][:3]}, {fmt_time(start)}"
        ev = evaluate_one(db, user, event)
        fits = ev.result.passed and ev.result.window is not None
        title = notify._fit(f"{notify._short(org.org_name, 30)} just posted: {notify._short(event.title, 50)}")[:120]
        body = f"{when}. Fits your free time." if fits else f"{when}."
        if notify.create(db, user, "club_post", event, title, body, {"fits": fits}, now=now):
            sent += 1
    return sent


def club_out(db: Session, org: Organizer, viewer: User | None) -> dict:
    """Public club page. Never student names or counts small enough to identify anyone."""
    from .feed import registered_counts

    now = utcnow()
    upcoming = db.scalars(select(Event).where(Event.organizer_id == org.id, Event.status == "published", Event.start_at > now)
                          .order_by(Event.start_at)).unique().all()
    past = db.scalars(select(Event).where(Event.organizer_id == org.id, Event.status == "published", Event.end_at < now)
                      .order_by(Event.start_at.desc()).limit(10)).unique().all()
    completed = db.scalar(select(func.count()).select_from(Event).where(
        Event.organizer_id == org.id, Event.status == "published", Event.end_at < now)) or 0
    completed = max(completed, org.past_events_count or 0)
    show_stats = completed >= MIN_COMPLETED_FOR_STATS
    counts = registered_counts(db, [e.id for e in upcoming]) if upcoming else {}
    brief = lambda e: {"id": e.id, "title": e.title, "start_at": e.start_at.isoformat() + "Z" if e.start_at else None,  # noqa: E731
                       "end_at": e.end_at.isoformat() + "Z" if e.end_at else None, "event_type": e.event_type,
                       "category_slug": e.category_slug, "mode": e.mode, "venue_name": e.venue_name, "fee_inr": e.fee_inr,
                       "poster_url": e.poster_url, "category": e.category, "seats_taken": counts.get(e.id, 0)}
    following = bool(viewer and viewer.role == "student" and db.scalar(
        select(Follow.id).where(Follow.student_id == viewer.id, Follow.organizer_id == org.id)))
    return {
        "slug": ensure_slug(db, org),
        "name": org.org_name,
        "logo_url": org.logo_url,
        "bio": org.bio,
        "org_type": org.org_type,
        "college_or_company": org.college_or_company,
        "city": org.city,
        "trust_level": org.trust_level,
        "trust_label": {"new": "New", "verified": "Verified", "trusted": "Trusted"}.get(org.trust_level),
        "website": org.website, "instagram": org.instagram, "linkedin": org.linkedin,
        "contact_email": org.user.email if org.show_official_email and org.user else None,
        "followers": follower_count(db, org.id),
        "following": following,
        "events_hosted": completed if show_stats else None,
        "attendance_rate": org.avg_attendance_rate if show_stats else None,
        "upcoming": [brief(e) for e in upcoming],
        "past": [brief(e) for e in past],
    }


# Words that say "I'm looking for a club" rather than naming one.
_CLUB_WORDS = {"club", "clubs", "organizer", "organizers", "organiser", "organisers", "community", "communities",
               "society", "societies", "chapter", "team"}
_FILLER = {"a", "an", "the", "of", "by", "from", "for", "in", "at", "on", "and", "to", "me", "my", "show", "find", "search",
           "follow", "following", "events", "event", "page", "near", "all", "any", "list", "which", "what", "who", "is", "are"}


def search(db: Session, text: str, viewer: User | None, limit: int = 6) -> list[dict]:
    """Clubs whose name matches the search. College or city words only help rank a name match, so
    "hackathons in Coimbatore" doesn't list every club in Coimbatore. "clubs" alone lists the most followed."""
    words = [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())]
    asks_for_clubs = any(w in _CLUB_WORDS for w in words)
    terms = [w for w in words if w not in _FILLER and w not in _CLUB_WORDS and len(w) >= 2]
    terms = [w[:-1] if len(w) > 4 and w.endswith("s") else w for w in terms]  # "hackathons" finds "Hackathon Club"
    if not terms and not asks_for_clubs:
        return []
    orgs = db.scalars(select(Organizer)).all()
    counts = dict(db.execute(select(Follow.organizer_id, func.count()).group_by(Follow.organizer_id)).all())
    trust = {"trusted": 2, "verified": 1}
    scored = []
    for o in orgs:
        name = (o.org_name or "").lower()
        place = f"{o.college_or_company or ''} {o.city or ''}".lower()
        name_words = set(re.findall(r"[a-z0-9]+", name))
        hit = lambda t, txt, ws: t in ws if len(t) < 3 else t in txt  # noqa: E731 - "ai" must be a whole word
        in_name = sum(1 for t in terms if hit(t, name, name_words))
        if terms and not in_name:
            continue
        score = in_name * 3 + sum(1 for t in terms if hit(t, place, set(re.findall(r"[a-z0-9]+", place))) and not hit(t, name, name_words))
        scored.append((score, trust.get(o.trust_level, 0), counts.get(o.id, 0), o))
    scored.sort(key=lambda s: (-s[0], -s[1], -s[2], s[3].org_name or ""))
    following = set()
    if viewer is not None and viewer.role == "student":
        following = set(db.scalars(select(Follow.organizer_id).where(Follow.student_id == viewer.id)))
    return [{"slug": ensure_slug(db, o), "name": o.org_name, "logo_url": o.logo_url, "city": o.city,
             "college_or_company": o.college_or_company,
             "trust_level": o.trust_level, "trust_label": {"verified": "Verified", "trusted": "Trusted"}.get(o.trust_level),
             "followers": n, "following": o.id in following} for _, _, n, o in scored[:limit]]
