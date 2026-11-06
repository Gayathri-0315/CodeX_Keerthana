"""Organizer listings: form -> event fields, the trust gate with duplicate detection, and reach preview."""

import re
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, Organizer, User
from ..schemas import EventIn
from ..seed.venues import AREAS
from ..timeutil import ist_to_utc, to_ist, utcnow
from . import embeddings, extraction, scam_model, spam
from .feed import user_going, user_profile, user_windows
from .matching import check_event
from .ranking import score_event, tag_label

DUPLICATE_COSINE = 0.92
DUPLICATE_TITLE_OVERLAP = 0.8
TITLE_WORD = re.compile(r"[a-z0-9]+")
REACH_MIN_MATCH = 75


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def form_times(form: EventIn) -> tuple[datetime | None, datetime | None, datetime | None]:
    """IST form date/times -> naive UTC start, end and registration deadline (end of that day).

    Internships have no session time: the apply-by date (end of that day) is start, end and deadline.
    """
    if form.event_type == "internship":
        day = form.registration_deadline or form.date
        if day is None:
            return None, None, None
        due = ist_to_utc(day, 23 * 60 + 59)
        return due, due, due
    if form.date is None or not form.start_time:
        return None, None, None
    start = ist_to_utc(form.date, _minutes(form.start_time))
    end = ist_to_utc(form.date, _minutes(form.end_time)) if form.end_time else start + timedelta(hours=2)
    deadline = None
    if form.registration_deadline:
        deadline = min(start, ist_to_utc(form.registration_deadline, 23 * 60 + 59))
    return start, end, deadline


def form_coords(db: Session, form: EventIn) -> tuple[float | None, float | None]:
    if form.mode == "online":
        return None, None
    if form.area:
        area = next((a for a in AREAS if a["name"] == form.area), None)
        if area:
            return area["lat"], area["lng"]
    from .geocode import geocode

    hit = geocode(db, " ".join(x for x in (form.address, form.venue_name) if x))
    return (hit["lat"], hit["lng"]) if hit else (None, None)


def apply_form(db: Session, event: Event, form: EventIn) -> None:
    start, end, deadline = form_times(form)
    lat, lng = form_coords(db, form)
    event.title = form.title.strip()
    event.description = form.description.strip()
    event.category = form.category.strip()
    event.event_type = form.event_type
    from .categories import SLUGS

    event.category_slug = form.category_slug if form.category_slug in SLUGS else None
    event.tags = form.tags
    event.mode = form.mode
    event.venue_name = (form.venue_name or "").strip() or None
    event.address = (form.address or "").strip() or None
    event.lat, event.lng = lat, lng
    event.start_at, event.end_at, event.registration_deadline = start, end, deadline
    event.fee_inr = form.fee_inr
    event.capacity = form.capacity
    event.eligibility = {"required_tags": form.eligibility_tags, "text": (form.eligibility_text or "").strip()}
    event.skill_level = form.skill_level
    event.registration_url = form.registration_url
    event.poster_url = form.poster_url
    event.source = form.source
    event.field_confidence = form.field_confidence
    embeddings.invalidate_event(event.id or "")


def event_form(e: Event) -> dict:
    """An Event back into the organizer form shape (IST)."""
    start = to_ist(e.start_at) if e.start_at else None
    end = to_ist(e.end_at) if e.end_at else None
    area = next((a["name"] for a in AREAS if e.lat is not None and abs(a["lat"] - e.lat) < 1e-6 and abs(a["lng"] - e.lng) < 1e-6), None)
    return {
        "title": e.title, "description": e.description, "category": e.category, "event_type": e.event_type, "tags": e.tags or [],
        "category_slug": e.category_slug,
        "date": start.date().isoformat() if start else None,
        "start_time": start.strftime("%H:%M") if start else None,
        "end_time": end.strftime("%H:%M") if end else None,
        "mode": e.mode, "venue_name": e.venue_name, "address": e.address, "area": area,
        "fee_inr": e.fee_inr, "capacity": e.capacity,
        "registration_deadline": to_ist(e.registration_deadline).date().isoformat() if e.registration_deadline else None,
        "eligibility_text": (e.eligibility or {}).get("text") or None,
        "eligibility_tags": (e.eligibility or {}).get("required_tags") or [],
        "skill_level": e.skill_level, "registration_url": e.registration_url, "poster_url": e.poster_url,
        "source": e.source, "field_confidence": e.field_confidence or {},
    }


# ---- trust gate ----

