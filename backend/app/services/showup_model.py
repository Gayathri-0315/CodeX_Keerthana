"""Learned show-up prediction: will this registrant actually come?

A small logistic regression in plain Python (no numpy), retrained every night from finished events
(attended vs no-show). It only replaces the hand-tuned rules in showup_score.py when it has enough real
outcomes AND predicts held-out events better than the rules. Until then the rules are used.

Privacy and fairness: the prediction is never shown per student to organizers (only totals and advice),
and it is only used to privately ask a likely no-show to confirm, so a waitlisted student can get the seat.
"""

import logging
import math
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, ExtractionCache, Registration, User
from ..timeutil import iso_utc, to_ist, utcnow

log = logging.getLogger("showup.model")
KEY = "model:showup"
MIN_ROWS, MIN_EACH = 200, 30  # need this many finished registrations, with this many of both outcomes
NAMES = ["bias", "with_friend", "interest", "distance", "days_before", "confirmed", "past_rate", "has_history",
         "tight_fit", "weekend", "evening", "paid"]


@dataclass
class Features:
    with_friend: bool
    interest: float | None  # 0..100
    distance_km: float | None
    days_before: float
    confirmed: bool
    past_rate: float | None
    slack_min: float | None
    start: datetime
    fee_inr: int

    def vector(self) -> list[float]:
        local = to_ist(self.start)
        return [
            1.0,
            float(self.with_friend),
            (self.interest if self.interest is not None else 60.0) / 100,
            min(self.distance_km or 0.0, 40.0) / 10,
            min(max(self.days_before, 0.0), 60.0) / 7,
            float(self.confirmed),
            self.past_rate if self.past_rate is not None else 0.5,
            float(self.past_rate is not None),
            float(self.slack_min is not None and self.slack_min < 30),
            float(local.weekday() >= 5),
            float(local.hour >= 17),
            float(self.fee_inr > 0),
        ]


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))


def predict(model: dict, f: Features) -> float:
    x = f.vector()
    z = sum(w * (v - m) / s for w, v, m, s in zip(model["weights"], x, model["means"], model["stds"]))
    return _sigmoid(z)


def _fit(xs: list[list[float]], ys: list[int], l2: float = 0.5, steps: int = 400, lr: float = 0.3) -> dict:
    """Standardize, then batch gradient descent on L2-regularized log loss. Small data, so plain Python is fine."""
    n, d = len(xs), len(xs[0])
    means = [sum(x[j] for x in xs) / n for j in range(d)]
    stds = [math.sqrt(sum((x[j] - means[j]) ** 2 for x in xs) / n) or 1.0 for j in range(d)]
    means[0], stds[0] = 0.0, 1.0  # keep the bias column as 1
    zs = [[(x[j] - means[j]) / stds[j] for j in range(d)] for x in xs]
    w = [0.0] * d
    for _ in range(steps):
        grad = [0.0] * d
        for z, y in zip(zs, ys):
            err = _sigmoid(sum(a * b for a, b in zip(w, z))) - y
            for j in range(d):
                grad[j] += err * z[j]
        for j in range(d):
            w[j] -= lr * (grad[j] / n + (l2 * w[j] / n if j else 0.0))
    return {"weights": w, "means": means, "stds": stds}


def _log_loss(ps: list[float], ys: list[int]) -> float:
    eps = 1e-6
    return -sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in zip(ps, ys)) / max(len(ys), 1)


def training_rows(db: Session) -> list[tuple[Features, int, str]]:
    """(features, attended?, event id) for every finished registration with a known outcome."""
    from .registration import features_for

    rows = db.execute(select(Registration, User, Event).join(User, User.id == Registration.user_id)
                      .join(Event, Event.id == Registration.event_id)
                      .where(Registration.status.in_(("attended", "no_show")), Event.end_at < utcnow())).all()
    out = []
    for reg, user, event in rows:
        try:
            out.append((features_for(db, user, event, reg, exclude_event=True), int(reg.status == "attended"), event.id))
        except Exception:  # noqa: BLE001 - one odd row shouldn't stop training
            log.warning("skipped a training row")
    return out


def train(db: Session, rows: list[tuple[Features, int, str]] | None = None) -> dict:
    """Fit on most events, test on the rest (split by event, so it's judged on events it hasn't seen).
    Saves the model only if it beats the rules. Returns a short report."""
    from .showup_score import likelihood

    rows = rows if rows is not None else training_rows(db)
    pos = sum(y for _, y, _ in rows)
    report = {"rows": len(rows), "attended": pos, "no_show": len(rows) - pos, "used": False, "trained_at": iso_utc(utcnow())}
    if len(rows) < MIN_ROWS or min(pos, len(rows) - pos) < MIN_EACH:
        report["reason"] = f"Not enough finished events yet (need {MIN_ROWS} registrations with at least {MIN_EACH} of each outcome)."
        _save(db, None, report)
        return report
    events = sorted({e for _, _, e in rows})
    random.Random(7).shuffle(events)
    test_events = set(events[: max(1, len(events) // 5)])
    train_rows = [r for r in rows if r[2] not in test_events]
    test_rows = [r for r in rows if r[2] in test_events]
    model = _fit([f.vector() for f, _, _ in train_rows], [y for _, y, _ in train_rows])
    ys = [y for _, y, _ in test_rows]
    learned = _log_loss([predict(model, f) for f, _, _ in test_rows], ys)
    rules = _log_loss([likelihood(f.interest, f.distance_km, f.days_before, f.confirmed, f.past_rate, f.slack_min, f.with_friend).p
                       for f, _, _ in test_rows], ys)
    report.update({"test_rows": len(test_rows), "log_loss_learned": round(learned, 4), "log_loss_rules": round(rules, 4)})
    if learned < rules:
        final = _fit([f.vector() for f, _, _ in rows], [y for _, y, _ in rows])  # refit on everything
        final["weights_named"] = dict(zip(NAMES, (round(w, 3) for w in final["weights"])))
        report["used"] = True
        _save(db, final, report)
    else:
        report["reason"] = "The learned model didn't beat the rules on held-out events, so the rules stay."
        _save(db, None, report)
    log.info("show-up model: %s", {k: v for k, v in report.items() if k != "trained_at"})
    return report


_cache: tuple[float, dict | None] = (0.0, None)
_lock = threading.Lock()


def _save(db: Session, model: dict | None, report: dict) -> None:
    global _cache
    row = db.get(ExtractionCache, KEY)
    value = {"model": model, "report": report}
    if row:
        row.result = value
    else:
        db.add(ExtractionCache(key=KEY, result=value))
    db.commit()
    with _lock:
        _cache = (time.monotonic(), model)


def current(db: Session) -> dict | None:
    """The model in use, or None (use the rules). Cached in memory for 10 minutes."""
    global _cache
    with _lock:
        at, model = _cache
    if time.monotonic() - at < 600 and at:
        return model
    row = db.get(ExtractionCache, KEY)
    model = (row.result or {}).get("model") if row else None
    with _lock:
        _cache = (time.monotonic(), model)
    return model


def status(db: Session) -> dict:
    row = db.get(ExtractionCache, KEY)
    return (row.result or {}).get("report") if row else {"used": False, "reason": "Not trained yet."}


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = (0.0, None)
