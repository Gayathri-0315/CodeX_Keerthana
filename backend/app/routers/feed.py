from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..services.feed import evaluate

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/count")
def feed_count(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Events that fit the user's free time right now (drives the live calendar pill)."""
    results = evaluate(db, user)
    return {
        "fits": sum(1 for r in results if r.result.passed),
        "almost": sum(1 for r in results if r.result.almost),
    }
