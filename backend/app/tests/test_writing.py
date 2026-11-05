"""Writing help for organizers: suggestions only, and the AI may not add facts."""

from unittest.mock import patch

from app.services import writing

from .conftest import login

DESC = "JOIN US FOR A HANDS-ON MACHINE LEARNING WORKSHOP!!!   bring your laptop.\n\n\nentry fee rs 100. register at https://club.example.org/ml"


def test_rules_tidy_and_suggest(client):
    login(client, "organizer")
    r = client.post("/api/organizer/writing-help", json={"title": "ML workshop", "description": DESC}).json()
    assert r["source"] == "rules" and r["event_type"] == "workshop" and r["category"] == "ai-ml" and "ai" in r["tags"]
    assert "!!!" not in r["description"] and "\n\n\n" not in r["description"]
    assert "rs 100" in r["description"].lower() and "https://club.example.org/ml" in r["description"]


def test_only_organizers(client):
    assert client.post("/api/organizer/writing-help", json={"title": "x", "description": DESC}).status_code == 401
    login(client, "student")
    assert client.post("/api/organizer/writing-help", json={"title": "x", "description": DESC}).status_code == 403


def test_ai_suggestion_used_when_it_keeps_the_facts(client):
    good = {"description": "A hands-on machine learning workshop. Bring your laptop. Entry fee: Rs 100. Register at https://club.example.org/ml",
            "title": "Hands-on ML Workshop", "event_type": "workshop", "category": "ai-ml", "tags": ["ai", "python", "made-up"]}
    with patch.object(writing.llm, "chat_json", return_value=good):
        r = writing.suggest("ML workshop", DESC)
    assert r["source"] == "ai" and r["description"] == good["description"] and r["title"] == "Hands-on ML Workshop"
    assert r["tags"] == ["ai", "python"]


def test_ai_rewrite_that_invents_facts_is_rejected():
    bad = {"description": "Machine learning workshop on 12 Dec. Fee Rs 100, prizes worth 50000! https://evil.example.com",
           "title": "ML Workshop with 50000 prizes", "event_type": "party", "category": "nope", "tags": "ai"}
    with patch.object(writing.llm, "chat_json", return_value=bad):
        r = writing.suggest("ML workshop", DESC)
    assert "50000" not in r["description"] and "evil" not in r["description"] and r["title"] is None
    assert r["event_type"] == "workshop" and r["category"] == "ai-ml" and r["tags"]
