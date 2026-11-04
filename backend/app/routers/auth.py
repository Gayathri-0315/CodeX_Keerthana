"""Email + password auth: sign-up (student or organizer), email verification, password reset, lockout."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import auth_limit, client_ip, current_user, email_limit
from ..errors import fail
from ..models import AuthToken, Organizer, User
from ..schemas import ForgotIn, LoginIn, OrganizerRegisterIn, RegisterIn, ResetIn, UserOut, VerifyIn
from ..security import (
    COOKIE_NAME, CSRF_COOKIE, TOKEN_DAYS, burn_password_check, create_token, hash_password, new_code, new_csrf,
    new_link_token, password_problem, sha256, verify_password,
)
from ..services.email import send_email
from ..timeutil import utcnow
from .users import user_out

router = APIRouter(prefix="/auth", tags=["auth"])

VERIFY_HOURS = 24
RESET_MINUTES = 30
MAX_CODE_ATTEMPTS = 5


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


# ---- one-time tokens ----

def _issue(db: Session, user: User, kind: str) -> tuple[str, str | None]:
    """New verification or reset token; older unused ones of the same kind stop working."""
    db.execute(update(AuthToken).where(AuthToken.user_id == user.id, AuthToken.kind == kind, AuthToken.used_at.is_(None))
               .values(used_at=utcnow()))
    link = new_link_token()
    code = new_code() if kind == "verify" else None
    ttl = timedelta(hours=VERIFY_HOURS) if kind == "verify" else timedelta(minutes=RESET_MINUTES)
    db.add(AuthToken(user_id=user.id, kind=kind, token_hash=sha256(link), code_hash=sha256(code) if code else None,
                     expires_at=utcnow() + ttl))
    db.commit()
    return link, code


def send_verification(db: Session, user: User) -> None:
    link, code = _issue(db, user, "verify")
    send_email(user.email, "Verify your email",
               f"Your ShowUp code is {code}. Enter it in the app, or tap the button. It expires in {VERIFY_HOURS} hours.",
               "Verify email", f"{settings.public_url}/verify?token={link}", transactional=True)


def _mark_verified(db: Session, user: User, token: AuthToken) -> None:
    token.used_at = utcnow()
    user.email_verified_at = user.email_verified_at or utcnow()
    db.commit()


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
    """Student sign-up (the "Discover events" side)."""
    user = _new_user(db, body.name, body.email, body.password, "student")
    user.college = body.college.strip() if body.college else None
    db.add(user)
    db.commit()
    send_verification(db, user)
    return sign_in(response, user)


@router.post("/register-organizer", response_model=UserOut, dependencies=[Depends(auth_limit)])
def register_organizer(body: OrganizerRegisterIn, response: Response, db: Session = Depends(get_db)):
    """Organizer sign-up (the "Create events" side). Every new organizer starts at trust level `new` (SPEC 5.6)."""
    user = _new_user(db, body.name, body.email, body.password, "organizer")
    db.add(user)
    db.flush()
    db.add(Organizer(user_id=user.id, org_name=body.org_name.strip(), org_email_domain=user.email.split("@")[-1],
                     phone=(body.phone or "").strip() or None, college_or_company=body.college_or_company.strip(),
                     trust_level="new"))
    db.commit()
    db.refresh(user)
    send_verification(db, user)
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
    if body.role and body.role != user.role:
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


# ---- email verification ----

@router.post("/verify", response_model=UserOut)
def verify(body: VerifyIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Verify by the 6-digit code (signed in) or by the emailed link token (works in any browser)."""
    auth_limit(request)
    now = utcnow()
    if body.token:
        token = db.scalar(select(AuthToken).where(AuthToken.token_hash == sha256(body.token), AuthToken.kind == "verify"))
        if token is None or token.used_at or token.expires_at < now:
            fail(400, "bad_token", "This link has expired or was already used. Sign in and ask for a new code.")
        user = db.get(User, token.user_id)
        _mark_verified(db, user, token)
        return user_out(user)
    user = current_user(request, db)
    if user.email_verified_at:
        return user_out(user)
    token = db.scalar(select(AuthToken).where(AuthToken.user_id == user.id, AuthToken.kind == "verify", AuthToken.used_at.is_(None))
                      .order_by(AuthToken.created_at.desc()).limit(1))
    if token is None or token.expires_at < now or token.attempts >= MAX_CODE_ATTEMPTS:
        fail(400, "bad_code", "That code has expired. Tap “Send a new code”.")
    if token.code_hash != sha256((body.code or "").strip()):
        token.attempts += 1
        db.commit()
        fail(400, "bad_code", "That code isn't right. Check the latest email and try again.")
    _mark_verified(db, user, token)
    return user_out(user)


@router.post("/resend-verification", status_code=204)
def resend_verification(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    email_limit.hit(f"verify:{user.id}")
    email_limit.hit(f"ip:{client_ip(request)}")
    if user.email_verified_at is None:
        send_verification(db, user)


# ---- password reset ----

@router.post("/forgot", status_code=204)
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Always answers the same way, so it can't be used to find out who has an account."""
    email_limit.hit(f"ip:{client_ip(request)}")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or user.role == "admin":
        return
    email_limit.hit(f"reset:{user.id}")
    link, _ = _issue(db, user, "reset")
    send_email(user.email, "Reset your password",
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
    user.email_verified_at = user.email_verified_at or utcnow()  # they proved they read this inbox
    db.commit()
    return sign_in(response, user)
