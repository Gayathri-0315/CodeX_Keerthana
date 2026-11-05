"""Explore tab (prompt v2, item 3): every upcoming published event, filters, time-fit badge."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event
from app.services import feedcache

from .conftest import login


def all_explore(client, **params) -> list[dict]:
    items, cursor = [], ""
    while True:
        r = client.get("/api/feed/explore", params={**params, "limit": 5, **({"cursor": cursor} if cursor else {})}).json()
        items += r["items"]
        cursor = r["next_cursor"]
        if not cursor:
            return items


def test_explore_shows_every_published_event_sorted_and_never_blocked_or_pending(client):
    login(client, "student")
    with SessionLocal() as db:
        e = db.scalar(select(Event).where(Event.title == "Python Meetup Coimbatore"))
        e.status = "pending_review"
        db.commit()
        published = {i for (i,) in db.execute(select(Event.id).where(Event.status == "published"))}
        hidden = {i for (i,) in db.execute(select(Event.id).where(Event.status != "published"))}
    feedcache.invalidate_all()
    items = all_explore(client)
    ids = [i["id"] for i in items]
    assert set(ids) <= published and not set(ids) & hidden
    assert len(ids) == len(set(ids))  # paging never repeats
    starts = [i["start_at"] for i in items]
    assert starts == sorted(starts)
    for_you = {i["id"] for i in client.get("/api/feed?limit=50").json()["items"]}
    assert len(ids) > len(for_you)  # non-fitting events are not hidden


def test_badges_say_whether_it_fits_with_a_reason(client):
    login(client, "student")
    items = {i["title"]: i["time_fit"] for i in all_explore(client)}
    assert items["Python Meetup Coimbatore"] == {"fits": True, "reason": None}
    clash = items["ML Hackathon: Build for Kovai"]
    assert clash["fits"] is False and "Runs until 5 PM" in clash["reason"]


def test_explore_filters(client):
    login(client, "student")
    free = all_explore(client, price="free")
    assert free and all(i["fee_inr"] == 0 for i in free)
    paid = all_explore(client, price="paid")
    assert paid and all(i["fee_inr"] > 0 for i in paid)
    online = all_explore(client, mode="online")
    assert online and all(i["mode"] != "in_person" for i in online)
    found = all_explore(client, q="python")
    assert found and all("python" in i["title"].lower() for i in found)
    cats = client.get("/api/feed/categories").json()["categories"]
    assert [c["slug"] for c in cats][:3] == ["ai-ml", "cyber-security", "web-app"]
    ai = next(c for c in cats if c["slug"] == "ai-ml")
    one = all_explore(client, category="ai-ml")
    assert ai["count"] == len(one) > 0 and all(i["category_slug"] == "ai-ml" for i in one)
    first = all_explore(client)[0]["start_at"][:10]
    assert all(i["start_at"][:10] >= first for i in all_explore(client, date_from=first))
