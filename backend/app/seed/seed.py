"""Sample data for LOCAL DEVELOPMENT ONLY. Run: `npm run seed` (python manage.py seed_dev).

Refuses to run when APP_ENV=production. Account passwords come from SEED_DEV_PASSWORD, or a random
one is generated and printed; nothing is hardcoded.
"""

import json
import os
import random
import secrets
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Base, SessionLocal, engine
from ..models import AvailabilitySlot, Event, Organizer, Registration, User, UserInterest
from ..security import hash_password
from ..services import categories, event_types, feedcache, listing, spam
from ..timeutil import ist_to_utc, ist_today, utcnow
from .make_samples import make_posters, make_timetables
from .venues import AREAS, find_area

SEED_DIR = Path(__file__).parent
DEV_DOMAIN = "example.com"  # reserved for documentation, so these addresses can never reach a real inbox
DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

INTEREST_POOL = [
    "ai", "python", "web", "cybersecurity", "data", "hackathons", "design", "robotics", "startups",
    "careers", "cloud", "open-source", "public-speaking", "music", "sports", "volunteering", "photography",
    "product", "iot",
]
FIRST = ["Aarav", "Diya", "Karthik", "Meera", "Ravi", "Ananya", "Vikram", "Priya", "Arjun", "Kavya", "Surya",
         "Nila", "Harish", "Divya", "Gokul", "Lakshmi", "Pranav", "Sneha", "Naveen", "Keerthana", "Rahul",
         "Swetha", "Ajay", "Janani", "Dinesh", "Pooja", "Sanjay", "Varsha", "Vishnu", "Abinaya"]
LAST = ["K", "S", "R", "M", "P", "V", "N", "T", "A", "G"]


def hm(text: str) -> int:
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def event_date(day: str, today: date) -> date:
    """Next occurrence of `day` from tomorrow on, so every seeded event is upcoming."""
    if day == "past":
        return today - timedelta(days=2)
    tomorrow = today + timedelta(days=1)
    return tomorrow + timedelta(days=(DAYS[day] - tomorrow.weekday()) % 7)


def slot(user_id: str, dow: int, start: str, end: str) -> AvailabilitySlot:
    return AvailabilitySlot(user_id=user_id, day_of_week=dow, start_min=hm(start), end_min=hm(end))


def make_user(email: str, name: str, pw: str, role: str = "student", **kw) -> User:
    return User(email=email, name=name, password_hash=pw, role=role, onboarded=True, **kw)


def dev_email(local: str) -> str:
    return f"{local}@{DEV_DOMAIN}"


SAMPLE_NOTE = "Sample event: demo data to show how ShowUp works, not a real event."


def seed(db: Session, password: str, samples_only: bool = False) -> dict:
    """Local dev: everything, including sign-in accounts. samples_only (safe on a live site): only the sample
    clubs, students and events, added next to real data, with accounts nobody can sign in to."""
    if settings.is_production and not samples_only:
        raise SystemExit("Refusing to load sample data: APP_ENV=production.")
    rng = random.Random(42)
    categories.ensure_rows(db)
    pw = hash_password(password)
    today = ist_today()
    now = utcnow()
    if not samples_only:
        _main_student(db, pw)

    def organizer(email, name, org_name, domain, trust, past=0, rate=None):
        u = make_user(email, name, pw, role="organizer")
        db.add(u)
        db.flush()
        from ..services.clubs import unique_slug

        o = Organizer(user_id=u.id, org_name=org_name, slug=unique_slug(db, org_name), org_email_domain=domain, trust_level=trust,
                      past_events_count=past, avg_attendance_rate=rate)
        db.add(o)
        db.flush()
        return o

    return _seed_rest(db, pw, rng, today, now, organizer, samples_only)


