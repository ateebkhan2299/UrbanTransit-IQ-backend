from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models_db import RouteGeo, StopHotspot
from backend.schemas import RouteGeoItem, StopHotspotItem, PathPoint

router = APIRouter(prefix="/api/map", tags=["map"])

@router.get("/routes-geo", response_model=List[RouteGeoItem])
def get_routes_geo(db: Session = Depends(get_db)):
    geos = db.query(RouteGeo).all()
    res = [
        RouteGeoItem(
            route_id=g.route_id,
            route_name=g.route_name,
            status_color=g.status_color,
            path=[PathPoint(**p) for p in (g.path_json or [])]
        )
        for g in geos
    ]
    return res

@router.get("/delay-hotspots", response_model=List[StopHotspotItem])
def get_delay_hotspots(db: Session = Depends(get_db)):
    hotspots = db.query(StopHotspot).all()
    res = [
        StopHotspotItem(
            stop_id=h.stop_id,
            stop_name=h.stop_name,
            latitude=h.latitude,
            longitude=h.longitude,
            delay_events=h.delay_events
        )
        for h in hotspots
    ]
    return res
