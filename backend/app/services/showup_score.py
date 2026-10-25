"""Show-up likelihood (SPEC 5.7): transparent rules, a planning estimate, never a promise."""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .matching import BUFFER_MIN

FLOOR, CEIL = 0.15, 0.95


@dataclass
class Likelihood:
    p: float
    reasons: list[str] = field(default_factory=list)


def likelihood(
    interest: float | None,
    distance_km: float | None,
    days_before: float,
    reminder_confirmed: bool,
    past_rate: float | None,
    slack_min: float | None,
) -> Likelihood:
    """`past_rate` is the user's attended / (attended + no-show), only when they have >= 2 past registrations."""
    p = 0.70
    reasons: list[str] = []
    if interest is not None and interest >= 80:
        p += 0.10
        reasons.append("Strong interest match (+10%)")
    if distance_km is not None and distance_km > 15:
        p -= 0.15
        reasons.append(f"Lives {round(distance_km)} km away (-15%)")
    elif distance_km is not None and distance_km > 8:
        p -= 0.07
        reasons.append(f"Lives {round(distance_km)} km away (-7%)")
    if days_before > 14:
        p -= 0.10
        reasons.append("Registered more than 2 weeks ahead (-10%)")
    if reminder_confirmed:
        p += 0.10
        reasons.append("Confirmed they're still going (+10%)")
    if past_rate is not None:
        delta = 0.20 * (past_rate - 0.5)
        p += delta
        reasons.append(f"Attended {round(past_rate * 100)}% of past events ({'+' if delta >= 0 else ''}{round(delta * 100)}%)")
    if slack_min is not None and slack_min < 30:
        p -= 0.05
        reasons.append("Tight fit with their free time (-5%)")
    return Likelihood(round(min(CEIL, max(FLOOR, p)), 2), reasons)


def expected_turnout(ps: list[float]) -> tuple[float, int, int]:
    """Expected count with a rough 80% range (normal approximation of a sum of Bernoullis)."""
    mean = sum(ps)
    sd = math.sqrt(sum(p * (1 - p) for p in ps))
    return round(mean, 1), max(0, math.floor(mean - 1.28 * sd)), min(len(ps), math.ceil(mean + 1.28 * sd))


def leave_by(start_at: datetime, travel_min: int) -> datetime:
    """SPEC 5.8: start - travel - 10 min buffer."""
    return start_at - timedelta(minutes=travel_min + BUFFER_MIN)


def reminder_times(start_at: datetime, travel_min: int) -> dict[str, datetime]:
    """When each reminder goes out: 24 h before, 2 h before, and 15 min before leave-by."""
    return {
        "reminder_24h": start_at - timedelta(hours=24),
        "reminder_2h": start_at - timedelta(hours=2),
        "reminder_leave_by": leave_by(start_at, travel_min) - timedelta(minutes=15),
    }
