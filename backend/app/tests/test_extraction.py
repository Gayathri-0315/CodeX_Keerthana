import json
from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services import extraction
from app.services.extraction import ExtractionFailed, PosterExtraction


def test_schema_rejects_bad_formats():
    with pytest.raises(ValidationError):
        PosterExtraction(date="31/10/2026")
    with pytest.raises(ValidationError):
        PosterExtraction(start_time="3 PM")
    with pytest.raises(ValidationError):
        PosterExtraction(fee_inr=-5)
    ok = PosterExtraction(date="2026-10-31", start_time="15:30", fee_inr=0)
    assert ok.mode is None and ok.field_confidence.title is None


def test_low_confidence_flags_missing_and_unsure_fields():
    fields = PosterExtraction(title="AI Workshop", date="2026-10-31", field_confidence={"title": 0.95, "date": 0.5}).model_dump()
    flagged = extraction.low_confidence(fields)
    assert "date" in flagged and "venue_name" in flagged and "title" not in flagged


def test_mock_poster_resolves_relative_dates():
    spec = json.loads((extraction.SEED_DIR / "posters" / "ai_workshop.json").read_text(encoding="utf-8"))
    out = extraction.resolve_mock_poster(spec, date(2026, 10, 25))  # a Sunday
    assert out["date"] == "2026-10-31" and out["registration_deadline"] == "2026-10-30" and "poster" not in out
    PosterExtraction.model_validate(out)


class FakeMessages:
    """Stands in for client.messages; each queued item is returned or raised in order."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def parse(self, **kw):
        self.calls.append(kw)
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def response(parsed=None, text="", stop="end_turn"):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop, content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture()
def fake_client(monkeypatch):
    def install(results):
        messages = FakeMessages(results)
        monkeypatch.setattr(extraction, "_client", lambda: SimpleNamespace(messages=messages))
        return messages

    return install


def validation_error():
    try:
        PosterExtraction(date="nope")
    except ValidationError as e:
        return e


def test_retry_once_with_the_validation_error(fake_client):
    good = PosterExtraction(title="AI Workshop")
    messages = fake_client([validation_error(), response(good)])
    assert extraction.call_model([], "prompt", PosterExtraction) is good
    assert len(messages.calls) == 2
    retry_text = messages.calls[1]["messages"][0]["content"][-1]["text"]
    assert "did not validate" in retry_text and "date" in retry_text


def test_second_failure_returns_partial_fields(fake_client):
    bad_json = json.dumps({"title": "AI Workshop", "date": "31 Oct", "fee_inr": 100})
    fake_client([response(None, bad_json), response(None, bad_json)])
    with pytest.raises(ExtractionFailed) as e:
        extraction.call_model([], "prompt", PosterExtraction)
    assert e.value.partial == {"title": "AI Workshop", "fee_inr": 100}


def test_refusal_is_a_friendly_failure(fake_client):
    fake_client([response(None, "", stop="refusal")])
    with pytest.raises(ExtractionFailed, match="declined"):
        extraction.call_model([], "prompt", PosterExtraction)
