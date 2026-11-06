"""AI topics make keyword matching understand meaning; feeds never wait on the AI."""

from types import SimpleNamespace
from unittest.mock import patch

from app.db import SessionLocal
from app.services import concepts, embeddings

STUDENT = "I like building robots and drones"
EVENT = SimpleNamespace(id="ev-iot", title="IoT hardware jam", description="Wire sensors to a microcontroller and stream readings.",
                        tags=["iot"])
ANSWERS = {STUDENT: {"topics": [{"tag": "robotics", "weight": 1}, {"tag": "iot", "weight": 0.6}, {"tag": "made-up", "weight": 1}]},
           concepts.event_text(EVENT): {"topics": [{"tag": "iot", "weight": 1}, {"tag": "robotics", "weight": 0.5}]}}


def _sim():
    embeddings._event_cache.clear()
    return embeddings.cosine(embeddings.text_vector([(STUDENT, 1.5)]), embeddings.event_vector(EVENT))


def test_meaning_closes_the_gap_once_topics_are_stored(client):
    concepts.reset()
    assert _sim() == 0  # no shared words
    with SessionLocal() as db, patch("app.services.llm.enabled", return_value=True), \
         patch("app.services.llm.chat_json", side_effect=lambda _s, text, **_: ANSWERS[text]):
        assert concepts.compute(db, STUDENT) == [("robotics", 1.0), ("iot", 0.6)]  # unknown tags dropped
        concepts.compute(db, concepts.event_text(EVENT))
    assert embeddings.calibrate(_sim()) >= 60  # interest score: 0 before, a solid match now
    concepts.reset()
    assert embeddings.calibrate(_sim()) >= 60  # read back from the database, not just memory


def test_lookups_never_call_the_ai(client):
    concepts.reset()
    with patch("app.services.llm.chat_json") as call:
        assert concepts.lookup(None, "Some brand new interest text nobody tagged yet") == []
        _sim()
    call.assert_not_called()


def test_background_warmup_without_a_key_does_nothing(client):
    with SessionLocal() as db, patch("app.services.llm.enabled", return_value=False):
        assert concepts.warm(db) == 0


def test_bad_answers_are_ignored(client):
    with SessionLocal() as db, patch("app.services.llm.enabled", return_value=True), \
         patch("app.services.llm.chat_json", return_value={"topics": "robotics"}):
        assert concepts.compute(db, "Robots and more robots please") is None
