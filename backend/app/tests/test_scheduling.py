from datetime import date
from types import SimpleNamespace

from app.services.scheduling import day_intervals, free_windows, gaps_from_periods, merge, subtract
from app.timeutil import ist_to_utc

SAT = date(2026, 10, 31)  # a Saturday


def slot(dow, s, e, *, d=None, kind="free"):
    return SimpleNamespace(day_of_week=dow, start_min=s, end_min=e, recurring=d is None, date=d, kind=kind)


def test_merge_joins_overlaps_and_touching():
    assert merge([(600, 660), (540, 600), (700, 720), (650, 690)]) == [(540, 690), (700, 720)]


def test_subtract_splits():
    assert subtract([(540, 780)], [(600, 630), (700, 900)]) == [(540, 600), (630, 700)]


def test_recurring_slot_applies_to_matching_weekday_only():
    slots = [slot(5, 840, 1080)]
    assert day_intervals(slots, SAT) == [(840, 1080)]
    assert day_intervals(slots, date(2026, 11, 1)) == []


def test_one_off_free_adds_and_busy_override_removes():
    slots = [slot(5, 840, 1080), slot(5, 600, 660, d=SAT), slot(5, 900, 960, d=SAT, kind="busy_override")]
    assert day_intervals(slots, SAT) == [(600, 660), (840, 900), (960, 1080)]
    # The override only touches that date.
    assert day_intervals(slots, date(2026, 11, 7)) == [(840, 1080)]


def test_free_windows_are_utc_and_merge_across_midnight():
    slots = [slot(5, 1320, 1440), slot(6, 0, 60)]
    windows = free_windows(slots, SAT, date(2026, 11, 1))
    assert windows == [(ist_to_utc(SAT, 1320), ist_to_utc(date(2026, 11, 1), 60))]


def test_timetable_gaps_between_8_and_21():
    gaps = gaps_from_periods({0: [(540, 590), (600, 650), (780, 830)]}, 480, 1260)
    assert gaps[0] == [(480, 540), (590, 600), (650, 780), (830, 1260)]
    assert gaps[6] == [(480, 1260)]
