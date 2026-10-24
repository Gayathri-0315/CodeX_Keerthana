from datetime import datetime, timedelta

import pytest

from app.services import spam

NOW = datetime(2026, 10, 26, 6, 0)
START = NOW + timedelta(days=5)


def cand(**kw):
    base = dict(title="Python Meetup", description="Two short talks and Q&A.", category="Meetup", mode="in_person",
                venue_name="Thinkspace", start_at=START, end_at=START + timedelta(hours=2), fee_inr=0, registration_url=None)
    base.update(kw)
    return spam.Candidate(**base)


def score(c, trust=None, duplicate=None):
    return spam.assess(c, trust, NOW, duplicate)


def test_clean_event_scores_zero():
    a = score(cand())
    assert a.score == 0 and a.reasons == [] and a.level == "low"


@pytest.mark.parametrize("phrase", spam.SCAM_PHRASES)
def test_each_scam_phrase_adds_35(phrase):
    a = score(cand(description=f"Join us. {phrase.upper()} for everyone."))
    assert a.score >= 35 and any(phrase in r for r in a.reasons)


def test_missing_fields():
    a = score(cand(start_at=None, end_at=None, venue_name=None))
    assert a.score == 50 and "Missing date or time" in a.reasons and "Missing venue for an in-person event" in a.reasons
    assert score(cand(mode="online", venue_name=None)).score == 0


def test_past_date_and_end_before_start():
    assert score(cand(start_at=NOW - timedelta(days=1), end_at=NOW)).reasons == ["Start date is in the past"]
    assert score(cand(end_at=START - timedelta(hours=1))).reasons == ["Ends before it starts"]


def test_personal_payment():
    assert "Asks for payment to a personal UPI ID" in score(cand(description="Pay to quickjobs@okaxis")).reasons
    assert "Asks for payment to a personal phone number" in score(cand(description="Pay the fee on GPay to 98765 43210")).reasons
    assert "Asks for payment by QR code" in score(cand(description="Scan the QR to pay the entry fee")).reasons
    # A phone number alone, without payment words, is just contact info.
    assert score(cand(description="Questions? Call 98765 43210")).score == 0


def test_shortener_and_lookalike_links():
    assert score(cand(registration_url="https://bit.ly/x")).reasons == ["Registration link uses a URL shortener"]
    assert score(cand(registration_url="https://docs-google.forms.example/x")).score == 20
    assert score(cand(registration_url="https://forms.gle/abc")).score == 0


def test_fee_outlier():
    assert score(cand(category="Workshop", fee_inr=2500)).score == 15
    assert score(cand(category="Workshop", fee_inr=2000)).score == 0


def test_duplicate():
    a = score(cand(), duplicate=("e1", "Python Meetup"))
    assert a.score == 30 and a.duplicate_of == "e1"


def test_caps_and_urgency():
    assert score(cand(title="FREE WORKSHOP FOR EVERYONE THIS WEEK")).score == 10
    assert score(cand(description="Hurry, act now!!!")).score == 10


def test_trust_levels_adjust():
    bad = cand(registration_url="https://bit.ly/x", fee_inr=2500, category="Workshop")  # 35
    assert score(bad, "new").score == 45
    assert score(bad, "verified").score == 25
    assert score(bad, "trusted").score == 10
    assert score(cand(), "trusted").score == 0  # never below zero


def test_fake_internship_is_high_even_for_trusted():
    a = score(cand(title="GUARANTEED INTERNSHIP AT TOP MNC", category="Careers", fee_inr=500,
                   description="Guaranteed internship! Limited seats pay now. Send Rs 500 registration fee to personal UPI quickjobs@okaxis",
                   registration_url="https://bit.ly/mnc"), "trusted")
    assert a.level == "high"


@pytest.mark.parametrize("value,expected", [
    (29, ("published", "organizer_verified")),
    (30, ("published", "unverified")),
    (59, ("published", "unverified")),
    (60, ("blocked", "unverified")),
])
def test_outcome_thresholds(value, expected):
    assert spam.outcome(value, "verified", "psgtech.ac.in", is_first_event=False) == expected


def test_outcome_labels_never_overclaim():
    assert spam.outcome(10, "new", "gmail.com", is_first_event=False) == ("published", "details_reviewed")


def test_new_organizer_first_event_goes_to_review():
    assert spam.outcome(10, "new", "gmail.com", True) == ("pending_review", "unverified")
    assert spam.outcome(45, "new", "kct.ac.in", True) == ("pending_review", "unverified")
    # Low risk from a college domain skips review.
    assert spam.outcome(10, "new", "kct.ac.in", True) == ("published", "details_reviewed")


def test_llm_combination():
    a = spam.Assessment(40, ["x"])
    assert spam.combine_llm(a, "high", ["Pressure to pay"]).score == 55
    assert spam.combine_llm(a, "low", []).score == 25
    assert spam.combine_llm(a, None, []).score == 40
