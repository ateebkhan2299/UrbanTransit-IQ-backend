from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class RouteBase(BaseModel):
    route_id: str
    route_name: str
    transport_mode: str
    active: bool = True

class RouteCreate(RouteBase):
    pass

class RouteOut(RouteBase):
    id: int
    class Config:
        from_attributes = True

class StopBase(BaseModel):
    stop_id: str
    stop_name: str
    latitude: float
    longitude: float
    zone: Optional[str] = None

class StopCreate(StopBase):
    pass

class StopOut(StopBase):
    id: int
    class Config:
        from_attributes = True

class VehicleBase(BaseModel):
    vehicle_id: str
    transport_mode: str
    capacity: int
    status: str = 'Active'

class VehicleCreate(VehicleBase):
    pass

class VehicleOut(VehicleBase):
    id: int
    last_maintenance: Optional[datetime] = None
    class Config:
        from_attributes = True

class TripBase(BaseModel):
    trip_id: str
    route_id: str
    vehicle_id: str
    direction: str
    status: str = 'Scheduled'

class TripCreate(TripBase):
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None

class TripOut(TripBase):
    id: int
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    class Config:
        from_attributes = True

class SparkJobStatusOut(BaseModel):
    id: int
    job_name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    records_processed: Optional[int] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

class RouteStopBase(BaseModel):
    route_id: str
    stop_id: str
    stop_sequence: int

class RouteStopCreate(RouteStopBase):
    pass

class RouteStopOut(RouteStopBase):
    id: int
    stop_name: Optional[str] = None
    class Config:
        from_attributes = True
