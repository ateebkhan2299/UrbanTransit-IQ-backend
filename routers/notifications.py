from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models_db import NotificationAlert
from backend.schemas import NotificationResponse

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("", response_model=List[NotificationResponse])
def get_notifications(unread_only: bool = Query(False), db: Session = Depends(get_db)):
    query = db.query(NotificationAlert)
    if unread_only:
        query = query.filter(NotificationAlert.is_read == False)
    alerts = query.order_by(NotificationAlert.id.desc()).all()
    res = [
        NotificationResponse(
            id=a.id,
            severity=a.severity,
            message=a.message,
            route_id=a.route_id,
            route_name=a.route_name,
            created_at=a.created_at,
            is_read=a.is_read
        )
        for a in alerts
    ]
    return res
