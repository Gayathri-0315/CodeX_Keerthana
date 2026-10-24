"""Per-user feed cache (SPEC 7.3): 30 s TTL, dropped on availability, profile or event changes."""

import threading
import time
from typing import Any

TTL_SECONDS = 30
_lock = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}


def get(user_id: str) -> Any | None:
    with _lock:
        hit = _cache.get(user_id)
        if hit and time.monotonic() - hit[0] < TTL_SECONDS:
            return hit[1]
        return None


def put(user_id: str, value: Any) -> None:
    with _lock:
        _cache[user_id] = (time.monotonic(), value)


def invalidate(user_id: str) -> None:
    with _lock:
        _cache.pop(user_id, None)


def invalidate_all() -> None:
    with _lock:
        _cache.clear()
