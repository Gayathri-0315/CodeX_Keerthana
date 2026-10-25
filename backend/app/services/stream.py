"""Server-Sent Events hub: per-user queues fed from any thread (SPEC 9 /stream)."""

import asyncio
import json
import threading
from collections import defaultdict

_lock = threading.Lock()
_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def subscribe(user_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    with _lock:
        _subscribers[user_id].add(q)
    return q


def unsubscribe(user_id: str, q: asyncio.Queue) -> None:
    with _lock:
        _subscribers[user_id].discard(q)
        if not _subscribers[user_id]:
            _subscribers.pop(user_id, None)


def is_online(user_id: str) -> bool:
    with _lock:
        return bool(_subscribers.get(user_id))


def publish(user_id: str, kind: str, data: dict) -> bool:
    """Queue an event for every open tab of this user. Safe to call from worker threads."""
    if _loop is None:
        return False
    with _lock:
        queues = list(_subscribers.get(user_id, ()))
    message = f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"

    def put():
        for q in queues:
            if not q.full():  # a stalled tab drops events rather than blocking everyone
                q.put_nowait(message)

    _loop.call_soon_threadsafe(put)
    return bool(queues)
