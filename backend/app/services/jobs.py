"""Background work (APScheduler, every 30 s): seat offers expiring, reminders, deadline alerts,
quiet-hours flush, and closing finished events (no-shows, organizer stats and trust, SPEC 5.10)."""

import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import Event, Organizer, Registration, Report, User
from ..timeutil import utcnow
from . import alerts, assist, feedcache, followup, notify, org_alerts, registration, together
from .showup_score import reminder_times

log = logging.getLogger("showup.jobs")
TICK_SECONDS = 30
DEADLINE_WINDOW = timedelta(hours=48)


def offer_seats(db: Session, promoted: list[Registration], now: datetime | None = None) -> None:
    """Tell each promoted person their seat is waiting (urgent, bypasses cap by one and quiet hours)."""
    for reg in promoted:
        event, user = db.get(Event, reg.event_id), db.get(User, reg.user_id)
        title, body = notify.seat_copy(event, settings.waitlist_confirm_minutes)
        # Not deduped: a seat can be offered to the same person more than once over an event's life.
        n = notify.Notification(user_id=user.id, type="seat_opened", event_id=event.id, title=title, body=body,
                                payload={"registration_id": reg.id, "expires_at": reg.promotion_expires_at.isoformat() + "Z"})
        db.add(n)
        db.commit()
        notify.deliver(db, n, user, now)


def send_reminders(db: Session, now: datetime) -> int:
    regs = db.scalars(
        select(Registration).join(Event, Event.id == Registration.event_id).where(
            Registration.status == "registered", Event.status == "published",
            Event.start_at > now, Event.start_at <= now + timedelta(hours=25),
        )
    ).all()
    sent = 0
    for reg in regs:
        event, user = db.get(Event, reg.event_id), db.get(User, reg.user_id)
        distance, travel = registration.travel_for(user, event)
        for kind, at in reminder_times(event.start_at, travel).items():
            if kind == "reminder_leave_by" and distance is None:
                continue  # online: nothing to leave for
            # Due now, and not one that was already due when they registered (no "tomorrow" ping an hour before).
            if at <= now and at >= reg.registered_at - timedelta(minutes=1):
                friends = [together.first_name(u) for _, u in together.companions(db, reg)]
                title, body = notify.reminder_copy(kind, event, registration.leave_by_for(user, event), friends)
                payload = {"registration_id": reg.id}
                if kind == "reminder_leave_by":
                    payload["maps_url"] = f"https://www.google.com/maps/dir/?api=1&destination={event.lat},{event.lng}"
                if notify.create(db, user, kind, event, title, body, payload, now=now):
                    sent += 1
    return sent


def send_deadline_alerts(db: Session, now: datetime) -> int:
    events = db.scalars(select(Event).where(
        Event.status == "published", Event.registration_deadline > now, Event.registration_deadline <= now + DEADLINE_WINDOW,
    )).unique().all()
    return sum(notify.suggest(db, e, "deadline", now=now) for e in events)


def close_finished(db: Session, now: datetime) -> int:
    """After an event ends: no-shows, the organizer's attendance rate, and trust promotion."""
    events = db.scalars(select(Event).where(Event.status == "published", Event.end_at < now, Event.closed_at.is_(None))).unique().all()
    for e in events:
        for r in db.scalars(select(Registration).where(Registration.event_id == e.id, Registration.status.in_(("registered", "promoted_pending")))):
            r.status = "no_show" if r.status == "registered" else "cancelled"
        db.flush()
        counts = dict(db.execute(select(Registration.status, func.count()).where(Registration.event_id == e.id).group_by(Registration.status)).all())
        attended, no_show = counts.get("attended", 0), counts.get("no_show", 0)
        e.closed_at = now
        org = db.get(Organizer, e.organizer_id) if e.organizer_id else None
        if org and attended + no_show > 0:
            rate = attended / (attended + no_show)
            n = org.past_events_count + 1
            org.avg_attendance_rate = rate if org.avg_attendance_rate is None else (org.avg_attendance_rate * (n - 1) + rate) / n
            org.past_events_count = n
            clean = valid_reports(db, org) == 0 and followup.organizer_described_ok(db, org)
            if org.trust_level == "new" and attended > 0 and clean:
                org.trust_level = "verified"
            elif org.trust_level == "verified" and n >= 3 and org.avg_attendance_rate >= 0.5 and clean:
                org.trust_level = "trusted"
        db.commit()
    if events:
        feedcache.invalidate_all()
    return len(events)


def valid_reports(db: Session, org: Organizer) -> int:
    """Reports not settled by an admin decision (an approval after the report clears it)."""
    return db.scalar(
        select(func.count()).select_from(Report).join(Event, Event.id == Report.event_id).where(
            Event.organizer_id == org.id, (Event.reviewed_at.is_(None)) | (Report.created_at > Event.reviewed_at)
        )
    ) or 0


def tick(now: datetime | None = None) -> None:
    now = now or utcnow()
    with SessionLocal() as db:
        for name, job in (
            ("expire_offers", lambda: offer_seats(db, registration.expire_offers(db, now), now)),
            ("reminders", lambda: send_reminders(db, now)),
            ("deadlines", lambda: send_deadline_alerts(db, now)),
            ("flush", lambda: notify.flush_pending(db, now)),
            ("organizer reminders", lambda: org_alerts.send_event_reminders(db, now)),
            ("organizer digests", lambda: org_alerts.send_digests(db, now)),
            ("how was it", lambda: followup.send_how_was(db, now)),
            ("chat summaries", lambda: assist.send_daily_summaries(db, now)),
            ("close", lambda: close_finished(db, now)),
        ):
            try:
                job()
            except Exception:
                db.rollback()
                log.exception("Job %s failed", name)


def suggest_for_event(db: Session, event_id: str) -> None:
    """Match alerts for a newly published event (run in the background after publishing)."""
    event = db.get(Event, event_id)
    if event is not None:
        notify.suggest(db, event)
        alerts.suggest_similar(db, event)
        from . import clubs

        clubs.notify_followers(db, event)


def in_background(fn, *args) -> None:
    """Run fn(db, *args) after the response, in its own session. Inline under tests for determinism."""
    def run():
        with SessionLocal() as db:
            try:
                fn(db, *args)
            except Exception:
                log.exception("Background task %s failed", getattr(fn, "__name__", fn))

    if settings.app_env == "test":
        run()
    else:
        threading.Thread(target=run, daemon=True).start()


_scheduler = None


def start_scheduler() -> None:
    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(tick, "interval", seconds=TICK_SECONDS, max_instances=1, coalesce=True, next_run_time=utcnow() + timedelta(seconds=5))
    _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