def _main_student(db: Session, pw: str) -> None:
    home = find_area("Gandhipuram")
    student = make_user(
        dev_email("asha"), "Asha", pw, college="Sample College of Technology",
        home_area=home["name"], home_lat=home["lat"], home_lng=home["lng"],
        max_distance_km=20, budget_max_inr=200, skill_level="beginner",
        eligibility_tags=["college_student", "it_dept", "year_3"],
        interest_text="Machine learning, building with Python, weekend hackathons",
    )
    student.interests = [UserInterest(tag="ai", weight=3), UserInterest(tag="python", weight=2), UserInterest(tag="hackathons", weight=2)]
    db.add(student)
    db.flush()
    db.add_all([slot(student.id, 5, "14:00", "18:00"), slot(student.id, 6, "09:00", "13:00")])


def _seed_rest(db: Session, pw: str, rng, today, now, organizer, samples_only: bool) -> dict:
    orgs = {
        "club": organizer(dev_email("club"), "Club lead", "Coimbatore AI Club", "kct.ac.in", "trusted", 9, 0.78),
        "new": organizer(dev_email("neworg"), "Quick Careers", "QuickCareers Hub", "gmail.com", "new"),
        "design": organizer(dev_email("design"), "Design lead", "PSG Design Society", "psgtech.ac.in", "verified", 2, 0.71),
        "volunteers": organizer(dev_email("volunteers"), "Volunteer lead", "Kovai Volunteers", "kovaivolunteers.org", "verified", 4, 0.66),
    }
    if not samples_only:
        db.add(make_user(dev_email("admin"), "Admin", pw, role="admin"))

    # ---- 30 generated students (so reach preview has realistic numbers) ----
    students: list[User] = []
    patterns = [
        [(5, "14:00", "18:00"), (6, "09:00", "13:00")],
        [(5, "10:00", "19:00"), (6, "10:00", "19:00")],
        [(d, "17:00", "21:00") for d in range(5)],
        [(5, "08:00", "20:00")],
        [(6, "06:00", "13:00"), (2, "17:00", "21:00")],
        [(3, "15:30", "22:00"), (4, "17:00", "22:00"), (5, "14:00", "22:00")],
    ]
    for i in range(30):
        area = rng.choice(AREAS)
        u = make_user(
            dev_email(f"student{i + 1}"), f"{FIRST[i]} {rng.choice(LAST)}.", pw,
            home_area=area["name"], home_lat=area["lat"], home_lng=area["lng"],
            max_distance_km=rng.choice([10, 15, 20, 25]), budget_max_inr=rng.choice([0, 100, 200, 500, None]),
            skill_level=rng.choice(["beginner", "intermediate", "advanced"]),
            eligibility_tags=["college_student", rng.choice(["it_dept", "cse_dept", "ece_dept", "mech_dept"]),
                              rng.choice(["year_1", "year_2", "year_3", "year_4"])],
        )
        u.interests = [UserInterest(tag=t, weight=rng.randint(1, 3)) for t in rng.sample(INTEREST_POOL, rng.randint(2, 4))]
        db.add(u)
        db.flush()
        for dow, s, e in rng.choice(patterns):
            db.add(slot(u.id, dow, s, e))
        students.append(u)

    # ---- events ----
    spec = json.loads((SEED_DIR / "events.json").read_text(encoding="utf-8"))
    events: dict[str, Event] = {}
    for item in spec:
        d = event_date(item["day"], today)
        start, end = ist_to_utc(d, hm(item["start"])), ist_to_utc(d, hm(item["end"]))
        org = orgs[item["org"]]
        deadline = now + timedelta(hours=item["deadline_in_hours"]) if "deadline_in_hours" in item else start - timedelta(hours=2)
        if item.get("type") == "internship":
            deadline = end = start  # apply-by date: no session time
        clean_label = "organizer_verified" if org.trust_level in ("verified", "trusted") else "details_reviewed"
        status = item.get("status", "published")
        e = Event(
            organizer_id=org.id, title=item["title"],
            description=f"{SAMPLE_NOTE}\n\n{item['description']}" if samples_only else item["description"], category=item["category"],
            category_slug=categories.suggest(item["tags"], item["title"]),
            event_type=item.get("type") or event_types.suggest(item["title"], item["category"], " ".join(item["tags"])),
            tags=item["tags"], mode=item.get("mode", "in_person"), venue_name=item["venue"], address=item["address"],
            lat=item["lat"], lng=item["lng"], start_at=start, end_at=end, registration_deadline=deadline,
            fee_inr=item["fee"], capacity=item["capacity"], eligibility=item.get("eligibility", {}),
            skill_level=item["skill"], registration_url=item.get("registration_url"), status=status,
            verification_label=item.get("label", clean_label), source="form",
            published_at=now - timedelta(days=rng.randint(1, 6)) if status == "published" else None,
        )
        db.add(e)
        db.flush()
        # Run the real gate so seeded risk scores and reasons match what an upload would get.
        # Only earlier events exist yet, so a copy is flagged, never its original.
        a = spam.assess(
            spam.Candidate(e.title, e.description, e.category, e.mode, e.venue_name, e.start_at, e.end_at, e.fee_inr, e.registration_url,
                           event_type=e.event_type),
            org.trust_level, now, listing.find_duplicate(db, e, e.id),
        )
        e.risk_score, e.risk_reasons, e.duplicate_of = a.score, a.reasons, a.duplicate_of
        events[item["key"]] = e

        pool = rng.sample(students, len(students))
        n_reg = min(item.get("seed_registrations", 0), len(pool))
        for u in pool[:n_reg]:
            db.add(Registration(user_id=u.id, event_id=e.id, status="registered",
                                registered_at=now - timedelta(days=rng.randint(0, 10))))
        for pos, u in enumerate(pool[n_reg:n_reg + item.get("seed_waitlist", 0)], start=1):
            db.add(Registration(user_id=u.id, event_id=e.id, status="waitlisted", waitlist_position=pos))

    db.commit()
    feedcache.invalidate_all()
    if samples_only:
        return {"users": len(orgs) + len(students), "events": len(events)}
    make_posters(today)
    make_timetables()
    return {"users": 1 + len(orgs) + 1 + len(students), "events": len(events)}


