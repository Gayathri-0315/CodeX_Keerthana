"""Admin view of the people and events on ShowUp: every event's registrants with their details, students, organizers.

Admins only. Read-only. Each view of someone's details is logged (who looked, at what), so access can be audited.
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Application, Event, Follow, Organizer, Registration, User
from ..services import smart_find
from ..timeutil import iso_utc, utcnow
from .admin import admin_only

router = APIRouter(prefix="/admin", tags=["admin"])
log = logging.getLogger("showup.admin")

ACTIVE = ("registered", "promoted_pending", "attended", "no_show")
TAG_NAMES = {"college_student": "College student", "school_student": "School student", "graduate": "Graduate",
             "working": "Working"}


def _tags(tags: list | None) -> dict:
    """eligibility tags -> readable department and year."""
    tags = tags or []
    dept = next((t[:-5].upper() for t in tags if t.endswith("_dept")), None)
    year = next((f"Year {t[5:]}" for t in tags if re.fullmatch(r"year_\d", t)), None)
    kind = next((TAG_NAMES[t] for t in tags if t in TAG_NAMES), None)
    return {"department": dept, "year": year, "kind": kind}


def _like(q: str) -> str:
    return f"%{q.strip().lower()}%"


def _person(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "college": u.college, "home_area": u.home_area,
            "skill_level": u.skill_level, **_tags(u.eligibility_tags),
            "interests": [i.tag for i in sorted(u.interests or [], key=lambda i: -i.weight)],
            "joined": iso_utc(u.created_at), "last_active": iso_utc(u.last_active_at)}


def _event_brief(e: Event, org_name: str | None, counts: dict) -> dict:
    c = counts.get(e.id, {})
    return {"id": e.id, "title": e.title, "status": e.status, "event_type": e.event_type, "mode": e.mode,
            "venue_name": e.venue_name, "start_at": iso_utc(e.start_at), "end_at": iso_utc(e.end_at), "fee_inr": e.fee_inr,
            "capacity": e.capacity, "organizer": org_name, "registered": c.get("registered", 0),
            "waitlisted": c.get("waitlisted", 0), "attended": c.get("attended", 0), "applications": c.get("applications", 0)}


def _counts(db: Session, event_ids: list[str]) -> dict:
    out: dict[str, dict] = {i: {} for i in event_ids}
    if not event_ids:
        return out
    for eid, status, n in db.execute(select(Registration.event_id, Registration.status, func.count())
                                     .where(Registration.event_id.in_(event_ids)).group_by(Registration.event_id, Registration.status)):
        d = out[eid]
        if status in ACTIVE:
            d["registered"] = d.get("registered", 0) + n
        if status == "attended":
            d["attended"] = n
        if status == "waitlisted":
            d["waitlisted"] = n
    for eid, n in db.execute(select(Application.event_id, func.count()).where(Application.event_id.in_(event_ids))
                             .group_by(Application.event_id)):
        out[eid]["applications"] = n
    return out


@router.get("/events")
def events(q: str = Query("", max_length=100), when: str = Query("upcoming", pattern="^(upcoming|past|all)$"),
           user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Every event (any status), with registration counts. Tap one for its registrants."""
    now = utcnow()
    stmt = select(Event, Organizer.org_name).outerjoin(Organizer, Organizer.id == Event.organizer_id)
    if when == "upcoming":
        stmt = stmt.where(Event.end_at >= now).order_by(Event.start_at)
    elif when == "past":
        stmt = stmt.where(Event.end_at < now).order_by(Event.start_at.desc())
    else:
        stmt = stmt.order_by(Event.start_at.desc())
    wanted, source = smart_find.terms(q, "events")
    if wanted:  # a sentence: every key term must appear somewhere in the event's details
        rows = [(e, name) for e, name in db.execute(stmt.limit(3000)).unique().all()
                if smart_find.matches(smart_find.text_of(e.title, name, e.event_type, e.status, e.mode, e.venue_name,
                                                         e.category, e.tags, "free" if not e.fee_inr else "paid"), wanted)][:200]
    else:
        rows = db.execute(stmt.limit(200)).unique().all()
    counts = _counts(db, [e.id for e, _ in rows])
    return {"items": [_event_brief(e, name, counts) for e, name in rows], "terms": wanted, "source": source}


