from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models_db import OccupancySummary
from backend.schemas import OccupancySummarySchema

router = APIRouter(prefix="/api/occupancy", tags=["occupancy"])

@router.get("/hourly", response_model=List[OccupancySummarySchema])
def get_hourly_occupancy(route_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(OccupancySummary)
    if route_id:
        query = query.filter(OccupancySummary.route_id == route_id)
    occ = query.all()
    return occ

@router.get("/overcrowded", response_model=List[OccupancySummarySchema])
def get_overcrowded_routes(route_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(OccupancySummary).filter(OccupancySummary.overcrowded_trips_count > 0)
    if route_id:
        query = query.filter(OccupancySummary.route_id == route_id)
    overcrowded = query.all()
    return overcrowded
