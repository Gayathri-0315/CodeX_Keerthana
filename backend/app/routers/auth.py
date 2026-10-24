from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import auth_limit, current_user
from ..models import User
from ..schemas import DemoLoginIn, LoginIn, RegisterIn, UserOut
from ..security import COOKIE_NAME, TOKEN_DAYS, create_token, hash_password, verify_password
from .users import user_out

router = APIRouter(prefix="/auth", tags=["auth"])

DEMO_EMAILS = {"student": "student@demo.app", "organizer": "organizer@demo.app", "admin": "admin@demo.app"}


def _sign_in(response: Response, user: User) -> UserOut:
    response.set_cookie(
        COOKIE_NAME,
        create_token(user.id),
        max_age=TOKEN_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "prod",
    )
    return user_out(user)


@router.post("/register", response_model=UserOut, dependencies=[Depends(auth_limit)])
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "That email already has an account. Sign in instead.")
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password), eligibility_tags=["college_student"])
    db.add(user)
    db.commit()
    return _sign_in(response, user)


@router.post("/login", response_model=UserOut, dependencies=[Depends(auth_limit)])
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is wrong. Check them and try again.")
    return _sign_in(response, user)


@router.post("/demo", response_model=UserOut)
def demo_login(body: DemoLoginIn, response: Response, db: Session = Depends(get_db)):
    if not settings.demo_mode:
        raise HTTPException(404, "Demo sign-in is turned off.")
    user = db.scalar(select(User).where(User.email == DEMO_EMAILS[body.role]))
    if user is None:
        raise HTTPException(503, "Demo data is missing. Run `npm run seed` and try again.")
    return _sign_in(response, user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.get("/config")
def public_config():
    return {"demo_mode": settings.demo_mode, "ai_live": settings.use_live_ai}
