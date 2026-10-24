import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import COOKIE_NAME, decode_token


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
    user_id = decode_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(401, "Please sign in to continue.")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "You don't have access to this.")
        return user

    return dep


class RateLimit:
    """Small in-memory sliding-window limiter, keyed by client IP. Enough for a single-process pilot."""

    def __init__(self, limit: int, per_seconds: int):
        self.limit, self.per = limit, per_seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.per:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
        q.append(now)


auth_limit = RateLimit(20, 60)
upload_limit = RateLimit(10, 60)
