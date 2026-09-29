import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models_db import (
    RouteSummary, PipelineSyncLog, PassengerFlowSummary,
    DelayAnalysisSummary, OccupancyDashboardSummary, RouteGeo, ForecastResults
)
from backend.schemas import (
    SyncStatusResponse,
    DashboardSummaryContractResponse,
    TopRouteItem
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/sync-status", response_model=SyncStatusResponse)
def get_sync_status(db: Session = Depends(get_db)):
    sync_entry = db.query(PipelineSyncLog).order_by(PipelineSyncLog.id.desc()).first()
    return SyncStatusResponse(
        last_updated=sync_entry.last_updated if sync_entry else "",
        status=sync_entry.status if sync_entry else "unknown",
    )

@router.get("/summary", response_model=DashboardSummaryContractResponse)
def get_dashboard_summary(route_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    # Live aggregation from the SQLite analytics store.
    query = db.query(RouteSummary)
    if route_id:
        query = query.filter(RouteSummary.route_id == route_id)
    routes = query.all()

    total_passengers = sum(r.total_passengers or 0 for r in routes) if routes else 0
    total_trips = sum(r.total_trips or 0 for r in routes) if routes else 0
    counts = len(routes) or 1

    def mean(values):
        vals = [v for v in values if v is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    return DashboardSummaryContractResponse(
        total_passengers=total_passengers,
        total_passengers_change_pct=0.0,
        total_trips=total_trips,
        total_trips_change_pct=0.0,
        avg_occupancy_pct=mean([r.avg_occupancy_pct for r in routes]),
        avg_occupancy_change_pct=0.0,
        avg_delay_minutes=mean([r.avg_delay_minutes for r in routes]),
        on_time_pct=mean([r.on_time_performance_pct for r in routes]),
        on_time_change_pct=0.0,
        overcrowded_routes=sum(1 for r in routes if r.is_persistently_overcrowded),
        overcrowded_routes_change_pct=0.0,
        underutilized_routes=sum(1 for r in routes if r.is_persistently_overcrowded is False
                                and (r.avg_occupancy_pct or 0) < 30),
        routes_analyzed=len(routes),
    )

@router.get("/top-routes", response_model=List[TopRouteItem])
def get_top_routes(limit: int = Query(5), db: Session = Depends(get_db)):
    routes = db.query(RouteSummary).order_by(RouteSummary.total_passengers.desc()).limit(limit).all()
    res = [
        TopRouteItem(
            route_id=r.route_id,
            route_name=r.route_name,
            total_passengers=r.total_passengers,
            occupancy_pct=r.avg_occupancy_pct
        )
        for r in routes
    ]
    return res

@router.get("/passenger-flow")
def get_passenger_flow(db: Session = Depends(get_db)):
    summary = db.query(PassengerFlowSummary).order_by(PassengerFlowSummary.id.desc()).first()
    if summary and summary.boarding_alighting_json:
        return {
            "boarding_alighting": summary.boarding_alighting_json,
            "od_matrix": summary.od_matrix_json,
            "peak_periods": summary.peak_periods_json,
            "total_demand": summary.total_demand,
            "busiest_stop": summary.busiest_stop_name
        }
    
    return {
        "status": "data_unavailable",
        "reason": "Passenger-flow analytics have not been generated. Run the pipeline and populate the serving database.",
    }

@router.get("/route-performance")
def get_route_performance(db: Session = Depends(get_db)):
    summaries = [s for s in db.query(RouteSummary).all() if s.performance_score is not None]
    if not summaries:
        return {
            "status": "data_unavailable",
            "reason": "Route-performance analytics have not been generated. Run the pipeline and populate the serving database.",
        }

    def quantile(values, p):
        vals = sorted(values)
        return vals[min(len(vals) - 1, int(p * len(vals)))]

    delays = [s.avg_delay_minutes or 0.0 for s in summaries]
    occs = [s.avg_occupancy_pct or 0.0 for s in summaries]
    scores = [s.performance_score for s in summaries]
    d_med = quantile(delays, 0.5)
    o_lo, o_hi = quantile(occs, 0.30), quantile(occs, 0.70)
    s_lo, s_hi = quantile(scores, 0.25), quantile(scores, 0.75)

    routes = []
    for s in summaries:
        delay = s.avg_delay_minutes or 0.0
        occ = s.avg_occupancy_pct or 0.0
        score = s.performance_score
        if occ >= o_hi and delay >= d_med:
            category = "High-Demand-but-Unreliable"
        elif occ >= o_hi:
            category = "Overcrowded"
        elif occ <= o_lo and delay <= d_med:
            category = "Reliable-but-Underutilized"
        elif score <= s_lo:
            category = "Low Performing"
        elif score >= s_hi:
            category = "High Performing"
        else:
            category = "Balanced"

        routes.append({
            "route_id": s.route_id,
            "route_name": s.route_name,
            "transport_mode": s.transport_mode,
            "performance_score": score,
            "avg_delay": round(delay, 1),
            "occupancy_pct": round(occ, 1),
            "reliability_pct": s.on_time_performance_pct,
            "total_passengers": s.total_passengers,
            "total_trips": s.total_trips,
            "tier": s.performance_tier,
            "cluster_label": s.cluster_label,
            "category": category,
            "delay_trend": [{"value": v} for v in (s.delay_trend_json or [])],
            "occupancy_trend": [{"value": v} for v in (s.occupancy_trend_json or [])],
        })

    return {
        "routes": routes,
        "thresholds": {
            "delay_median": round(d_med, 1),
            "delay_low": round(quantile(delays, 0.25), 1),
            "delay_high": round(quantile(delays, 0.75), 1),
            "occupancy_low": round(o_lo, 1),
            "occupancy_high": round(o_hi, 1),
        },
    }

@router.get("/delays")
def get_delays(db: Session = Depends(get_db)):
    summary = db.query(DelayAnalysisSummary).order_by(DelayAnalysisSummary.id.desc()).first()
    if not summary:
        return {}
    
    # We read route_delays directly from RouteSummary per user instructions
    route_summaries = db.query(RouteSummary).order_by(RouteSummary.avg_delay_minutes.desc()).all()
    route_delays = [{"route_id": r.route_id, "avg_delay": r.avg_delay_minutes} for r in route_summaries]

    return {
        "route_delays": route_delays,
        "severity_breakdown": json.loads(summary.severity_breakdown_json) if isinstance(summary.severity_breakdown_json, str) else summary.severity_breakdown_json,
        "delay_trend": json.loads(summary.delay_trend_json) if isinstance(summary.delay_trend_json, str) else summary.delay_trend_json,
        "bottlenecks": json.loads(summary.bottlenecks_json) if isinstance(summary.bottlenecks_json, str) else summary.bottlenecks_json,
        "predicted_risks": json.loads(summary.predicted_risks_json) if isinstance(summary.predicted_risks_json, str) else summary.predicted_risks_json
    }

@router.get("/occupancy")
def get_occupancy(db: Session = Depends(get_db)):
    summary = db.query(OccupancyDashboardSummary).order_by(OccupancyDashboardSummary.id.desc()).first()
    if not summary:
        return {}
    return {
        "avg_utilization": summary.avg_utilization,
        "utilization_change": summary.utilization_change,
        "occupancy_trend": json.loads(summary.occupancy_trend_json) if isinstance(summary.occupancy_trend_json, str) else summary.occupancy_trend_json,
        "overcrowded_routes": json.loads(summary.overcrowded_routes_json) if isinstance(summary.overcrowded_routes_json, str) else summary.overcrowded_routes_json,
        "high_risk_trips": json.loads(summary.high_risk_trips_json) if isinstance(summary.high_risk_trips_json, str) else summary.high_risk_trips_json
    }

@router.get("/forecast")
def get_forecast(db: Session = Depends(get_db)):
    rows = db.query(ForecastResults).order_by(ForecastResults.forecast_date).all()
    if not rows:
        return {
            "status": "data_unavailable",
            "reason": "No forecast results in the serving database. Populate forecast_results first.",
        }

    by_date = {}
    for r in rows:
        by_date.setdefault(r.forecast_date, []).append(r)

    dates = sorted(by_date.keys())
    daily = {
        "dates": dates,
        "predicted": [round(sum(x.predicted_passenger_demand for x in by_date[d]), 2) for d in dates],
        "lower": [round(sum(x.confidence_lower for x in by_date[d]), 2) for d in dates],
        "upper": [round(sum(x.confidence_upper for x in by_date[d]), 2) for d in dates],
    }
    routes_series = {}
    for r in rows:
        routes_series.setdefault(r.route_id, []).append({
            "date": r.forecast_date,
            "predicted": r.predicted_passenger_demand,
            "lower": r.confidence_lower,
            "upper": r.confidence_upper,
        })
    for rid in routes_series:
        routes_series[rid].sort(key=lambda x: x["date"])

    return {
        "status": "ok",
        "horizon_days": len(dates),
        "routes_forecasted": sorted(routes_series.keys()),
        "total_routes": len(routes_series),
        "daily": daily,
        "routes": routes_series,
        "metrics": _forecast_metrics(db),
        "series": [
            {"time": d, "historical": None, "forecast": p, "actual": None}
            for d, p in zip(dates, daily["predicted"])
        ],
    }

def _forecast_metrics(db):
    """Best-quality metrics from the model registry, else nulls."""
    row = _best_forecast_metric(db)
    if row is None:
        return {"mae": None, "rmse": None, "accuracy": None, "predicted_peak": None}
    return {
        "mae": row.get("mae"),
        "rmse": row.get("rmse"),
        "accuracy": row.get("accuracy"),
        "predicted_peak": row.get("predicted_peak"),
    }

def _best_forecast_metric(db):
    from backend.models_db import ModelMetrics
    rows = db.query(ModelMetrics).filter(ModelMetrics.task_name == "forecast").all()
    best = None
    for r in rows:
        try:
            m = r.metrics_json or {}
            if not isinstance(m, dict):
                continue
            algs = m.get("trained_algorithms") or {}
            cand = None
            for name, metrics in algs.items():
                if isinstance(metrics, dict) and metrics.get("r2") is not None:
                    if cand is None or metrics.get("r2", -1) > cand.get("r2", -1):
                        cand = metrics
            if cand is None and m.get("best"):
                cand = m["best"]
            if cand and (best is None or cand.get("r2", -1) > best.get("r2", -1)):
                best = cand
        except Exception:
            continue
    if best is None:
        return None
    r2 = best.get("r2")
    accuracy = round(max(0.0, min(100.0, r2 * 100)), 2) if r2 is not None else None
    peak = _forecast_peak_date(db)
    return {
        "mae": round(best.get("mae"), 2) if best.get("mae") is not None else None,
        "rmse": round(best.get("rmse"), 2) if best.get("rmse") is not None else None,
        "accuracy": accuracy,
        "predicted_peak": peak,
    }

def _forecast_peak_date(db):
    from backend.models_db import ForecastResults
    row = db.query(ForecastResults).order_by(ForecastResults.predicted_passenger_demand.desc()).first()
    return row.forecast_date if row else None

@router.get("/route-geo")
def get_route_geo(db: Session = Depends(get_db)):
    route_geos = db.query(RouteGeo).all()
    if not route_geos:
        return {}
    
    routes = []
    # Collect all unique stops from the routes
    all_stops_dict = {}
    for r in route_geos:
        routes.append({
            "route_id": r.route_id,
            "route_name": r.route_name,
            "status": r.status_color,
            "path": r.path_json,
            "avg_delay": r.avg_delay,
            "avg_occupancy": r.avg_occupancy
        })
        if r.stops_json:
            for s in r.stops_json:
                all_stops_dict[s["stop_id"]] = {
                    "stop_id": s["stop_id"],
                    "stop_name": s["stop_name"],
                    "latitude": s["latitude"],
                    "longitude": s["longitude"],
                    "boardings": s.get("boardings", 0)
                }
    
    stops = list(all_stops_dict.values())

    return {
        "routes": routes,
        "stops": stops
    }
