import os
import sys
import json
import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import engine, Base, SessionLocal
from backend.models_db import (
    User,
    AuditLog,
    RouteSummary,
    DelaySummary,
    OccupancySummary,
    ForecastResults,
    ModelMetrics,
    WhatIfScenario,
    NotificationAlert,
    PipelineSyncLog,
    RouteGeo,
    StopHotspot,
    Route,
    Stop,
    Vehicle,
    Trip,
    SparkJobStatus
)
from backend.routers.auth import hash_password
from backend.config import (
    OVERCROWDING_THRESHOLD_PCT,
    DELAY_MAJOR_MIN
)
from seed_credentials import get_seed_password, print_seed_credentials

PROCESSED_DIR = "./processed_data"
MODELS_DIR = "./models"
RAW_DIR = "./raw_data"

def populate_database():
    print("=== Phase 1 & 9: Initializing & Populating SQLite Database (Full Auth & Contract) ===")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    try:
        # 0. Populate Default User Accounts (RBAC Roles: Admin, Operator, Analyst, Evaluator)
        seed_passwords = {
            username: get_seed_password(username)
            for username in ("admin", "operator", "analyst", "evaluator")
        }
        default_users = [
            User(
                username="admin",
                email="admin@urbantransit.org",
                hashed_password=hash_password(seed_passwords["admin"]),
                role="Admin",
                full_name="System Operations Director",
                is_active=True
            ),
            User(
                username="operator",
                email="operator@urbantransit.org",
                hashed_password=hash_password(seed_passwords["operator"]),
                role="Operator",
                full_name="Fleet Dispatch Operator",
                is_active=True
            ),
            User(
                username="analyst",
                email="analyst@urbantransit.org",
                hashed_password=hash_password(seed_passwords["analyst"]),
                role="Analyst",
                full_name="Senior Transit Data Scientist",
                is_active=True
            ),
            User(
                username="evaluator",
                email="evaluator@urbantransit.org",
                hashed_password=hash_password(seed_passwords["evaluator"]),
                role="Evaluator",
                full_name="Competition Audit Evaluator",
                is_active=True
            ),
        ]
        for u in default_users:
            db.add(u)
        print_seed_credentials([
            {"username": u.username, "password": seed_passwords[u.username]}
            for u in default_users
        ])
        print("  [DB] Inserted 4 default RBAC user accounts (Admin, Operator, Analyst, Evaluator).")

        # 0.1 Populate Pipeline Sync Log
        sync_log = PipelineSyncLog(
            last_updated=time.strftime("%Y-%m-%d %H:%M:%S"),
            status="ok"
        )
        db.add(sync_log)

        # 1. Populate Route Summaries and Raw Routes
        route_perf_path = os.path.join(PROCESSED_DIR, "summary_route_performance.parquet")
        df_routes = pd.DataFrame()
        if os.path.exists(route_perf_path):
            df_routes = pd.read_parquet(route_perf_path)
            for _, r in df_routes.iterrows():
                r_id = str(r.get("route_id", ""))
                r_short = str(r.get("route_short_name", r_id))
                r_long = str(r.get("route_long_name", f"Line {r_short}"))
                r_name = f"Route {r_short} — {r_long}" if not r_short in r_long else r_long

                route_sum = RouteSummary(
                    route_id=r_id,
                    route_name=r_name,
                    transport_mode=str(r.get("transport_mode", "Bus")),
                    total_trips=int(r.get("total_trips", 500)),
                    total_passengers=int(r.get("total_boardings", r.get("total_passengers", 25000))),
                    avg_occupancy_pct=round(float(r.get("avg_occupancy_pct", 45.0)), 2),
                    avg_delay_minutes=round(float(r.get("avg_delay_minutes", 12.0)), 2),
                    on_time_performance_pct=round(float(r.get("on_time_performance_pct", 85.0)), 2),
                    performance_score=round(float(r.get("performance_score", 75.0)), 2),
                    performance_tier=str(r.get("performance_tier", "Tier B")),
                    cluster_id=int(r.get("cluster_id", 0)) if pd.notnull(r.get("cluster_id")) else 0,
                    cluster_label=f"Cluster {r.get('cluster_id', 0)}"
                )
                db.add(route_sum)
                
                # Raw Route for Management
                raw_route = Route(
                    route_id=r_id,
                    route_name=r_name,
                    transport_mode=str(r.get("transport_mode", "Bus")),
                    active=True
                )
                db.add(raw_route)
            print(f"  [DB] Inserted {len(df_routes)} route summaries and raw routes.")

        # 2. Populate Delay Summaries with percentage_share
        delay_causes_path = os.path.join(PROCESSED_DIR, "summary_delay_causes.parquet")
        if os.path.exists(delay_causes_path):
            df_delays = pd.read_parquet(delay_causes_path)
            grouped_delays = df_delays.groupby("delay_cause").agg({
                "delay_count": "sum",
                "avg_duration_min": "mean"
            }).reset_index()

            total_incidents = grouped_delays["delay_count"].sum() if len(grouped_delays) > 0 else 1

            for _, r in grouped_delays.iterrows():
                cnt = int(r["delay_count"])
                share = round((cnt / total_incidents) * 100.0, 2)
                delay_sum = DelaySummary(
                    cause=str(r["delay_cause"]),
                    incident_count=cnt,
                    total_delay_minutes=round(float(r["avg_duration_min"] * cnt), 2),
                    avg_delay_minutes=round(float(r["avg_duration_min"]), 2),
                    max_delay_minutes=round(float(r["avg_duration_min"] * 1.8), 2),
                    percentage_share=share
                )
                db.add(delay_sum)
            print(f"  [DB] Inserted {len(grouped_delays)} delay cause summaries.")

        # 3. Populate Occupancy Summaries from features_occupancy.parquet
        occ_path = os.path.join(PROCESSED_DIR, "features_occupancy.parquet")
        if os.path.exists(occ_path):
            df_occ = pd.read_parquet(occ_path)
            grouped = df_occ.groupby(["route_id", "hour_of_day"]).agg({
                "current_occupancy": "mean",
                "total_capacity": "mean",
                "occupancy_pct": "mean",
                "is_overcrowded": "sum",
                "is_underutilized": "sum"
            }).reset_index()

            for _, r in grouped.iterrows():
                occ_sum = OccupancySummary(
                    route_id=str(r["route_id"]),
                    route_name=f"Route {r['route_id']}",
                    hour_of_day=int(r["hour_of_day"]),
                    avg_passengers=round(float(r["current_occupancy"]), 1),
                    avg_capacity=round(float(r["total_capacity"]), 1),
                    avg_occupancy_pct=round(float(r["occupancy_pct"]), 2),
                    overcrowded_trips_count=int(r["is_overcrowded"]),
                    underutilized_trips_count=int(r["is_underutilized"])
                )
                db.add(occ_sum)
            print(f"  [DB] Inserted {len(grouped)} occupancy hourly summaries.")

        # 4. Populate Forecast Results
        demand_path = os.path.join(PROCESSED_DIR, "summary_hourly_demand.parquet")
        if os.path.exists(demand_path):
            df_demand = pd.read_parquet(demand_path)
            routes = df_demand["route_id"].unique() if "route_id" in df_demand.columns else ["ROUTE_001", "ROUTE_002"]
            dates = [(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
            forecast_count = 0
            for r_id in routes:
                base_demand = float(df_demand[df_demand["route_id"] == r_id]["total_boardings"].mean()) if "route_id" in df_demand.columns else 1200.0
                if pd.isna(base_demand):
                    base_demand = 1200.0
                for d_idx, d_str in enumerate(dates):
                    pred = round(base_demand * (1.0 + (d_idx * 0.02)), 1)
                    fc = ForecastResults(
                        route_id=str(r_id),
                        forecast_date=d_str,
                        predicted_passenger_demand=pred,
                        confidence_lower=round(pred * 0.9, 1),
                        confidence_upper=round(pred * 1.1, 1)
                    )
                    db.add(fc)
                    forecast_count += 1
            print(f"  [DB] Inserted {forecast_count} forecast result entries.")

        # 5. Populate Model Metrics
        if os.path.exists(MODELS_DIR):
            metrics_files = [f for f in os.listdir(MODELS_DIR) if f.endswith("_metrics.json")]
            for m_file in metrics_files:
                m_path = os.path.join(MODELS_DIR, m_file)
                with open(m_path, "r") as f:
                    content = json.load(f)
                pipeline = "spark_mllib" if m_file.startswith("spark_") else "python_sklearn"
                task = m_file.replace("spark_", "").replace("python_", "").replace("_model_metrics.json", "").replace("_metrics.json", "")

                mm = ModelMetrics(
                    task_name=task,
                    pipeline_type=pipeline,
                    model_name=content.get("model_type", content.get("model_name", task)),
                    metrics_json=content
                )
                db.add(mm)
            print(f"  [DB] Inserted {len(metrics_files)} model metrics entries.")

        # 6. Auto-Generate Pipeline Notification Alerts
        alerts = [
            NotificationAlert(
                severity="High",
                message="Persistent overcrowding detected during 08:00 - 09:00 peak hours.",
                route_id="ROUTE_012",
                route_name="Route 12 — Downtown Express",
                created_at=(datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
                is_read=False
            ),
            NotificationAlert(
                severity="Critical",
                message="Severe delay threshold (>25m) crossed due to Signal Priority Fault.",
                route_id="ROUTE_076",
                route_name="Route 76 — Crosstown Rapid",
                created_at=(datetime.now() - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S"),
                is_read=False
            ),
            NotificationAlert(
                severity="Medium",
                message="Automated passenger counter sensor anomaly flagged and clean-imputed.",
                route_id="ROUTE_084",
                route_name="Route 84 — Metro Feeder",
                created_at=(datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                is_read=True
            ),
            NotificationAlert(
                severity="Low",
                message="Weekly ML Demand Forecast model retraining complete.",
                route_id=None,
                route_name=None,
                created_at=(datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
                is_read=True
            )
        ]
        for a in alerts:
            db.add(a)
        print(f"  [DB] Inserted {len(alerts)} pipeline notification alerts.")

        # 7. Populate Route Geo & Stop Hotspots
        stops_file = os.path.join(RAW_DIR, "stops.csv")
        stops_df = pd.read_csv(stops_file) if os.path.exists(stops_file) else pd.DataFrame()

        # Stop hotspots
        if len(stops_df) > 0:
            for idx, s in stops_df.head(25).iterrows():
                hs = StopHotspot(
                    stop_id=str(s.get("stop_id", f"STOP_{idx+1}")),
                    stop_name=str(s.get("stop_name", f"Station {idx+1}")),
                    latitude=float(s.get("latitude", 40.7128)),
                    longitude=float(s.get("longitude", -74.0060)),
                    delay_events=int((idx + 1) * 7 + 12)
                )
                db.add(hs)
                
                # Raw Stop for Management
                raw_stop = Stop(
                    stop_id=str(s.get("stop_id", f"STOP_{idx+1}")),
                    stop_name=str(s.get("stop_name", f"Station {idx+1}")),
                    latitude=float(s.get("latitude", 40.7128)),
                    longitude=float(s.get("longitude", -74.0060)),
                    zone=f"Zone {idx % 5}"
                )
                db.add(raw_stop)
            print(f"  [DB] Inserted {len(stops_df.head(25))} stop delay hotspots and raw stops.")

        # Route Geos
        if len(df_routes) > 0:
            for idx, r in df_routes.iterrows():
                r_id = str(r.get("route_id", ""))
                avg_d = float(r.get("avg_delay_minutes", 10.0))
                occ = float(r.get("avg_occupancy_pct", 50.0))

                if avg_d >= DELAY_MAJOR_MIN or occ >= OVERCROWDING_THRESHOLD_PCT:
                    status_color = "high"
                elif avg_d >= 15.0 or occ >= 70.0:
                    status_color = "moderate"
                else:
                    status_color = "normal"

                sample_stops = stops_df.sample(min(8, len(stops_df))).to_dict(orient="records") if len(stops_df) > 0 else []
                path = [{"lat": float(st["latitude"]), "lon": float(st["longitude"]), "stop_name": str(st["stop_name"])} for st in sample_stops]

                r_geo = RouteGeo(
                    route_id=r_id,
                    route_name=str(r.get("route_name", f"Route {r_id}")),
                    status_color=status_color,
                    path_json=path
                )
                db.add(r_geo)
                db.add(r_geo)
            print(f"  [DB] Inserted {len(df_routes)} route geospatial paths.")

        # 8. Populate Vehicles & Trips (Mock data)
        for i in range(1, 11):
            v = Vehicle(
                vehicle_id=f"VEH_{i:03d}",
                transport_mode="Bus" if i % 2 == 0 else "Tram",
                capacity=60 if i % 2 == 0 else 120,
                status="Active" if i % 3 != 0 else "Maintenance",
                last_maintenance=datetime.utcnow() - timedelta(days=i*5)
            )
            db.add(v)
            
            t = Trip(
                trip_id=f"TRIP_{i:03d}",
                route_id=f"ROUTE_00{i%3 + 1}",
                vehicle_id=f"VEH_{i:03d}",
                direction="Outbound" if i % 2 == 0 else "Inbound",
                scheduled_start=datetime.utcnow() + timedelta(hours=i),
                scheduled_end=datetime.utcnow() + timedelta(hours=i+1),
                status="Scheduled" if i % 2 == 0 else "In Progress"
            )
            db.add(t)
            
        print(f"  [DB] Inserted mock vehicles and trips.")

        db.commit()
        print("\n[SUCCESS] Database populated with RBAC Accounts & Full Contract Data!")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Database population failed: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    populate_database()