# Exactly the accounts load_samples creates. Anyone else on example.com (say, a tester's sign-up) isn't a sample.
SAMPLE_EMAILS = [dev_email(x) for x in ("club", "neworg", "design", "volunteers")] + [dev_email(f"student{i}") for i in range(1, 31)]


def has_samples(db: Session) -> bool:
    from sqlalchemy import select

    return db.scalar(select(User.id).where(User.email.in_(SAMPLE_EMAILS)).limit(1)) is not None


def load_samples() -> dict:
    """Add the sample clubs, students and events to any database (live too), without touching real data.
    Their accounts get a random password that is never shown, so nobody can sign in to them."""
    with SessionLocal() as db:
        if has_samples(db):
            raise SystemExit("Sample data is already loaded. Run remove_samples first to load it fresh.")
        return seed(db, secrets.token_urlsafe(32), samples_only=True)


def remove_samples() -> dict:
    """Delete every sample account and sample event (all on the reserved example.com domain). Real data stays."""
    from sqlalchemy import delete, select

    with SessionLocal() as db:
        users = select(User.id).where(User.email.in_(SAMPLE_EMAILS), User.role != "admin")
        orgs = select(Organizer.id).where(Organizer.user_id.in_(users))
        n_events = db.execute(delete(Event).where(Event.organizer_id.in_(orgs))).rowcount
        n_users = db.execute(delete(User).where(User.id.in_(users))).rowcount
        db.commit()
    feedcache.invalidate_all()
    return {"users": n_users, "events": n_events}


def dev_password() -> tuple[str, bool]:
    """(password, generated?) for the sample accounts."""
    pw = (os.environ.get("SEED_DEV_PASSWORD") or settings.seed_dev_password).strip()
    return (pw, False) if pw else (secrets.token_urlsafe(9), True)


def reset_and_seed(password: str | None = None) -> dict:
    """Wipe the local database and load sample data. Never runs in production."""
    if settings.is_production:
        raise SystemExit("Refusing to reset the database: APP_ENV=production.")
    from sqlalchemy import text

    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    if settings.app_env == "test":
        Base.metadata.create_all(engine)
    else:
        from ..migrate import upgrade

        upgrade()
    with SessionLocal() as db:
        return seed(db, password or dev_password()[0])