@router.get("/events/{event_id}/people")
def event_people(event_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Who registered (or applied, for internships), with their details."""
    e = db.get(Event, event_id)
    if e is None:
        raise HTTPException(404, "That event doesn't exist.")
    log.info("admin %s viewed registrants of event %s", user.id, e.id)
    org = db.get(Organizer, e.organizer_id) if e.organizer_id else None
    regs = db.execute(select(Registration, User).join(User, User.id == Registration.user_id)
                      .where(Registration.event_id == e.id)
                      .order_by(Registration.status == "cancelled", Registration.waitlist_position.nulls_first(),
                                Registration.registered_at)).all()
    apps = db.execute(select(Application, User).join(User, User.id == Application.user_id)
                      .where(Application.event_id == e.id).order_by(Application.created_at)).all()
    return {
        "event": _event_brief(e, org.org_name if org else None, _counts(db, [e.id])),
        "registrations": [{**_person(u), "status": r.status, "waitlist_position": r.waitlist_position,
                           "registered_at": iso_utc(r.registered_at), "checked_in_at": iso_utc(r.checked_in_at),
                           "with_friends": r.group_id is not None} for r, u in regs],
        "applications": [{**_person(u), "status": a.status, "note": a.note, "link": a.link, "applied_at": iso_utc(a.created_at)}
                         for a, u in apps],
    }


@router.get("/students")
def students(q: str = Query("", max_length=100), user: User = Depends(admin_only), db: Session = Depends(get_db)):
    stmt = select(User).where(User.role == "student").order_by(User.created_at.desc())
    wanted, source = smart_find.terms(q, "students")
    if wanted:  # every key term must appear somewhere in the student's details
        people = [u for u in db.scalars(stmt.limit(5000)).all()
                  if smart_find.matches(smart_find.text_of(*(v for k, v in _person(u).items() if k not in ("id", "joined", "last_active"))),
                                        wanted)][:200]
    else:
        people = db.scalars(stmt.limit(200)).all()
    ids = [u.id for u in people]
    reg = dict(db.execute(select(Registration.user_id, func.count()).where(Registration.user_id.in_(ids), Registration.status.in_(ACTIVE))
                          .group_by(Registration.user_id)).all()) if ids else {}
    att = dict(db.execute(select(Registration.user_id, func.count()).where(Registration.user_id.in_(ids), Registration.status == "attended")
                          .group_by(Registration.user_id)).all()) if ids else {}
    return {"items": [{"id": u.id, "name": u.name, "email": u.email, "college": u.college, **_tags(u.eligibility_tags),
                       "joined": iso_utc(u.created_at), "registrations": reg.get(u.id, 0), "attended": att.get(u.id, 0)}
                      for u in people], "terms": wanted, "source": source}


@router.get("/students/{user_id}")
def student(user_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None or u.role != "student":
        raise HTTPException(404, "That student doesn't exist.")
    log.info("admin %s viewed student %s", user.id, u.id)
    rows = db.execute(select(Registration, Event, Organizer.org_name).join(Event, Event.id == Registration.event_id)
                      .outerjoin(Organizer, Organizer.id == Event.organizer_id)
                      .where(Registration.user_id == u.id).order_by(Event.start_at.desc())).all()
    apps = db.execute(select(Application, Event).join(Event, Event.id == Application.event_id)
                      .where(Application.user_id == u.id).order_by(Application.created_at.desc())).all()
    following = db.scalars(select(Organizer.org_name).join(Follow, Follow.organizer_id == Organizer.id)
                           .where(Follow.student_id == u.id)).all()
    return {
        **_person(u), "max_distance_km": u.max_distance_km, "budget_max_inr": u.budget_max_inr, "following": following,
        "history": [{"event_id": e.id, "title": e.title, "organizer": name, "start_at": iso_utc(e.start_at), "status": r.status,
                     "checked_in_at": iso_utc(r.checked_in_at)} for r, e, name in rows],
        "applications": [{"event_id": e.id, "title": e.title, "status": a.status, "applied_at": iso_utc(a.created_at)} for a, e in apps],
    }


@router.get("/organizers/{organizer_id}")
def organizer(organizer_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    o = db.get(Organizer, organizer_id)
    if o is None:
        raise HTTPException(404, "That organizer doesn't exist.")
    log.info("admin %s viewed organizer %s", user.id, o.id)
    owner = db.get(User, o.user_id)
    evs = db.scalars(select(Event).where(Event.organizer_id == o.id).order_by(Event.start_at.desc())).unique().all()
    counts = _counts(db, [e.id for e in evs])
    followers = db.scalar(select(func.count()).select_from(Follow).where(Follow.organizer_id == o.id)) or 0
    return {
        "id": o.id, "name": o.org_name, "slug": o.slug, "trust_level": o.trust_level, "org_type": o.org_type,
        "college_or_company": o.college_or_company, "city": o.city, "bio": o.bio, "phone": o.phone,
        "website": o.website, "instagram": o.instagram, "linkedin": o.linkedin,
        "faculty_name": o.faculty_name, "faculty_email": o.faculty_email, "email_domain": o.org_email_domain,
        "contact_name": owner.name if owner else None, "email": owner.email if owner else None,
        "joined": iso_utc(owner.created_at) if owner else None, "last_active": iso_utc(owner.last_active_at) if owner else None,
        "followers": followers, "attendance_rate": o.avg_attendance_rate,
        "events": [_event_brief(e, o.org_name, counts) for e in evs],
    }
