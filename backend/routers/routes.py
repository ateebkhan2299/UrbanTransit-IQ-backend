from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models_db import RouteSummary
from backend.schemas import RouteListItem, RouteDetailResponse, RouteSummarySchema

router = APIRouter(prefix="/api/routes", tags=["routes"])

@router.get("/list", response_model=List[RouteListItem])
def get_routes_list(db: Session = Depends(get_db)):
    try:
        from database.mongo_db import get_collection
        routes_col = get_collection("clean_routes")
        docs = list(routes_col.find({}, {"route_id": 1, "route_short_name": 1, "route_long_name": 1, "_id": 0}).limit(100))
        if docs:
            return [
                RouteListItem(
                    route_id=d.get("route_id", ""),
                    route_name=f"{d.get('route_short_name', '')} - {d.get('route_long_name', '')}".strip(" -")
                )
                for d in docs
            ]
    except Exception:
        pass

    routes = db.query(RouteSummary).all()
    res = [RouteListItem(route_id=r.route_id, route_name=r.route_name) for r in routes]
    return res

@router.get("", response_model=List[RouteSummarySchema])
def get_all_routes(db: Session = Depends(get_db)):
    routes = db.query(RouteSummary).all()
    return routes

@router.get("/{route_id}", response_model=RouteDetailResponse)
def get_route_by_id(route_id: str, db: Session = Depends(get_db)):
    r = db.query(RouteSummary).filter(RouteSummary.route_id == route_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return RouteDetailResponse(
        route_id=r.route_id,
        route_name=r.route_name,
        avg_delay_minutes=r.avg_delay_minutes,
        occupancy_pct=r.avg_occupancy_pct,
        on_time_pct=r.on_time_performance_pct,
        performance_category=r.performance_tier
    )
