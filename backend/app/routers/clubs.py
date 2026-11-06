"""Club pages (public) and follow (students)."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import RateLimit, client_ip, optional_user, student_only
from ..models import Follow, Organizer, User
from ..services import clubs, feedcache

router = APIRouter(tags=["clubs"])
search_limit = RateLimit(30, 60, "You're searching quickly. Wait a moment and try again.")


def _club(db: Session, slug: str) -> Organizer:
    org = db.scalar(select(Organizer).where(Organizer.slug == slug))
    if org is None:
        raise HTTPException(404, "That club doesn't exist.")
    return org


@router.get("/public/clubs")
def search_clubs(request: Request, q: str = Query("", max_length=200), viewer: User | None = Depends(optional_user),
                 db: Session = Depends(get_db)):
    """Clubs by name, for search. Public, so guests can find a club too."""
    search_limit.hit(client_ip(request))
    return {"items": clubs.search(db, q, viewer)}


@router.get("/public/clubs/{slug}")
def club_page(slug: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return clubs.club_out(db, _club(db, slug), viewer)


@router.post("/clubs/{slug}/follow")
def follow(slug: str, user: User = Depends(student_only), db: Session = Depends(get_db)):
    org = _club(db, slug)
    if not db.scalar(select(Follow.id).where(Follow.student_id == user.id, Follow.organizer_id == org.id)):
        db.add(Follow(student_id=user.id, organizer_id=org.id))
        try:
            db.commit()
        except IntegrityError:  # two taps at once: the pair is unique
            db.rollback()
    feedcache.invalidate(user.id)
    return {"following": True, "followers": clubs.follower_count(db, org.id)}


@router.delete("/clubs/{slug}/follow")
def unfollow(slug: str, user: User = Depends(student_only), db: Session = Depends(get_db)):
    org = _club(db, slug)
    row = db.scalar(select(Follow).where(Follow.student_id == user.id, Follow.organizer_id == org.id))
    if row:
        db.delete(row)
        db.commit()
    feedcache.invalidate(user.id)
    return {"following": False, "followers": clubs.follower_count(db, org.id)}


@router.get("/me/following")
def my_following(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Only the student sees which clubs they follow."""
    orgs = db.scalars(select(Organizer).join(Follow, Follow.organizer_id == Organizer.id)
                      .where(Follow.student_id == user.id).order_by(Organizer.org_name)).all()
    return {"items": [{"slug": clubs.ensure_slug(db, o), "name": o.org_name, "logo_url": o.logo_url} for o in orgs]}
