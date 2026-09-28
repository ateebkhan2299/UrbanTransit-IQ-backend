from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from backend.database import get_db
from backend.models_db import Route, Stop, Vehicle, Trip, SparkJobStatus, RouteStop
from backend.schemas_admin import (
    RouteCreate, RouteOut,
    StopCreate, StopOut,
    VehicleCreate, VehicleOut,
    TripCreate, TripOut,
    SparkJobStatusOut,
    RouteStopCreate, RouteStopOut
)
from backend.routers.auth import require_roles, log_audit, get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin-management"])

import concurrent.futures

def try_fetch_mongo(collection_name: str, limit: int = 100, timeout_sec: float = 1.5):
    def _query():
        from database.mongo_db import get_collection
        col = get_collection(collection_name)
        return list(col.find({}, {"_id": 0}).limit(limit))

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_query)
            return future.result(timeout=timeout_sec)
    except Exception:
        return []

# --- ROUTES CRUD ---
@router.get("/routes", response_model=List[RouteOut])
def get_routes(db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator", "Analyst"]))):
    # Try fetching from SQLite first for instant responsiveness
    sqlite_routes = db.query(Route).all()
    if sqlite_routes and len(sqlite_routes) > 0:
        return sqlite_routes
        
    mongo_routes = try_fetch_mongo("clean_routes") or try_fetch_mongo("routes")
    if mongo_routes:
        out = []
        for i, r in enumerate(mongo_routes, start=1):
            out.append(RouteOut(
                id=i,
                route_id=str(r.get("route_id", f"ROUTE_{i}")),
                route_name=str(r.get("route_name", r.get("route_long_name", f"Route {i}"))),
                transport_mode=str(r.get("transport_mode", "Bus")),
                active=bool(r.get("active", True))
            ))
        return out
    return []

@router.post("/routes", response_model=RouteOut, status_code=status.HTTP_201_CREATED)
def create_route(route: RouteCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Route).filter(Route.route_id == route.route_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Route with this ID already exists")
    new_route = Route(**route.model_dump())
    db.add(new_route)
    db.commit()
    db.refresh(new_route)
    log_audit(db, current_user.username, current_user.role, "CREATE_ROUTE", "/api/admin/routes", f"Created route {route.route_id}")
    return new_route

@router.put("/routes/{route_id}", response_model=RouteOut)
def update_route(route_id: str, route: RouteCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Route).filter(Route.route_id == route_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")
    for key, value in route.model_dump().items():
        setattr(existing, key, value)
    db.commit()
    db.refresh(existing)
    return existing

@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(route_id: str, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Route).filter(Route.route_id == route_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")
    db.delete(existing)
    db.commit()
    return None


# --- STOPS CRUD ---
@router.get("/stops", response_model=List[StopOut])
def get_stops(db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator", "Analyst"]))):
    sqlite_stops = db.query(Stop).all()
    if sqlite_stops and len(sqlite_stops) > 0:
        return sqlite_stops

    mongo_stops = try_fetch_mongo("clean_stops") or try_fetch_mongo("stops")
    if mongo_stops:
        out = []
        for i, s in enumerate(mongo_stops, start=1):
            out.append(StopOut(
                id=i,
                stop_id=str(s.get("stop_id", f"STOP_{i}")),
                stop_name=str(s.get("stop_name", f"Station {i}")),
                latitude=float(s.get("latitude", 40.7128)),
                longitude=float(s.get("longitude", -74.0060)),
                zone=str(s.get("zone", f"Zone {i % 5}"))
            ))
        return out
    return []

@router.post("/stops", response_model=StopOut, status_code=status.HTTP_201_CREATED)
def create_stop(stop: StopCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Stop).filter(Stop.stop_id == stop.stop_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Stop with this ID already exists")
    new_stop = Stop(**stop.model_dump())
    db.add(new_stop)
    db.commit()
    db.refresh(new_stop)
    log_audit(db, current_user.username, current_user.role, "CREATE_STOP", "/api/admin/stops", f"Created stop {stop.stop_id}")
    return new_stop

@router.put("/stops/{stop_id}", response_model=StopOut)
def update_stop(stop_id: str, stop: StopCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Stop).filter(Stop.stop_id == stop_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Stop not found")
    for key, value in stop.model_dump().items():
        setattr(existing, key, value)
    db.commit()
    db.refresh(existing)
    return existing

@router.delete("/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stop(stop_id: str, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Stop).filter(Stop.stop_id == stop_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Stop not found")
    db.delete(existing)
    db.commit()
    return None

# --- VEHICLES CRUD ---
@router.get("/vehicles", response_model=List[VehicleOut])
def get_vehicles(db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator", "Analyst"]))):
    sqlite_vehicles = db.query(Vehicle).all()
    if sqlite_vehicles and len(sqlite_vehicles) > 0:
        return sqlite_vehicles

    mongo_vehicles = try_fetch_mongo("clean_vehicles") or try_fetch_mongo("vehicles")
    if mongo_vehicles:
        out = []
        for i, v in enumerate(mongo_vehicles, start=1):
            out.append(VehicleOut(
                id=i,
                vehicle_id=str(v.get("vehicle_id", f"VEH_{i:03d}")),
                transport_mode=str(v.get("transport_mode", "Bus")),
                capacity=int(v.get("capacity", 50)),
                status=str(v.get("status", "Active")),
                last_maintenance=datetime.utcnow() - timedelta(days=i*4)
            ))
        return out
    return []

@router.post("/vehicles", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def create_vehicle(vehicle: VehicleCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle.vehicle_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle with this ID already exists")
    new_vehicle = Vehicle(**vehicle.model_dump())
    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)
    log_audit(db, current_user.username, current_user.role, "CREATE_VEHICLE", "/api/admin/vehicles", f"Created vehicle {vehicle.vehicle_id}")
    return new_vehicle

@router.put("/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: str, vehicle: VehicleCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    for key, value in vehicle.model_dump().items():
        setattr(existing, key, value)
    db.commit()
    db.refresh(existing)
    return existing

@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: str, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(existing)
    db.commit()
    return None

# --- TRIPS CRUD ---
@router.get("/trips", response_model=List[TripOut])
def get_trips(db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator", "Analyst"]))):
    sqlite_trips = db.query(Trip).all()
    if sqlite_trips and len(sqlite_trips) > 0:
        return sqlite_trips

    mongo_trips = try_fetch_mongo("clean_trips", limit=100) or try_fetch_mongo("trips", limit=100)
    if mongo_trips:
        out = []
        for i, t in enumerate(mongo_trips, start=1):
            out.append(TripOut(
                id=i,
                trip_id=str(t.get("trip_id", f"TRIP_{i:03d}")),
                route_id=str(t.get("route_id", "ROUTE_001")),
                vehicle_id=str(t.get("vehicle_id", "VEH_001")),
                direction=str(t.get("direction", "Outbound")),
                status=str(t.get("status", "Scheduled")),
                scheduled_start=datetime.utcnow() + timedelta(hours=i),
                scheduled_end=datetime.utcnow() + timedelta(hours=i+1)
            ))
        return out
    return []

@router.post("/trips", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(trip: TripCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Trip).filter(Trip.trip_id == trip.trip_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Trip with this ID already exists")
    new_trip = Trip(**trip.model_dump())
    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)
    log_audit(db, current_user.username, current_user.role, "CREATE_TRIP", "/api/admin/trips", f"Created trip {trip.trip_id}")
    return new_trip

@router.put("/trips/{trip_id}", response_model=TripOut)
def update_trip(trip_id: str, trip: TripCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Trip).filter(Trip.trip_id == trip_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Trip not found")
    for key, value in trip.model_dump().items():
        setattr(existing, key, value)
    db.commit()
    db.refresh(existing)
    return existing

@router.delete("/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: str, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    existing = db.query(Trip).filter(Trip.trip_id == trip_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Trip not found")
    db.delete(existing)
    db.commit()
    return None

# --- SPARK JOBS STATUS ---
@router.get("/spark-jobs", response_model=List[SparkJobStatusOut])
def get_spark_jobs(db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Evaluator"]))):
    return db.query(SparkJobStatus).order_by(SparkJobStatus.start_time.desc()).all()

# --- ROUTE-STOP SEQUENCE CRUD ---
@router.get("/routes/{route_id}/stops", response_model=List[RouteStopOut])
def get_route_stops(route_id: str, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator", "Analyst"]))):
    """Get all stops for a route, ordered by stop_sequence."""
    rows = db.query(RouteStop).filter(RouteStop.route_id == route_id).order_by(RouteStop.stop_sequence).all()
    result = []
    for rs in rows:
        stop = db.query(Stop).filter(Stop.stop_id == rs.stop_id).first()
        result.append(RouteStopOut(
            id=rs.id,
            route_id=rs.route_id,
            stop_id=rs.stop_id,
            stop_sequence=rs.stop_sequence,
            stop_name=stop.stop_name if stop else None
        ))
    return result

@router.put("/routes/{route_id}/stops")
def set_route_stops(route_id: str, stops: List[RouteStopCreate], db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    """Replace the entire stop sequence for a route."""
    db.query(RouteStop).filter(RouteStop.route_id == route_id).delete()
    for s in stops:
        db.add(RouteStop(route_id=route_id, stop_id=s.stop_id, stop_sequence=s.stop_sequence))
    db.commit()
    log_audit(db, current_user.username, current_user.role, "SET_ROUTE_STOPS", f"/api/admin/routes/{route_id}/stops", f"Set {len(stops)} stops for {route_id}")
    return {"detail": f"{len(stops)} stops saved for {route_id}"}

@router.post("/routes/{route_id}/stops", response_model=RouteStopOut, status_code=status.HTTP_201_CREATED)
def add_route_stop(route_id: str, entry: RouteStopCreate, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    """Add a single stop to a route's sequence."""
    rs = RouteStop(route_id=route_id, stop_id=entry.stop_id, stop_sequence=entry.stop_sequence)
    db.add(rs)
    db.commit()
    db.refresh(rs)
    stop = db.query(Stop).filter(Stop.stop_id == entry.stop_id).first()
    log_audit(db, current_user.username, current_user.role, "ADD_ROUTE_STOP", f"/api/admin/routes/{route_id}/stops", f"Added {entry.stop_id} at seq {entry.stop_sequence}")
    return RouteStopOut(id=rs.id, route_id=rs.route_id, stop_id=rs.stop_id, stop_sequence=rs.stop_sequence, stop_name=stop.stop_name if stop else None)

@router.delete("/routes/{route_id}/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_route_stop(route_id: str, stop_id: str, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator"]))):
    """Remove a stop from a route's sequence."""
    rs = db.query(RouteStop).filter(RouteStop.route_id == route_id, RouteStop.stop_id == stop_id).first()
    if not rs:
        raise HTTPException(status_code=404, detail="Stop not found in this route")
    db.delete(rs)
    db.commit()
    log_audit(db, current_user.username, current_user.role, "REMOVE_ROUTE_STOP", f"/api/admin/routes/{route_id}/stops/{stop_id}", f"Removed {stop_id} from {route_id}")
