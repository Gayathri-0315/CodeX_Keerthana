"""Saved alerts: create from an Almost card, list and delete in Settings > My alerts."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..models import Event, SavedAlert, User
from ..services import alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])
student_only = require_role("student")


class AlertIn(BaseModel):
    event_id: str = Field(min_length=1, max_length=36)


@router.get("")
def list_alerts(user: User = Depends(student_only), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedAlert).where(SavedAlert.user_id == user.id).order_by(SavedAlert.created_at.desc()))
    return {"items": [alerts.alert_out(a) for a in rows]}


@router.post("", status_code=201)
def create_alert(body: AlertIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    event = db.get(Event, body.event_id)
    if event is None or event.status != "published" or event.start_at is None:
        raise HTTPException(404, "That event isn't available any more.")
    alert = alerts.create_from_event(db, user, event)
    return {**alerts.alert_out(alert), "found": alerts.fitting_now(db, user, alert)}


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: str, user: User = Depends(student_only), db: Session = Depends(get_db)):
    alert = db.get(SavedAlert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(404, "That alert doesn't exist.")
    db.delete(alert)
    db.commit()