def find_duplicate(db: Session, event_like, exclude_id: str | None) -> tuple[str, str] | None:
    if event_like.start_at is None:
        return None
    day = to_ist(event_like.start_at).date()
    others = db.scalars(
        select(Event).where(
            Event.status.in_(("published", "pending_review")),
            Event.start_at >= ist_to_utc(day, 0),
            Event.start_at < ist_to_utc(day, 1440),
            Event.id != (exclude_id or ""),
        )
    ).unique().all()
    if not others:
        return None
    mine = embeddings.compute_event_vector(event_like)
    best = max(others, key=lambda o: embeddings.cosine(mine, embeddings.event_vector(o)))
    if embeddings.cosine(mine, embeddings.event_vector(best)) > DUPLICATE_COSINE:
        return best.id, best.title
    # The 0.92 cosine is tuned for the embedding model; keyword vectors of a copy with a reworded
    # description fall short, so near-identical titles on the same date also count.
    same_title = next((o for o in others if title_overlap(event_like.title, o.title) >= DUPLICATE_TITLE_OVERLAP), None)
    return (same_title.id, same_title.title) if same_title else None


def title_overlap(a: str, b: str) -> float:
    ta, tb = set(TITLE_WORD.findall((a or "").lower())), set(TITLE_WORD.findall((b or "").lower()))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def run_gate(db: Session, organizer: Organizer, event_like, exclude_id: str | None, ai: bool = True) -> spam.Assessment:
    """`ai=False` for the live preview (runs on every pause in typing): rules and the learned classifier only."""
    candidate = spam.Candidate(
        title=event_like.title or "", description=event_like.description or "", category=event_like.category or "",
        mode=event_like.mode, venue_name=event_like.venue_name, start_at=event_like.start_at, end_at=event_like.end_at,
        fee_inr=event_like.fee_inr or 0, registration_url=event_like.registration_url, has_organizer=organizer is not None,
        event_type=getattr(event_like, "event_type", "other") or "other",
    )
    assessment = spam.assess(candidate, organizer.trust_level if organizer else None, utcnow(),
                             find_duplicate(db, event_like, exclude_id))
    if blocks := internship_reasons(event_like):
        assessment = spam.Assessment(max(assessment.score, spam.HIGH), blocks + assessment.reasons, assessment.duplicate_of)
    text = f"{candidate.title}\n{candidate.description}\nFee: ₹{candidate.fee_inr}\nLink: {candidate.registration_url or '-'}"
    assessment = learned_check(db, assessment, text)
    judgement = extraction.judge_spam(text) if ai else None
    if judgement:
        assessment = spam.combine_llm(assessment, judgement.risk, judgement.reasons)
    elif ai and (verdict := scam_model.ai_judge(db, text)) is not None:
        assessment = spam.combine_llm(assessment, verdict[0], verdict[1])
    return assessment


def learned_check(db: Session, a: spam.Assessment, text: str) -> spam.Assessment:
    """The classifier trained on admin decisions adds to the score (never lowers it) with a reason admins can read."""
    p, words = scam_model.model(db).p_scam(text)
    bump = 25 if p >= 0.85 else 12 if p >= 0.65 else 0
    if not bump:
        return a
    why = f"Reads like listings that were rejected before ({round(p * 100)}% sure"
    why += f"; for example {', '.join(words)})" if words else ")"
    return spam.Assessment(min(100, a.score + bump), a.reasons + [why], a.duplicate_of)


def is_first_event(db: Session, organizer: Organizer, exclude_id: str | None) -> bool:
    other = db.scalar(
        select(Event.id).where(Event.organizer_id == organizer.id, Event.status == "published", Event.id != (exclude_id or "")).limit(1)
    )
    return other is None


def predicted_outcome(db: Session, organizer: Organizer, assessment: spam.Assessment, exclude_id: str | None,
                      event_like=None) -> tuple[str, str]:
    kind = getattr(event_like, "event_type", "other") or "other"
    return spam.outcome(assessment.score, organizer.trust_level, organizer.org_email_domain,
                        is_first_event(db, organizer, exclude_id), kind, internship_reasons(event_like))


def internship_reasons(event_like) -> list[str]:
    if event_like is None or getattr(event_like, "event_type", None) != "internship":
        return []
    from .event_types import internship_blocks

    return internship_blocks(event_like.title or "", event_like.description or "", event_like.fee_inr or 0, event_like.registration_url)


