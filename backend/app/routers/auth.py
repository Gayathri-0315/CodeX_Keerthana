"""Email + password auth: sign-up (student or organizer), sign-in, password reset, lockout."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import auth_limit, client_ip, current_user, email_limit
from ..errors import fail
from ..models import AuthToken, Organizer, User
from ..schemas import ForgotIn, LoginIn, OrganizerRegisterIn, RegisterIn, ResetIn, UserOut
from ..security import (
    COOKIE_NAME, CSRF_COOKIE, TOKEN_DAYS, burn_password_check, create_token, hash_password, new_csrf,
    new_link_token, password_problem, sha256, verify_password,
)
from ..services.email import send_email
from ..timeutil import to_ist, utcnow
from .users import user_out

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_MINUTES = 30


def set_csrf(response: Response, value: str | None = None) -> None:
    # Readable by the page (double-submit token): the app echoes it in the X-CSRF-Token header.
    response.set_cookie(CSRF_COOKIE, value or new_csrf(), max_age=TOKEN_DAYS * 86400, httponly=False, samesite="lax",
                        secure=settings.is_production)


def sign_in(response: Response, user: User, hours: float | None = None) -> UserOut:
    response.set_cookie(
        COOKIE_NAME,
        create_token(user.id, user.session_version or 0, hours),
        max_age=int((hours or TOKEN_DAYS * 24) * 3600),
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )
    set_csrf(response)
    return user_out(user)


# ---- password reset links ----

def _issue_reset(db: Session, user: User) -> str:
    """A new single-use reset link; older unused ones stop working."""
    db.execute(update(AuthToken).where(AuthToken.user_id == user.id, AuthToken.kind == "reset", AuthToken.used_at.is_(None))
               .values(used_at=utcnow()))
    link = new_link_token()
    db.add(AuthToken(user_id=user.id, kind="reset", token_hash=sha256(link), expires_at=utcnow() + timedelta(minutes=RESET_MINUTES)))
    db.commit()
    return link


# ---- sign-up ----

def _new_user(db: Session, name: str, email: str, password: str, role: str) -> User:
    email = email.strip().lower()
    if problem := password_problem(password):
        fail(422, "weak_password", problem)
    if db.scalar(select(User.id).where(User.email == email)):
        fail(409, "email_taken", "That email already has an account. Sign in instead.")
    user = User(name=name.strip(), email=email, password_hash=hash_password(password), role=role,
                eligibility_tags=["college_student"] if role == "student" else [])
    if role != "student":
        user.onboarded = True  # organizers don't go through the student onboarding
    return user


@router.post("/register", response_model=UserOut, dependencies=[Depends(auth_limit)])
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    """Student sign-up (the "Discover events" side): name, email and password."""
    user = _new_user(db, body.name, body.email, body.password, "student")
    db.add(user)
    db.commit()
    return sign_in(response, user)


@router.post("/register-organizer", response_model=UserOut, dependencies=[Depends(auth_limit)])
def register_organizer(body: OrganizerRegisterIn, response: Response, db: Session = Depends(get_db)):
    """Organizer sign-up (the "Create events" side). Every new organizer starts at trust level `new` (SPEC 5.6)."""
    user = _new_user(db, body.name, body.email, body.password, "organizer")
    db.add(user)
    db.flush()
    from ..services.clubs import unique_slug

    db.add(Organizer(user_id=user.id, org_name=body.org_name.strip(), slug=unique_slug(db, body.org_name), org_email_domain=user.email.split("@")[-1],
                     phone=(body.phone or "").strip() or None, college_or_company=(body.college_or_company or "").strip() or None,
                     trust_level="new"))
    db.commit()
    db.refresh(user)
    return sign_in(response, user)


# ---- sign-in ----

@router.post("/login", response_model=UserOut, dependencies=[Depends(auth_limit)])
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    now = utcnow()
    if user is None:
        burn_password_check(body.password)
        fail(401, "bad_credentials", "Email or password is wrong. Check them and try again.")
    if user.locked_until and user.locked_until > now:
        minutes = max(1, round((user.locked_until - now).total_seconds() / 60))
        fail(423, "locked", f"Too many wrong passwords. This account is locked for {minutes} more minute{'s' if minutes != 1 else ''}. "
                            "Reset your password to unlock it now.")
    if not verify_password(body.password, user.password_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= settings.login_max_failures:
            user.failed_logins = 0
            user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
            db.commit()
            fail(423, "locked", f"Too many wrong passwords. This account is locked for {settings.login_lock_minutes} minutes. "
                                "Reset your password to unlock it now.")
        db.commit()
        fail(401, "bad_credentials", "Email or password is wrong. Check them and try again.")
    # Admins have no panel of their own yet (the private admin sign-in comes with the admin area), so either side works.
    if body.role and user.role != "admin" and body.role != user.role:
        other = "Create events" if user.role == "organizer" else "Discover events"
        fail(403, "wrong_role", f"This is {'an organizer' if user.role == 'organizer' else 'a student'} account. Sign in on the “{other}” side.")
    user.failed_logins, user.locked_until = 0, None
    db.commit()
    return sign_in(response, user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.get("/session")
def session(request: Request, response: Response, db: Session = Depends(get_db)):
    """Like /me, but a signed-out visitor gets `{"user": null}` instead of a 401. Also hands out the CSRF cookie."""
    if not request.cookies.get(CSRF_COOKIE):
        set_csrf(response)
    try:
        return {"user": user_out(current_user(request, db))}
    except HTTPException:
        return {"user": None}


@router.get("/config")
def public_config():
    return {"ai_live": settings.use_live_ai, "dev_tools": settings.is_dev}


# ---- password reset ----

@router.post("/forgot", status_code=204)
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Always answers the same way, so it can't be used to find out who has an account."""
    email_limit.hit(f"ip:{client_ip(request)}")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None:
        return
    email_limit.hit(f"reset:{user.id}")
    link = _issue_reset(db, user)
    # The time in the subject keeps a second request from hiding inside the first one's Gmail thread.
    sent = to_ist(utcnow()).strftime("%I:%M %p").lstrip("0")
    send_email(user.email, f"Reset your password ({sent})",
               f"Tap the button to choose a new password. The link works for {RESET_MINUTES} minutes.",
               "Choose a new password", f"{settings.public_url}/reset?token={link}", transactional=True)


@router.post("/reset", response_model=UserOut)
def reset(body: ResetIn, request: Request, response: Response, db: Session = Depends(get_db)):
    auth_limit(request)
    token = db.scalar(select(AuthToken).where(AuthToken.token_hash == sha256(body.token), AuthToken.kind == "reset"))
    if token is None or token.used_at or token.expires_at < utcnow():
        fail(400, "bad_token", "This reset link has expired or was already used. Ask for a new one.")
    if problem := password_problem(body.password):
        fail(422, "weak_password", problem)
    user = db.get(User, token.user_id)
    token.used_at = utcnow()
    user.password_hash = hash_password(body.password)
    user.session_version = (user.session_version or 0) + 1  # sign out every other session
    user.failed_logins, user.locked_until = 0, None
    db.commit()
    return sign_in(response, user)
