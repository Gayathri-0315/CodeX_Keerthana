"""Ranking (SPEC 5.3) and reason lines (5.4). Reasons are templates over facts that passed; never invented."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from ..timeutil import DAY_NAMES, fmt_range, to_ist
from . import embeddings
from .matching import FilterResult

TAG_LABELS = {
    "ai": "AI", "python": "Python", "web": "web development", "cybersecurity": "cybersecurity", "data": "data",
    "hackathons": "hackathons", "design": "design", "robotics": "robotics", "startups": "startups",
    "careers": "careers", "cloud": "cloud", "open-source": "open source", "public-speaking": "public speaking",
    "music": "music", "sports": "sports", "volunteering": "volunteering", "photography": "photography",
    "product": "product", "iot": "IoT", "mobile": "mobile apps", "gaming": "gaming", "writing": "writing",
    "quiz": "quizzing", "art": "art",
}
NOT_FOR_ME_FACTOR = 0.85
NOT_FOR_ME_FLOOR = 0.5
ALMOST_MIN_INTEREST = 40  # "interesting events that clash"


ANYWHERE_SCALE_KM = 50  # "Anywhere": score travel as if the limit were the slider's top step

def tag_label(tag: str) -> str:
    return TAG_LABELS.get(tag, tag.replace("-", " "))


@dataclass
class UserProfile:
    """Per-request matching context for one user."""

    vector: object
    weights: dict[str, int]
    not_for_me: Counter = field(default_factory=Counter)  # tag -> times the user said "not for me"


def build_profile(user, not_for_me_tags: Counter) -> UserProfile:
    weights = {i.tag: i.weight for i in user.interests}
    weighted = [(t, float(w)) for t, w in weights.items()]
    if user.interest_text:
        weighted.append((user.interest_text, 1.5))
    return UserProfile(embeddings.text_vector(weighted), weights, not_for_me_tags)


def interest_score(profile: UserProfile, event) -> tuple[float, list[str]]:
    cos = embeddings.cosine(profile.vector, embeddings.event_vector(event))
    score = embeddings.calibrate(cos)
    overlap = sorted((t for t in event.tags or [] if t in profile.weights), key=lambda t: -profile.weights[t])
    if overlap:
        score = min(100.0, score + 10)
    penalties = sum(profile.not_for_me[t] for t in event.tags or [])
    if penalties:
        score *= max(NOT_FOR_ME_FLOOR, NOT_FOR_ME_FACTOR**penalties)
    return score, overlap


def schedule_score(fr: FilterResult, event) -> tuple[float, float | None]:
    """100 with >= 30 min slack both sides inside the free window, down to 60 with none."""
    if fr.window is None or fr.need_start is None:
        return 40.0, None  # strict schedule off and it doesn't fit
    before = (fr.need_start - fr.window[0]).total_seconds() / 60
    after = (fr.window[1] - event.end_at).total_seconds() / 60
    slack = min(before, after)
    return (100.0 if slack >= 30 else 60 + 40 * max(0.0, slack) / 30), slack


def travel_score(fr: FilterResult, user) -> float:
    if fr.distance_km is None:
        return 100.0
    scale = user.max_distance_km or ANYWHERE_SCALE_KM
    return max(0.0, 100 - (fr.distance_km / scale) * 60)


def budget_score(event, user) -> float:
    if event.fee_inr == 0:
        return 100.0
    budget = user.budget_max_inr if user.budget_max_inr else 1000  # "Any": treat ₹1,000 as the scale
    return max(0.0, 100 - (event.fee_inr / budget) * 40)


def pref_score(event, user) -> float:
    skill = 50 if event.skill_level in (None, user.skill_level) else 0
    if user.format_pref == "either":
        fmt = 50
    else:
        fmt = 50 if event.mode in (user.format_pref, "hybrid") else 0
    return float(skill + fmt)


@dataclass
class Scored:
    match: int
    interest: int
    reasons: list[tuple[str, str]]  # (kind, text); kind is schedule | interest | travel | budget | eligibility
    slack_min: float | None

    @property
    def texts(self) -> list[str]:
        return [t for _, t in self.reasons]

    @property
    def card_texts(self) -> list[str]:
        """Cards already show distance and price as chips, so their reasons skip those."""
        return [t for k, t in self.reasons if k in ("schedule", "interest", "eligibility")][:3]


def _km(d: float) -> str:
    return "Under 1 km away" if d < 1 else f"{round(d)} km away"


def reasons_for(event, user, fr: FilterResult, overlap: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if fr.window is not None:
        ws, we = to_ist(fr.window[0]), to_ist(fr.window[1])
        day = DAY_NAMES[to_ist(event.start_at).weekday()]
        # Long windows (an all-day free day) read better without the range.
        if (fr.window[1] - fr.window[0]) >= timedelta(hours=12):
            out.append(("schedule", f"Fits your free {day}"))
        else:
            out.append(("schedule", f"Fits your {day} {fmt_range(ws, we)} gap"))
    if overlap:
        labels = [tag_label(t) for t in overlap[:2]]
        noun = "interests" if len(labels) > 1 else "interest"
        out.append(("interest", f"Matches your {noun} in {' and '.join(labels)}"))
    if fr.distance_km is not None:
        out.append(("travel", f"{_km(fr.distance_km)}, about {fr.travel_min} min"))
    elif event.mode == "online":
        out.append(("travel", "Online, join from anywhere"))
    elif event.mode == "hybrid":
        out.append(("travel", "Join in person or online"))
    if event.fee_inr == 0:
        out.append(("budget", "Free"))
    elif user.budget_max_inr:
        out.append(("budget", f"₹{event.fee_inr:,}, within your ₹{user.budget_max_inr:,} budget"))
    else:
        out.append(("budget", f"₹{event.fee_inr:,}"))
    elig = event.eligibility or {}
    if elig.get("required_tags"):
        out.append(("eligibility", f"You're eligible ({elig.get('text') or 'meets the requirements'})"))
    return out


def score_event(event, user, fr: FilterResult, profile: UserProfile) -> Scored:
    interest, overlap = interest_score(profile, event)
    schedule, slack = schedule_score(fr, event)
    match = (
        0.40 * interest
        + 0.25 * schedule
        + 0.15 * travel_score(fr, user)
        + 0.10 * budget_score(event, user)
        + 0.10 * pref_score(event, user)
    )
    return Scored(round(match), round(interest), reasons_for(event, user, fr, overlap), slack)
