import hashlib
import hmac
import re
import secrets
from datetime import timedelta

import bcrypt
import jwt

from .config import settings
from .timeutil import utcnow

COOKIE_NAME = "showup_session"
CSRF_COOKIE = "showup_csrf"
CSRF_HEADER = "x-csrf-token"
TOKEN_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


# A fixed hash so a login for an unknown email costs the same time as a real one (no account probing by timing).
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt(rounds=12)).decode()


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


COMMON = {"password", "password1", "12345678", "123456789", "qwerty123", "iloveyou", "11111111", "showup123", "letmein1"}


def password_problem(password: str, strong: bool = False) -> str | None:
    """Plain-language reason a password is too weak, or None. `strong` is the stricter admin rule."""
    if len(password) < (12 if strong else 8):
        return f"Use at least {12 if strong else 8} characters."
    if password.lower() in COMMON:
        return "That password is too common. Pick something less guessable."
    if strong and not (re.search(r"[a-z]", password) and re.search(r"[A-Z]", password) and re.search(r"\d", password)
                       and re.search(r"[^A-Za-z0-9]", password)):
        return "Mix upper and lower case letters, a number and a symbol."
    return None


def create_token(user_id: str, session_version: int = 0, hours: float | None = None) -> str:
    exp = utcnow() + (timedelta(hours=hours) if hours else timedelta(days=TOKEN_DAYS))
    payload = {"sub": user_id, "sv": session_version, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> tuple[str, int] | None:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return data["sub"], int(data.get("sv", 0))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_link_token() -> str:
    return secrets.token_urlsafe(32)


def new_csrf() -> str:
    return secrets.token_urlsafe(24)


def same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(a, b)
