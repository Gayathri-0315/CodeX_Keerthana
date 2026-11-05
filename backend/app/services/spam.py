"""Spam and trust gate (SPEC 5.6). Rule-based score 0..100 with human-readable reasons."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

SCAM_PHRASES = [
    "guaranteed job", "guaranteed internship", "100% placement", "earn per day", "limited seats pay now",
    "registration fee to personal upi", "send money", "lottery", "mlm",
]
SHORTENERS = {"bit.ly", "tinyurl.com", "goo.gl", "t.ly", "cutt.ly", "rb.gy", "is.gd", "shorturl.at", "ow.ly", "tiny.cc", "s.id"}
LOOKALIKE = re.compile(r"g[o0]{2}g[l1I]e|forms-google|docs-google|go0gle|micr0soft|paytm-|upi-pay", re.I)
UPI_ID = re.compile(r"\b[\w.-]{2,}@(ok\w+|ybl|ibl|axl|paytm|upi|apl|sbi|icici|hdfcbank|freecharge)\b", re.I)
PHONE = re.compile(r"(?:\+91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b")
PAY_WORDS = re.compile(r"\b(pay|paid|payment|fee|send|transfer|upi|gpay|phonepe|scan)\b", re.I)
QR_PAY = re.compile(r"\b(scan|qr)\b.{0,40}\b(pay|fee|upi)\b|\b(pay|fee|upi)\b.{0,40}\b(scan|qr)\b", re.I)
URGENCY = re.compile(r"\b(hurry|last chance|act now|urgent|limited seats|only today)\b|!{3,}", re.I)
COLLEGE_DOMAIN = re.compile(r"(\.ac\.in|\.edu|\.edu\.in)$", re.I)

# Fees above these (₹) are "far outside the norm" for the category.
FEE_NORMS = {"workshop": 2000, "meetup": 500, "talk": 500, "webinar": 500, "hackathon": 1000, "conference": 3000,
             "competition": 1000, "internship": 0}
DEFAULT_FEE_NORM = 3000

LOW, HIGH = 30, 60


@dataclass
class Assessment:
    score: int
    reasons: list[str] = field(default_factory=list)
    duplicate_of: str | None = None

    @property
    def level(self) -> str:
        return "low" if self.score < LOW else "medium" if self.score < HIGH else "high"


@dataclass
class Candidate:
    """The event fields the gate looks at, from a saved Event or an unsaved form."""

    title: str
    description: str
    category: str
    mode: str
    venue_name: str | None
    start_at: datetime | None
    end_at: datetime | None
    fee_inr: int
    registration_url: str | None
    has_organizer: bool = True
    event_type: str = "other"


def _caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 20:
        return 0.0
    return sum(c.isupper() for c in letters) / len(letters)


def assess(c: Candidate, trust_level: str | None, now: datetime, duplicate: tuple[str, str] | None = None) -> Assessment:
    """`duplicate` is (event_id, title) of a near-identical event on the same date, found by the caller."""
    pts = 0
    reasons: list[str] = []
    text = f"{c.title}\n{c.description}"
    low = text.lower()

    def add(points: int, reason: str):
        nonlocal pts
        pts += points
        reasons.append(reason)

    internship = c.event_type == "internship"
    if c.start_at is None:
        add(25, "Missing apply-by date" if internship else "Missing date or time")
    if c.mode == "in_person" and not internship and not (c.venue_name or "").strip():
        add(25, "Missing venue for an in-person event")
    if not c.has_organizer:
        add(25, "Missing organizer")

    if c.start_at is not None and c.start_at < now:
        add(40, "Apply-by date is in the past" if internship else "Start date is in the past")
    elif not internship and c.start_at is not None and c.end_at is not None and c.end_at <= c.start_at:
        add(40, "Ends before it starts")

    for phrase in SCAM_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", low):
            add(35, f'Says "{phrase}"')

    if UPI_ID.search(text):
        add(40, "Asks for payment to a personal UPI ID")
    elif PHONE.search(text) and PAY_WORDS.search(text):
        add(40, "Asks for payment to a personal phone number")
    elif QR_PAY.search(text):
        add(40, "Asks for payment by QR code")

    urls = [c.registration_url or ""] + re.findall(r"https?://\S+", text)
    hosts = {urlparse(u).hostname or "" for u in urls if u}
    if any(h.removeprefix("www.") in SHORTENERS for h in hosts):
        add(20, "Registration link uses a URL shortener")
    elif any(LOOKALIKE.search(h) for h in hosts):
        add(20, "Registration link looks like an imitation of a known site")

    kind = c.event_type if c.event_type in FEE_NORMS else (c.category or "").lower()
    norm = FEE_NORMS.get(kind, DEFAULT_FEE_NORM)
    if c.fee_inr > norm:
        add(15, f"Fee of ₹{c.fee_inr:,} is unusually high for a {kind or 'event'}")

    duplicate_of = None
    if duplicate:
        duplicate_of = duplicate[0]
        add(30, f'Looks like a copy of "{duplicate[1]}" on the same date')

    if _caps_ratio(text) > 0.4 or len(URGENCY.findall(text)) >= 2:
        add(10, "Pushy wording or mostly capital letters")

    if trust_level == "new":
        add(10, "New organizer")
    elif trust_level == "verified":
        pts -= 10
    elif trust_level == "trusted":
        pts -= 25

    return Assessment(max(0, min(100, pts)), reasons, duplicate_of)


def combine_llm(a: Assessment, llm_risk: str | None, llm_reasons: list[str]) -> Assessment:
    """Optional LLM judgement nudges the rule score by up to 15 points and adds its reasons."""
    if llm_risk is None:
        return a
    delta = {"low": -15, "medium": 0, "high": 15}.get(llm_risk, 0)
    return Assessment(max(0, min(100, a.score + delta)), a.reasons + [f"Review: {r}" for r in llm_reasons[:3]], a.duplicate_of)


def outcome(score: int, trust_level: str, email_domain: str, is_first_event: bool, event_type: str = "other",
            hard_blocks: list[str] | None = None) -> tuple[str, str]:
    """(status, verification_label) for publishing. Labels never claim a check that didn't happen."""
    if score >= HIGH or hard_blocks:
        return "blocked", "unverified"
    if event_type == "internship":
        # Only verified organizers publish internships directly; every new organizer's internship is reviewed.
        if trust_level == "new":
            return "pending_review", "unverified"
        return ("published", "organizer_verified") if score < LOW else ("pending_review", "unverified")
    if is_first_event and trust_level == "new" and not (score < LOW and COLLEGE_DOMAIN.search(email_domain or "")):
        return "pending_review", "unverified"
    if score >= LOW:
        return "published", "unverified"
    return "published", "organizer_verified" if trust_level in ("verified", "trusted") else "details_reviewed"
