"""Demo data (SPEC section 12). Run: `npm run seed` (or `python -m app.seed.seed` in backend/)."""

import json
import random
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from ..db import Base, SessionLocal, engine
from ..models import AvailabilitySlot, Event, Organizer, Registration, User, UserInterest
from ..security import hash_password
from ..services import feedcache, listing, spam
from ..timeutil import ist_to_utc, ist_today, utcnow
from .make_samples import make_posters, make_timetables
from .venues import AREAS, find_area

SEED_DIR = Path(__file__).parent
DEMO_PASSWORD = "demo1234"
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


def seed(db: Session) -> dict:
    rng = random.Random(42)
    pw = hash_password(DEMO_PASSWORD)
    today = ist_today()
    now = utcnow()

    # ---- demo student ----
    home = find_area("Gandhipuram")
    student = make_user(
        "student@demo.app", "Asha", pw,
        home_area=home["name"], home_lat=home["lat"], home_lng=home["lng"],
        max_distance_km=20, budget_max_inr=200, skill_level="beginner",
        eligibility_tags=["college_student", "it_dept", "year_3"],
        interest_text="Machine learning, building with Python, weekend hackathons",
    )
    student.interests = [UserInterest(tag="ai", weight=3), UserInterest(tag="python", weight=2), UserInterest(tag="hackathons", weight=2)]
    db.add(student)
    db.flush()
    db.add_all([slot(student.id, 5, "14:00", "18:00"), slot(student.id, 6, "09:00", "13:00")])

    # ---- organizers + admin ----
    def organizer(email, name, org_name, domain, trust, past=0, rate=None):
        u = make_user(email, name, pw, role="organizer")
        db.add(u)
        db.flush()
        o = Organizer(user_id=u.id, org_name=org_name, org_email_domain=domain, trust_level=trust,
                      past_events_count=past, avg_attendance_rate=rate)
        db.add(o)
        db.flush()
        return o

    orgs = {
        "club": organizer("organizer@demo.app", "Club lead", "Coimbatore AI Club", "kct.ac.in", "trusted", 9, 0.78),
        "new": organizer("neworg@demo.app", "Quick Careers", "QuickCareers Hub", "gmail.com", "new"),
        "design": organizer("design@demo.app", "Design lead", "PSG Design Society", "psgtech.ac.in", "verified", 2, 0.71),
        "volunteers": organizer("volunteers@demo.app", "Volunteer lead", "Kovai Volunteers", "kovaivolunteers.org", "verified", 4, 0.66),
    }
    db.add(make_user("admin@demo.app", "Admin", pw, role="admin"))

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
            f"student{i + 1}@demo.app", f"{FIRST[i]} {rng.choice(LAST)}.", pw,
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
        clean_label = "organizer_verified" if org.trust_level in ("verified", "trusted") else "details_reviewed"
        status = item.get("status", "published")
        e = Event(
            organizer_id=org.id, title=item["title"], description=item["description"], category=item["category"],
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
            spam.Candidate(e.title, e.description, e.category, e.mode, e.venue_name, e.start_at, e.end_at, e.fee_inr, e.registration_url),
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
    make_posters(today)
    make_timetables()
    return {"users": 1 + len(orgs) + 1 + len(students), "events": len(events)}


def reset_and_seed() -> dict:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        return seed(db)


if __name__ == "__main__":
    result = reset_and_seed()
    print(f"Seeded {result['users']} users and {result['events']} events. Demo password: {DEMO_PASSWORD}")
