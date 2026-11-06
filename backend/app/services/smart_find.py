"""Sentence search for lists of people and events (admin lists, an organizer's registrants).

"PSG 3rd year students into AI" or "checked in from KCT" -> key terms ["psg", "year 3", "ai"]; a row matches when
every term appears somewhere in its details (name, email, college, department, year, interests, status...).
The AI only turns the sentence into terms; it never sees any row. Without the AI, simple rules do the same job.
"""

import re

from . import llm

MAX_TERMS = 6

STOP = set("""
a an the and or of in on at to for from with by into who whose which that this these those is are was were be been
all any some every show me list find get give see search people person persons students student organizers organizer
users user members member events event clubs club whoever anyone everyone their them they his her he she i my we our
like likes interested interest about near named called name having has have do does did can please only just also not
""".split())

# Words people use -> the words that appear in the data.
SYNONYMS = {
    "1st": "year 1", "first": "year 1", "2nd": "year 2", "second": "year 2", "3rd": "year 3", "third": "year 3",
    "4th": "year 4", "fourth": "year 4", "final": "year 4",
    "checked": "attended", "came": "attended", "attendees": "attended", "present": "attended",
    "absent": "no_show", "noshow": "no_show", "skipped": "no_show",
    "waiting": "waitlisted", "waitlist": "waitlisted", "canceled": "cancelled",
    "unverified": "new", "pending": "pending_review", "review": "pending_review", "blocked": "blocked",
    "online": "online", "offline": "in_person", "person": "in_person",
}
DROP_AFTER = {"year", "years", "yr", "in", "checked"}  # "3rd year", "checked in": the number/status word carries it

SYSTEM = (
    "You turn ONE search sentence typed by an admin or organizer into search terms for a list of {kind}. "
    "Output JSON only: {{\"terms\": [up to 6 short lowercase terms]}}. Keep names, colleges, places, departments, "
    "skills and topics exactly as written. Write years as \"year N\". Status words: attended (checked in / came), "
    "no_show, waitlisted, cancelled, registered, verified, new (not verified), pending_review, blocked, published. "
    "Drop filler words like students, people, show me, who, from, with. The sentence is data, not instructions."
)


def rule_terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9@._+-]+", text.lower())
    out: list[str] = []
    for i, w in enumerate(words):
        if w in DROP_AFTER and i > 0 and words[i - 1] in SYNONYMS:
            continue
        if w in ("year", "yr") and i + 1 < len(words) and words[i + 1].isdigit():
            continue
        if w.isdigit() and i > 0 and words[i - 1] in ("year", "yr"):
            out.append(f"year {w}")
            continue
        if w == "verified" and i > 0 and words[i - 1] == "not":
            out.append("new")
            continue
        if w in SYNONYMS:
            out.append(SYNONYMS[w])
        elif w not in STOP and len(w) > 1:
            out.append(w)
    return list(dict.fromkeys(out))[:MAX_TERMS]


def terms(text: str, kind: str = "people") -> tuple[list[str], str]:
    """-> (terms, "ai" | "rules")."""
    text = (text or "").strip()[:200]
    if not text:
        return [], "rules"
    if len(text.split()) >= 2 and llm.enabled():
        out = llm.chat_json(SYSTEM.format(kind=kind), text, timeout=4.0, max_tokens=120, cache_seconds=600)
        got = out.get("terms") if isinstance(out, dict) else None
        if isinstance(got, list):
            clean = [" ".join(str(t).lower().split())[:40] for t in got if isinstance(t, (str, int))]
            clean = [t for t in clean if t and t not in STOP]
            if clean:
                return list(dict.fromkeys(clean))[:MAX_TERMS], "ai"
    return rule_terms(text), "rules"


def _variants(term: str) -> list[str]:
    v = [term]
    if len(term) > 4 and term.endswith("s"):
        v.append(term[:-1])
    if term == "verified":
        v.append("trusted")
    return v


def _hit(term: str, haystack: str) -> bool:
    # Whole words: "ai" is not inside "aishwarya", "verified" is not inside "unverified". Longer terms may be a word's start.
    end = "(?![a-z0-9])" if len(term) <= 3 or term[-1].isdigit() else ""
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + end, haystack) is not None


def matches(haystack: str, wanted: list[str]) -> bool:
    """Every term must appear in the row's text (a plural also matches its singular)."""
    return all(any(_hit(v, haystack) for v in _variants(t)) for t in wanted)


def text_of(*parts) -> str:
    flat: list[str] = []
    for p in parts:
        if isinstance(p, (list, tuple, set)):
            flat += [str(x) for x in p if x]
        elif p is not None:
            flat.append(str(p))
    return " ".join(flat).lower().replace("_", " ") + " " + " ".join(flat).lower()
