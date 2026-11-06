"""Scam detection learns from admin decisions; it only ever adds to the risk score, with a reason."""

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Organizer
from app.services import listing, scam_model, spam
from app.timeutil import utcnow

NEW_SCAM = "Join our NFT airdrop club and claim free tokens; connect your wallet and verify with a small gas deposit"


def _reviewed(db, title, desc, status):
    org = db.scalar(select(Organizer).where(Organizer.slug == "quickcareers-hub"))
    start = utcnow() + timedelta(days=3)
    db.add(Event(organizer_id=org.id, title=title, description=desc, category_slug="careers", event_type="other", mode="online",
                 start_at=start, end_at=start + timedelta(hours=1), fee_inr=0, status=status, verification_label="unverified",
                 risk_score=50, reviewed_at=utcnow()))


def test_starter_examples_already_separate_obvious_cases(client):
    scam_model.reset_cache()
    with SessionLocal() as db:
        m = scam_model.model(db)
        assert m.p_scam("Guaranteed internship, pay Rs 499 registration fee to confirm")[0] > 0.9
        assert m.p_scam("Hands-on Python workshop by the CSE club, bring a laptop")[0] < 0.2


def test_learns_a_new_kind_of_scam_from_admin_rejections(client):
    scam_model.reset_cache()
    with SessionLocal() as db:
        before = scam_model.model(db).p_scam(NEW_SCAM)[0]
        for i in range(4):
            _reviewed(db, f"NFT airdrop {i}", "Claim free tokens, connect your wallet, verify with a small gas deposit", "blocked")
        _reviewed(db, "Blockchain basics talk", "Intro to how blockchains work, by the CSE department", "published")
        db.commit()
        after, words = scam_model.model(db).p_scam(NEW_SCAM)
    assert before < 0.65 <= 0.85 < after and words


def test_gate_adds_a_readable_reason_and_never_lowers_the_score(client):
    scam_model.reset_cache()
    with SessionLocal() as db:
        base = spam.Assessment(30, ["rule reason"], None)
        out = listing.learned_check(db, base, "Pay Rs 999 registration fee for guaranteed placement and offer letter")
        assert out.score == 55 and out.reasons[0] == "rule reason" and "rejected before" in out.reasons[-1]
        clean = listing.learned_check(db, base, "Weekend hackathon for local NGOs with mentors")
        assert clean.score == 30 and clean.reasons == ["rule reason"]


def test_ai_check_sees_recent_admin_decisions(client):
    with SessionLocal() as db:
        _reviewed(db, "Free crypto signals group", "Pay to join VIP", "blocked")
        db.commit()
        with patch("app.services.llm.enabled", return_value=True), \
             patch("app.services.llm.chat_json", return_value={"risk": "high", "reasons": ["Asks for payment"]}) as call:
            assert scam_model.ai_judge(db, "Join VIP signals, pay first") == ("high", ["Asks for payment"])
        prompt = call.call_args.args[1]
        assert "[rejected] Free crypto signals group" in prompt and "LISTING TO CHECK" in prompt
        with patch("app.services.llm.enabled", return_value=True), patch("app.services.llm.chat_json", return_value={"risk": "maybe"}):
            assert scam_model.ai_judge(db, "x") is None
