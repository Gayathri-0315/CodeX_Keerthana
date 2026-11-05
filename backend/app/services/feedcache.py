"""Per-user cache (SPEC 7.3): 30 s TTL, dropped on availability, profile, registration or event changes.

Holds the evaluated feed and anything built from it (the "Your week" view), so one invalidation clears all.
"""

import threading
import time
from typing import Any

TTL_SECONDS = 30
_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, Any]] = {}


def get(user_id: str, key: str = "feed", ttl: float = TTL_SECONDS) -> Any | None:
    with _lock:
        hit = _cache.get((user_id, key))
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        return None


def put(user_id: str, value: Any, key: str = "feed") -> None:
    with _lock:
        _cache[(user_id, key)] = (time.monotonic(), value)


def invalidate(user_id: str) -> None:
    with _lock:
        for k in [k for k in _cache if k[0] == user_id]:
            del _cache[k]


def invalidate_all() -> None:
    with _lock:
        _cache.clear()
