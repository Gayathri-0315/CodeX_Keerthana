import time
from collections import Counter
from datetime import date, timedelta
from types import SimpleNamespace

from app.services.matching import check_event
from app.services.ranking import build_profile, interest_score, score_event
from app.tests.test_filters import NOW, SAT, SAT_AFTERNOON, event, user


def student(**kw):
    u = user(skill_level="beginner", interest_text="", **kw)
    u.interests = [SimpleNamespace(tag="ai", weight=3), SimpleNamespace(tag="python", weight=2)]
    return u


def ev(eid, title, tags, start="15:00", end="17:00", **kw):
    return event(start, end, id=eid, title=title, description="", tags=tags, skill_level=None, **kw)


def rank(u, events, windows=SAT_AFTERNOON, nfm=None):
    profile = build_profile(u, nfm or Counter())
    out = []
    for e in events:
        fr = check_event(u, e, windows, NOW)
        if fr.passed:
            out.append((score_event(e, u, fr, profile).match, e.start_at, e.id))
    return [eid for *_, eid in sorted(out, key=lambda x: (-x[0], x[1]))]


def test_ranking_is_stable_and_deterministic():
    events = [
        ev("music", "Indie gig", ["music"]),
        ev("ai", "LLM workshop", ["ai", "python"]),
        ev("py", "Python meetup", ["python"], "16:00", "17:00"),
        ev("tie", "LLM workshop", ["ai", "python"]),  # identical to "ai": tie broken by start, then input order
    ]
    first = rank(student(), events)
    assert first[:2] == ["ai", "tie"] and first[-1] == "music"
    assert all(rank(student(), events) == first for _ in range(5))


def test_reasons_are_facts_that_passed():
    u = student()
    e = ev("ai", "LLM workshop", ["ai", "python"])
    fr = check_event(u, e, SAT_AFTERNOON, NOW)
    s = score_event(e, u, fr, build_profile(u, Counter()))
    assert s.reasons[0] == "Fits your Saturday 2 to 6 PM gap"
    assert s.reasons[1] == "Matches your interests in AI and Python"
    assert s.reasons[2].endswith("min") and "km away" in s.reasons[2]
    assert s.reasons[3] == "₹100, within your ₹200 budget"


def test_no_interest_reason_without_overlap():
    u = student()
    e = ev("music", "Indie gig", ["music"], fee_inr=0)
    fr = check_event(u, e, SAT_AFTERNOON, NOW)
    reasons = score_event(e, u, fr, build_profile(u, Counter())).reasons
    assert not any(r.startswith("Matches") for r in reasons) and "Free" in reasons


def test_schedule_slack_scales_score():
    u = student()
    roomy = ev("a", "LLM workshop", ["ai"], "15:00", "16:00")
    tight = ev("b", "LLM workshop", ["ai"], "15:00", "18:00")  # ends exactly when free time ends
    p = build_profile(u, Counter())
    s_roomy = score_event(roomy, u, check_event(u, roomy, SAT_AFTERNOON, NOW), p)
    s_tight = score_event(tight, u, check_event(u, tight, SAT_AFTERNOON, NOW), p)
    assert s_roomy.slack_min >= 30 and s_tight.slack_min == 0 and s_roomy.match > s_tight.match


def test_not_for_me_penalty_with_floor():
    u = student()
    e = ev("ai", "LLM workshop", ["ai", "python"])
    base, _ = interest_score(build_profile(u, Counter()), e)
    once, _ = interest_score(build_profile(u, Counter({"ai": 1})), e)
    many, _ = interest_score(build_profile(u, Counter({"ai": 20})), e)
    assert round(once, 6) == round(base * 0.85, 6)
    assert round(many, 6) == round(base * 0.5, 6)


def test_feed_for_500_events_under_50ms():
    u = student()
    events = [
        ev(f"e{i}", f"Event {i} about {'AI' if i % 3 else 'music'}", ["ai"] if i % 3 else ["music"],
           d=SAT + timedelta(days=7 * (i % 4)), lat=11.0 + (i % 10) * 0.01, lng=76.95 + (i % 7) * 0.01)
        for i in range(500)
    ]
    rank(student(), events[:5])  # warm caches the way a running server would be
    t = time.perf_counter()
    rank(u, events)
    assert (time.perf_counter() - t) * 1000 < 50