def form_from_extraction(fields: dict, poster_url: str | None, source: str) -> EventIn:
    """AI-extracted poster fields -> the organizer form (unknowns stay empty for the organizer to fill)."""
    known = {k: v for k, v in fields.items() if k in EventIn.model_fields and v not in (None, "", [])}
    known["tags"] = (known.get("tags") or [])[:4]
    if not known.get("event_type"):
        from .event_types import suggest as suggest_type

        known["event_type"] = suggest_type(fields.get("title") or "", fields.get("category") or "", " ".join(known["tags"]))
    if not known.get("category_slug"):
        from .categories import suggest

        known["category_slug"] = suggest(known["tags"], f'{fields.get("title") or ""} {fields.get("category") or ""}')
    return EventIn.model_validate({**known, "poster_url": poster_url, "source": source,
                                   "field_confidence": fields.get("field_confidence") or {}})


def publish(db: Session, organizer: Organizer, event: Event) -> str:
    """Run the gate and publish, review or block. Used by the organizer API."""
    from fastapi import HTTPException

    from . import feedcache, jobs

    if event.status in ("published", "cancelled"):
        raise HTTPException(409, "This event is already " + ("live." if event.status == "published" else "cancelled."))
    internship = event.event_type == "internship"
    missing = [name for name, ok in (("a title", event.title),
                                     ("an apply-by date" if internship else "a date and start time", event.start_at)) if not ok]
    if event.mode == "in_person" and not internship and not event.venue_name:
        missing.append("a venue")
    if not event.category_slug:
        missing.append("a category")
    if missing:
        raise HTTPException(422, f"Add {' and '.join(missing)} before publishing.")

    assessment = run_gate(db, organizer, event, event.id)
    event.risk_score, event.risk_reasons, event.duplicate_of = assessment.score, assessment.reasons, assessment.duplicate_of
    status, label = predicted_outcome(db, organizer, assessment, event.id, event)
    event.status, event.verification_label = status, label
    if status == "published":
        event.published_at = utcnow()
    db.commit()
    feedcache.invalidate_all()
    if status == "published":
        jobs.in_background(jobs.suggest_for_event, event.id)
    return status


def draft_from_form(db: Session, form: EventIn, organizer: Organizer) -> SimpleNamespace:
    """An unsaved event-like object for previews; quacks like Event for the gate and matching."""
    start, end, deadline = form_times(form)
    lat, lng = form_coords(db, form)
    return SimpleNamespace(
        id="preview", organizer=organizer, title=form.title, description=form.description, category=form.category,
        event_type=form.event_type, category_slug=form.category_slug,
        tags=form.tags, mode=form.mode, venue_name=form.venue_name, address=form.address, lat=lat, lng=lng,
        start_at=start, end_at=end, registration_deadline=deadline, fee_inr=form.fee_inr, capacity=form.capacity,
        eligibility={"required_tags": form.eligibility_tags, "text": form.eligibility_text or ""},
        skill_level=form.skill_level, registration_url=form.registration_url, status="published",
    )


# ---- reach preview ----

REACH_FIELDS = ("title", "description", "category", "tags", "mode", "venue_name", "lat", "lng", "start_at", "end_at",
                "fee_inr", "capacity", "eligibility", "skill_level")


def reach_probe(event_like):
    """A stand-in for the draft, as it will look once published. None without a date and time."""
    # A throwaway id keeps this probe's vector out of the shared cache key space.
    probe = SimpleNamespace(**{k: getattr(event_like, k) for k in REACH_FIELDS}, id=f"reach:{uuid.uuid4().hex}")
    probe.status = "published"
    probe.registration_deadline = None  # a draft's deadline shouldn't hide it from its own preview
    probe.event_type = getattr(event_like, "event_type", "other")
    if probe.start_at is None or probe.end_at is None:
        return None
    return probe


def reach(db: Session, event_like) -> dict:
    """Students who'd pass the hard filters with match >= 75, plus a small breakdown."""
    probe = reach_probe(event_like)
    if probe is None:
        return {"count": 0, "free": 0, "interested": 0, "interest_label": None, "ready": False}

    # Preview an event as it will look before it starts, even if the draft's date is already past.
    now = min(utcnow(), probe.start_at - timedelta(minutes=1))
    top_tag = (probe.tags or [None])[0]
    students = db.scalars(select(User).where(User.role == "student")).all()
    fit = free = interested = 0
    try:
        for u in students:
            if top_tag and any(i.tag == top_tag for i in u.interests):
                interested += 1
            fr = check_event(u, probe, user_windows(db, u), now, going=user_going(db, u))
            if not fr.passed:
                continue
            free += 1
            profile, _ = user_profile(db, u)
            if score_event(probe, u, fr, profile).match >= REACH_MIN_MATCH:
                fit += 1
    finally:
        embeddings.invalidate_event(probe.id)
    return {"count": fit, "free": free, "interested": interested, "interest_label": tag_label(top_tag) if top_tag else None, "ready": True}
