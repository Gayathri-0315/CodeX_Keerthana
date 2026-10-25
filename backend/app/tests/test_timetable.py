from app.seed.make_samples import TIMETABLES
from app.services.scheduling import gaps_from_periods


def timetable_png(name: str) -> bytes:
    return (TIMETABLES / "generated" / f"{name}.png").read_bytes()


def test_timetable_import_returns_free_gaps(client):
    client.post("/api/auth/demo", json={"role": "student"})
    r = client.post("/api/availability/timetable", files={"file": ("it_year3.png", timetable_png("it_year3"), "image/png")}).json()
    assert r["message"] is None and len(r["timetable"]["periods"]) == 25
    slots = {(s["day_of_week"], s["start_min"], s["end_min"]) for s in r["free_slots"]}
    # Monday: before class, short break, lunch, and after the lab until 21:00.
    assert {(0, 480, 540), (0, 640, 660), (0, 760, 810), (0, 990, 1260)} <= slots
    assert (6, 480, 1260) in slots  # Sunday is entirely free between 08:00 and 21:00
    # Nothing was saved yet: the student reviews first.
    assert len(client.get("/api/availability").json()["slots"]) == 2


def test_unknown_timetable_in_mock_mode_asks_to_paint(client):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (50, 50), "white").save(buf, "PNG")
    client.post("/api/auth/demo", json={"role": "student"})
    r = client.post("/api/availability/timetable", files={"file": ("mine.png", buf.getvalue(), "image/png")}).json()
    assert r["free_slots"] == [] and "Paint your free time" in r["message"]


def test_gap_math_handles_overlaps_and_edges():
    gaps = gaps_from_periods({0: [(470, 540), (530, 600), (1250, 1300)]}, 480, 1260)
    assert gaps[0] == [(600, 1250)]
