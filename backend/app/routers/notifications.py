import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Event, Notification, User
from ..services import stream
from ..services.notify import notification_out
from ..timeutil import utcnow

router = APIRouter(tags=["notifications"])
HEARTBEAT_S = 20


@router.get("/notifications")
def list_notifications(limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Notification, Event.title).outerjoin(Event, Event.id == Notification.event_id)
        .where(Notification.user_id == user.id, Notification.dismissed.is_(False))
        .order_by(Notification.created_at.desc()).limit(limit)
    ).all()
    unread = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None), Notification.dismissed.is_(False)))
    return {"items": [notification_out(n, title) for n, title in rows], "unread": unread or 0}


def _mine(db: Session, user: User, nid: str) -> Notification:
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "That alert doesn't exist.")
    return n


@router.post("/notifications/{nid}/read", status_code=204)
def read(nid: str, clicked: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = _mine(db, user, nid)
    now = utcnow()
    n.read_at = n.read_at or now
    if clicked:
        n.clicked_at = now
    db.commit()


@router.post("/notifications/read-all", status_code=204)
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=utcnow()))
    db.commit()


@router.post("/notifications/{nid}/dismiss", status_code=204)
def dismiss(nid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = _mine(db, user, nid)
    n.dismissed = True
    n.read_at = n.read_at or utcnow()
    db.commit()


@router.get("/stream")
async def events_stream(request: Request, user: User = Depends(current_user)):
    """SSE: live toasts and seat updates for this user. A comment line every 20 s keeps proxies open."""
    queue = stream.subscribe(user.id)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_S)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            stream.unsubscribe(user.id, queue)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
