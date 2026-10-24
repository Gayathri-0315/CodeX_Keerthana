"""Interest similarity (SPEC 5.3).

Uses sentence-transformers (all-MiniLM-L6-v2) when it is installed, loaded in a background thread
so no request waits on it. Until then, or if it's missing, a keyword + synonym model is used.
Both backends expose the same calls; calibration differs because their cosine ranges differ.
"""

import logging
import math
import re
import threading
from collections import Counter

log = logging.getLogger("showup.embeddings")

# ---- keyword fallback ----

PHRASES = {
    "machine learning": "ai", "deep learning": "ai", "artificial intelligence": "ai", "data science": "data",
    "open source": "open-source", "public speaking": "public-speaking", "capture the flag": "cybersecurity",
    "full stack": "web", "full-stack": "web", "ui/ux": "design", "user experience": "design",
    "mobile app": "mobile", "line following": "robotics",
}
SYNONYMS = {
    "ml": "ai", "llm": "ai", "llms": "ai", "chatbot": "ai", "gpt": "ai", "nlp": "ai", "genai": "ai", "neural": "ai",
    "hackathon": "hackathons", "hack": "hackathons", "hackathons": "hackathons", "ship": "hackathons",
    "pandas": "python", "fastapi": "python", "django": "python", "flask": "python", "jupyter": "python",
    "react": "web", "javascript": "web", "frontend": "web", "backend": "web", "website": "web", "coding": "web",
    "ctf": "cybersecurity", "security": "cybersecurity", "hacking": "cybersecurity", "crypto": "cybersecurity",
    "figma": "design", "ux": "design", "ui": "design", "prototype": "design",
    "robot": "robotics", "robots": "robotics", "arduino": "iot", "microcontroller": "iot", "sensors": "iot",
    "founder": "startups", "founders": "startups", "pitch": "startups", "investors": "startups", "startup": "startups",
    "interview": "careers", "interviews": "careers", "placement": "careers", "resume": "careers", "internship": "careers", "jobs": "careers",
    "aws": "cloud", "gcp": "cloud", "azure": "cloud", "deploy": "cloud", "deploying": "cloud",
    "github": "open-source", "git": "open-source", "maintainers": "open-source", "pr": "open-source",
    "csv": "data", "charts": "data", "analytics": "data", "visualization": "data", "viz": "data",
    "band": "music", "bands": "music", "concert": "music", "gig": "music",
    "football": "sports", "cricket": "sports", "tournament": "sports",
    "cleanup": "volunteering", "clean-up": "volunteering", "volunteer": "volunteering", "ngo": "volunteering",
    "photo": "photography", "photos": "photography", "camera": "photography",
    "speech": "public-speaking", "speeches": "public-speaking", "toastmasters": "public-speaking",
    "app": "mobile", "flutter": "mobile", "android": "mobile", "ios": "mobile",
}
STOP = set(
    "a an and are as at be by for from in into is it its of on or our the this to we with you your yours "
    "bring us one two three four five per all any can will just get go out up more most new show".split()
)
WORD = re.compile(r"[a-z0-9][a-z0-9+#/-]*")


def _tokens(text: str) -> list[str]:
    text = text.lower()
    found = [concept for phrase, concept in PHRASES.items() if phrase in text]
    for w in WORD.findall(text):
        if w in STOP or len(w) < 2:
            continue
        found.append(SYNONYMS.get(w, w))
    return found


def _sparse(weighted: list[tuple[str, float]]) -> dict[str, float]:
    vec: Counter = Counter()
    for text, weight in weighted:
        for t in _tokens(text):
            vec[t] += weight
    return dict(vec)


def _sparse_cos(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


# ---- optional sentence-transformers model ----

_model = None
_model_lock = threading.Lock()
_loading = False


def start_background_load() -> None:
    global _loading
    if _loading or _model is not None:
        return
    _loading = True

    def load():
        global _model
        try:
            from sentence_transformers import SentenceTransformer  # optional dependency

            m = SentenceTransformer("all-MiniLM-L6-v2")
            with _model_lock:
                _model = m
            _event_cache.clear()
            log.info("Embedding model ready")
        except Exception as e:  # missing package, no network, etc.
            log.info("Using keyword matching (embedding model unavailable: %s)", e.__class__.__name__)

    threading.Thread(target=load, name="embeddings-load", daemon=True).start()


def backend() -> str:
    return "model" if _model is not None else "keywords"


# Calibration: cosine -> 0..100. The model range is from the spec; the keyword range is tuned
# so a strong tag overlap reads as a strong match.
CALIBRATION = {"model": (0.20, 0.70), "keywords": (0.05, 0.55)}


def calibrate(cos: float) -> float:
    lo, hi = CALIBRATION[backend()]
    return max(0.0, min(1.0, (cos - lo) / (hi - lo))) * 100


def _encode(texts: list[str]):
    with _model_lock:
        return _model.encode(texts, normalize_embeddings=True)


_event_cache: dict[str, object] = {}


def event_text(event) -> list[tuple[str, float]]:
    return [(" ".join(event.tags or []), 2.0), (event.title or "", 1.5), (event.description or "", 1.0)]


def event_vector(event):
    key = f"{event.id}:{backend()}:{event.title}:{len(event.description or '')}"
    hit = _event_cache.get(key)
    if hit is not None:
        return hit
    if _model is not None:
        vec = _encode([f"{event.title}. {event.description} Tags: {', '.join(event.tags or [])}"])[0]
    else:
        vec = _sparse(event_text(event))
    _event_cache[key] = vec
    return vec


def text_vector(weighted: list[tuple[str, float]]):
    """A vector for arbitrary weighted text, e.g. a user's interests."""
    if _model is not None:
        texts = [t for t, _ in weighted if t.strip()]
        if not texts:
            return None
        weights = [w for t, w in weighted if t.strip()]
        vecs = _encode(texts)
        avg = sum(v * w for v, w in zip(vecs, weights)) / sum(weights)
        norm = float((avg @ avg) ** 0.5)
        return avg / norm if norm else None
    return _sparse(weighted)


def cosine(a, b) -> float:
    if a is None or b is None:
        return 0.0
    if isinstance(a, dict) or isinstance(b, dict):
        if not (isinstance(a, dict) and isinstance(b, dict)):
            return 0.0  # vectors from different backends (model finished loading mid-request)
        return _sparse_cos(a, b)
    return float(a @ b)


def invalidate_event(event_id: str) -> None:
    for k in [k for k in _event_cache if k.startswith(f"{event_id}:")]:
        _event_cache.pop(k, None)
