from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Boolean
from datetime import datetime
from backend.database import Base

# --- Phase 2 Management Models ---

class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(String, unique=True, index=True)
    route_name = Column(String)
    transport_mode = Column(String)
    active = Column(Boolean, default=True)

class RouteStop(Base):
    __tablename__ = "route_stops"
    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(String, index=True)
    stop_id = Column(String, index=True)
    stop_sequence = Column(Integer)

class Stop(Base):
    __tablename__ = "stops"
    id = Column(Integer, primary_key=True, index=True)
    stop_id = Column(String, unique=True, index=True)
    stop_name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    zone = Column(String, nullable=True)

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(String, unique=True, index=True)
    transport_mode = Column(String)
    capacity = Column(Integer)
    status = Column(String, default='Active') # 'Active', 'Maintenance', 'Retired'
    last_maintenance = Column(DateTime, nullable=True)

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(String, unique=True, index=True)
    route_id = Column(String, index=True)
    vehicle_id = Column(String, index=True)
    direction = Column(String)
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    status = Column(String, default='Scheduled') # 'Scheduled', 'In Progress', 'Completed', 'Cancelled'

class SparkJobStatus(Base):
    __tablename__ = "spark_job_status"
    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, index=True)
    status = Column(String) # 'Running', 'Success', 'Failed'
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    records_processed = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)

# --- Phase 3 & 4 Analytics / Summary Models ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="Analyst") # 'Admin', 'Operator', 'Analyst', 'Evaluator'
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    role = Column(String)
    action = Column(String)
    endpoint = Column(String)
    details = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class RouteSummary(Base):
    __tablename__ = "route_summaries"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(String, index=True)
    route_name = Column(String)
    transport_mode = Column(String)
    total_trips = Column(Integer)
    total_passengers = Column(Integer)
    avg_occupancy_pct = Column(Float)
    avg_delay_minutes = Column(Float)
    on_time_performance_pct = Column(Float)
    performance_score = Column(Float)
    performance_tier = Column(String)
    cluster_id = Column(Integer, nullable=True)
    cluster_label = Column(String, nullable=True)
    delay_trend_json = Column(JSON, nullable=True)
    occupancy_trend_json = Column(JSON, nullable=True)
    is_persistently_overcrowded = Column(Boolean, default=False)

class DelaySummary(Base):
    __tablename__ = "delay_summaries"

    id = Column(Integer, primary_key=True, index=True)
    cause = Column(String, index=True)
    incident_count = Column(Integer)
    total_delay_minutes = Column(Float)
    avg_delay_minutes = Column(Float)
    max_delay_minutes = Column(Float)
    percentage_share = Column(Float, default=0.0)

class OccupancySummary(Base):
    __tablename__ = "occupancy_summaries"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(String, index=True)
    route_name = Column(String)
    hour_of_day = Column(Integer)
    avg_passengers = Column(Float)
    avg_capacity = Column(Float)
    avg_occupancy_pct = Column(Float)
    overcrowded_trips_count = Column(Integer)
    underutilized_trips_count = Column(Integer)
    is_persistently_overcrowded = Column(Boolean, default=False)


class ForecastResults(Base):
    __tablename__ = "forecast_results"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(String, index=True)
    forecast_date = Column(String)
    predicted_passenger_demand = Column(Float)
    confidence_lower = Column(Float)
    confidence_upper = Column(Float)

class ModelMetrics(Base):
    __tablename__ = "model_metrics"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String, index=True)
    pipeline_type = Column(String)  # 'spark_mllib' or 'python_sklearn'
    model_name = Column(String)
    metrics_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class WhatIfScenario(Base):
    __tablename__ = "whatif_scenarios"

    id = Column(Integer, primary_key=True, index=True)
    scenario_name = Column(String)
    inputs_json = Column(JSON)
    results_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class NotificationAlert(Base):
    __tablename__ = "notification_alerts"

    id = Column(Integer, primary_key=True, index=True)
    severity = Column(String) # 'Critical', 'High', 'Medium', 'Low'
    message = Column(String)
    route_id = Column(String, index=True, nullable=True)
    route_name = Column(String, nullable=True)
    created_at = Column(String)
    is_read = Column(Boolean, default=False)

class PipelineSyncLog(Base):
    __tablename__ = "pipeline_sync_log"

    id = Column(Integer, primary_key=True, index=True)
    last_updated = Column(String)
    status = Column(String) # 'ok', 'error'

class RouteGeo(Base):
    __tablename__ = "route_geos"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(String, index=True, unique=True) # Ensure unique for upsert
    route_name = Column(String)
    status_color = Column(String) # 'normal', 'moderate', 'high'
    path_json = Column(JSON)
    avg_delay = Column(Float, nullable=True)
    avg_occupancy = Column(Float, nullable=True)
    stops_json = Column(JSON, nullable=True) # Holds [{stop_id, stop_name, latitude, longitude, boardings}]

class StopHotspot(Base):
    __tablename__ = "stop_hotspots"

    id = Column(Integer, primary_key=True, index=True)
    stop_id = Column(String, index=True)
    stop_name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    delay_events = Column(Integer)

class PassengerFlowSummary(Base):
    __tablename__ = "passenger_flow_summaries"
    id = Column(Integer, primary_key=True, index=True)
    boarding_alighting_json = Column(JSON)
    od_matrix_json = Column(JSON)
    peak_periods_json = Column(JSON)
    total_demand = Column(Integer)
    busiest_stop_name = Column(String)
    computed_at = Column(DateTime, default=datetime.utcnow)

class DelayAnalysisSummary(Base):
    __tablename__ = "delay_analysis_summaries"
    id = Column(Integer, primary_key=True, index=True)
    # route_delays_json removed per user instruction
    severity_breakdown_json = Column(JSON)
    delay_trend_json = Column(JSON)
    bottlenecks_json = Column(JSON)
    predicted_risks_json = Column(JSON) # Empty array for Phase C
    computed_at = Column(DateTime, default=datetime.utcnow)

class OccupancyDashboardSummary(Base):
    __tablename__ = "occupancy_dashboard_summaries"
    id = Column(Integer, primary_key=True, index=True)
    avg_utilization = Column(Float)
    utilization_change = Column(Float, default=0.0)
    occupancy_trend_json = Column(JSON)
    overcrowded_routes_json = Column(JSON)
    high_risk_trips_json = Column(JSON) # Empty array for Phase C
    computed_at = Column(DateTime, default=datetime.utcnow)
