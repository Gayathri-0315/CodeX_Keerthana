"""Event types (prompt v2, item 12) and the stricter trust gate for internships."""

import re
from urllib.parse import urlparse

TYPES = ["hackathon", "competition", "internship", "workshop", "conference", "meetup", "webinar", "other"]

# Words in a title, the poster's category text or tags -> type. First match wins.
_WORDS = [
    ("internship", ("internship", "internships", "intern", "apprenticeship")),
    ("hackathon", ("hackathon", "hackathons", "hack", "buildathon", "ideathon")),
    ("competition", ("competition", "contest", "challenge", "quiz", "cup", "tournament", "olympiad", "ctf")),
    ("conference", ("conference", "summit", "symposium", "conclave")),
    ("webinar", ("webinar", "online session", "live session", "livestream")),
    ("workshop", ("workshop", "bootcamp", "masterclass", "hands-on", "training", "study jam", "sprint")),
    ("meetup", ("meetup", "meet-up", "circle", "night", "evening", "walk", "drive", "community")),
]


def suggest(*texts: str) -> str:
    low = " ".join(t or "" for t in texts).lower()
    for kind, words in _WORDS:
        if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
            return kind
    return "other"


# ---- internships: a stricter gate, because fake internships are a common scam ----

PAY_REQUEST = re.compile(
    r"\b(registration|application|processing|security|training|joining|onboarding|certificate|enrol?ment)\s+(fee|fees|charge|charges|deposit)\b"
    r"|\b(pay|paying|payment|deposit|refundable)\b",
    re.I,
)


def internship_blocks(title: str, description: str, fee_inr: int, apply_url: str | None) -> list[str]:
    """Reasons an internship can't be published at all. Empty list = it may go on to review or publish."""
    from .spam import LOOKALIKE, SHORTENERS

    reasons = []
    if fee_inr > 0:
        reasons.append("Internships can't charge applicants a fee")
    if PAY_REQUEST.search(f"{title}\n{description}"):
        reasons.append("Internships can't ask applicants for any payment")
    host = (urlparse(apply_url or "").hostname or "").removeprefix("www.")
    if apply_url and (host in SHORTENERS or LOOKALIKE.search(host)):
        reasons.append("The apply link must be the organization's own website, not a short or look-alike link")
    return reasons
