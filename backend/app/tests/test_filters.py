from datetime import date, timedelta
from types import SimpleNamespace

from app.services.matching import check_event
from app.services.scheduling import free_windows
from app.services.travel import haversine_km, travel_minutes
from app.timeutil import ist_to_utc

SAT = date(2026, 10, 31)
NOW = ist_to_utc(date(2026, 10, 26), 600)
HOME = (11.0168, 76.9675)


def user(**kw):
    base = dict(eligibility_tags=["college_student"], format_pref="either", budget_max_inr=200,
                max_distance_km=20, home_lat=HOME[0], home_lng=HOME[1], strict_schedule=True)
    base.update(kw)
    return SimpleNamespace(**base)


def event(start="15:00", end="17:00", d=SAT, **kw):
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    base = dict(status="published", start_at=ist_to_utc(d, h1 * 60 + m1), end_at=ist_to_utc(d, h2 * 60 + m2),
                registration_deadline=None, eligibility={}, mode="in_person", fee_inr=100,
                lat=11.0250, lng=77.0120, capacity=None)
    base.update(kw)
    return SimpleNamespace(**base)


def windows(*ranges):
    slots = [SimpleNamespace(day_of_week=SAT.weekday(), start_min=s, end_min=e, recurring=True, date=None, kind="free")
             for s, e in ranges]
    return free_windows(slots, SAT - timedelta(days=1), SAT + timedelta(days=1))


SAT_AFTERNOON = windows((840, 1080))  # 2 PM to 6 PM


def test_inside_free_window_passes():
    r = check_event(user(), event(), SAT_AFTERNOON, NOW)
    assert r.passed and r.window is not None and r.travel_min > 0


def test_outside_free_window_goes_to_almost_with_reason():
    r = check_event(user(), event("17:00", "19:00"), SAT_AFTERNOON, NOW)
    assert not r.passed and r.almost
    assert r.reason == "Runs until 7 PM, you're free until 6 PM on Saturday."


def test_travel_buffer_is_respected():
    e = event("14:10", "15:00")  # free from 14:00, but travel + 10 min buffer needs an earlier start
    travel = travel_minutes(haversine_km(*HOME, e.lat, e.lng))
    assert travel > 0
    r = check_event(user(), e, SAT_AFTERNOON, NOW)
    assert r.almost and "leave by" in r.reason
    # Online events skip travel, so only the 10 min buffer applies.
    assert check_event(user(), event("14:10", "15:00", mode="online"), SAT_AFTERNOON, NOW).passed


def test_eligibility_drop():
    r = check_event(user(), event(eligibility={"required_tags": ["year_4"]}), SAT_AFTERNOON, NOW)
    assert r.failed_rule == "eligibility" and not r.almost


def test_format_drop():
    assert check_event(user(format_pref="in_person"), event(mode="online"), SAT_AFTERNOON, NOW).failed_rule == "format"
    assert check_event(user(format_pref="online"), event(), SAT_AFTERNOON, NOW).failed_rule == "format"


def test_budget_drop_and_any_budget():
    assert check_event(user(), event(fee_inr=250), SAT_AFTERNOON, NOW).failed_rule == "budget"
    assert check_event(user(budget_max_inr=None), event(fee_inr=2500), SAT_AFTERNOON, NOW).passed


def test_distance_drop():
    far = event(lat=11.30, lng=77.20)
    assert check_event(user(), far, SAT_AFTERNOON, NOW).failed_rule == "distance"


def test_deadline_passed_and_started_drop():
    assert check_event(user(), event(registration_deadline=NOW - timedelta(hours=1)), SAT_AFTERNOON, NOW).failed_rule == "status"
    assert check_event(user(), event(d=date(2026, 10, 24)), SAT_AFTERNOON, NOW).failed_rule == "status"


def test_unpublished_drop():
    assert check_event(user(), event(status="blocked"), SAT_AFTERNOON, NOW).failed_rule == "status"


def test_non_strict_schedule_skips_rule_6():
    assert check_event(user(strict_schedule=False), event("19:00", "21:00"), SAT_AFTERNOON, NOW).passed


def test_full_event_is_kept_as_waitlist():
    r = check_event(user(), event(capacity=20), SAT_AFTERNOON, NOW, registered_count=20)
    assert r.passed and r.waitlist


def test_not_free_that_day_reason():
    r = check_event(user(), event(d=SAT + timedelta(days=4)), SAT_AFTERNOON, NOW)
    assert r.reason == "You're not free on Wednesday."


# ---- distance: "Anywhere" and online events (prompt v2, item 1) ----

FAR = dict(lat=11.3410, lng=77.7172)  # Erode, about 85 km from Coimbatore


def test_far_event_dropped_with_a_km_limit():
    r = check_event(user(max_distance_km=50), event(start="20:00", end="21:00", **FAR), windows((0, 1440)), NOW)
    assert not r.passed and r.failed_rule == "distance"


def test_anywhere_keeps_far_events():
    r = check_event(user(max_distance_km=None), event(start="20:00", end="21:00", **FAR), windows((0, 1440)), NOW)
    assert r.passed and r.distance_km > 50


def test_online_events_ignore_distance_completely():
    for mode in ("online", "hybrid"):
        r = check_event(user(max_distance_km=5), event(mode=mode, **FAR), SAT_AFTERNOON, NOW)
        assert r.passed and r.distance_km is None and r.travel_min == 0


def test_anywhere_travel_score_is_bounded():
    from app.services.ranking import travel_score

    fr = check_event(user(max_distance_km=None), event(start="20:00", end="21:00", **FAR), windows((0, 1440)), NOW)
    assert 0 <= travel_score(fr, user(max_distance_km=None)) <= 100


# ---- events I'm going to count as busy (prompt v2, item 5) ----

def test_going_block_is_busy_and_explains_the_clash():
    from app.services.matching import Going, time_fit

    meetup = event(start="16:00", end="17:00", id="meetup")
    going = [Going("meetup", meetup.start_at, meetup.end_at, "Python Meetup")]
    other = event(start="16:30", end="17:30", id="other")
    r = check_event(user(), other, SAT_AFTERNOON, NOW, going=going)
    assert not r.passed and r.almost and r.reason == "You're already going to Python Meetup."
    assert time_fit(user(), other, SAT_AFTERNOON, going) == (False, "You're already going to Python Meetup.")
    # The event itself is never blocked by its own Going block.
    assert check_event(user(), meetup, SAT_AFTERNOON, NOW, going=going).passed
    # Travel time counts: leaving for an event right after another one clashes too.
    right_after = event(start="17:05", end="18:00", id="after")
    assert not check_event(user(), right_after, SAT_AFTERNOON, NOW, going=going).passed
