from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models_db import DelaySummary, RouteSummary
from backend.schemas import DelayCauseItem, DelaySummarySchema, RouteSummarySchema

router = APIRouter(prefix="/api/delays", tags=["delays"])

@router.get("/by-cause", response_model=List[DelayCauseItem])
def get_delays_by_cause(route_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    try:
        from database.mongo_db import get_collection
        causes_col = get_collection("viz_delay_causes")
        docs = list(causes_col.find({}, {"_id": 0}))
        if docs:
            return [
                DelayCauseItem(
                    cause=d.get("cause", "Traffic Congestion"),
                    incident_count=d.get("incident_count", 0),
                    percentage_share=d.get("percentage_share", 0.0)
                )
                for d in docs
            ]
    except Exception:
        pass

    delays = db.query(DelaySummary).all()
    res = [
        DelayCauseItem(
            cause=d.cause,
            incident_count=d.incident_count,
            percentage_share=d.percentage_share
        )
        for d in delays
    ]
    return res

@router.get("/summary", response_model=List[DelaySummarySchema])
def get_delay_summary(db: Session = Depends(get_db)):
    delays = db.query(DelaySummary).all()
    return delays

@router.get("/routes", response_model=List[RouteSummarySchema])
def get_delayed_routes(db: Session = Depends(get_db)):
    routes = db.query(RouteSummary).order_by(RouteSummary.avg_delay_minutes.desc()).all()
    return routes
