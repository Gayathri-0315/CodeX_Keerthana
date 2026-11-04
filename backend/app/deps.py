import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .errors import fail
from .models import User
from .security import COOKIE_NAME, decode_token
from .timeutil import utcnow


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
    decoded = decode_token(token) if token else None
    user = db.get(User, decoded[0]) if decoded else None
    # A password change or reset bumps session_version, which signs out every older session.
    if user is None or decoded[1] != (user.session_version or 0):
        raise HTTPException(401, "Please sign in to continue.")
    now = utcnow()
    if user.last_active_at is None or now - user.last_active_at > timedelta(minutes=10):
        user.last_active_at = now  # coarse on purpose: one write per 10 minutes at most
        db.commit()
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "You don't have access to this.")
        return user

    return dep


def require_verified(user: User = Depends(current_user)) -> User:
    if user.email_verified_at is None:
        fail(403, "unverified", "Verify your email first. We sent you a 6-digit code.")
    return user


def client_ip(request: Request) -> str:
    # Behind Render's proxy uvicorn runs with --proxy-headers, so request.client is the real client.
    return request.client.host if request.client else "unknown"


class RateLimit:
    """Small in-memory sliding-window limiter, keyed by client IP. Enough for a single-process pilot."""

    def __init__(self, limit: int, per_seconds: int, message: str = "Too many attempts. Wait a minute and try again."):
        self.limit, self.per, self.message = limit, per_seconds, message
        self.hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.per:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(429, self.message)
        q.append(now)

    def __call__(self, request: Request) -> None:
        self.hit(client_ip(request))

    def reset(self) -> None:
        self.hits.clear()


auth_limit = RateLimit(20, 60)
email_limit = RateLimit(5, 600, "Too many emails requested. Wait a few minutes and try again.")
upload_limit = RateLimit(10, 60)
