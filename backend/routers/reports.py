from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from backend.database import get_db
import csv
import io
import re

from backend.models_db import (
    DelaySummary,
    ForecastResults,
    ModelMetrics,
    OccupancySummary,
    PassengerFlowSummary,
    RouteGeo,
    RouteSummary,
    RouteStop,
    Stop,
    StopHotspot,
)
from backend.routers.auth import require_roles

router = APIRouter(prefix="/api/reports", tags=["reports"])

VALID_REPORT_TYPES = [
    "route_performance",
    "routes",
    "passenger_demand",
    "flow",
    "delays",
    "occupancy",
    "forecasting",
    "recommendations",
    "stop_performance",
    "route_clustering",
    "model_comparison",
    "model_metrics",
]

SUPPORTED_FORMATS = ["csv", "json"]


def _safe_name(value: str) -> str:
    """Strip anything outside [A-Za-z0-9_-] for the Content-Disposition header."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)[:64]


def _render(rows, headers, fmt: str, name: str):
    output = io.StringIO()
    if fmt == "json":
        import json

        payload = [dict(zip(headers, row)) for row in rows]
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        media_type = "application/json"
        ext = "json"
    else:
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        body = output.getvalue()
        media_type = "text/csv; charset=utf-8"
        ext = "csv"
    output.close()

    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="urbantransit_{_safe_name(name)}.{ext}"'
        },
    )


def _empty(rows, headers, fmt: str, name: str):
    return _render(rows or [], headers, fmt, name)


@router.get("/export")
def export_csv(
    type: str = Query("routes", description="One of " + ", ".join(VALID_REPORT_TYPES)),
    format: str = Query("csv", description="csv or json"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["Admin", "Operator", "Analyst", "Evaluator"])),
):
    fmt = format if format in SUPPORTED_FORMATS else "csv"

    if type in ("route_performance", "routes"):
        rows = db.query(RouteSummary).order_by(RouteSummary.performance_score.desc()).all()
        headers = ["id", "route_id", "route_name", "transport_mode", "total_trips",
                   "total_passengers", "avg_occupancy_pct", "avg_delay_minutes",
                   "on_time_performance_pct", "performance_score", "performance_tier",
                   "cluster_label", "is_persistently_overcrowded"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    if type in ("passenger_demand", "flow"):
        rows = db.query(PassengerFlowSummary).all()
        headers = ["id", "total_demand", "busiest_stop_name", "computed_at"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    if type == "delays":
        rows = db.query(DelaySummary).all()
        headers = ["id", "cause", "incident_count", "total_delay_minutes",
                   "avg_delay_minutes", "max_delay_minutes", "percentage_share"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    if type == "occupancy":
        rows = db.query(OccupancySummary).limit(500).all()
        headers = ["id", "route_id", "route_name", "hour_of_day", "avg_passengers",
                   "avg_capacity", "avg_occupancy_pct", "overcrowded_trips_count",
                   "underutilized_trips_count", "is_persistently_overcrowded"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    if type == "forecasting":
        rows = db.query(ForecastResults).all()
        headers = ["id", "route_id", "forecast_date", "predicted_passenger_demand",
                   "confidence_lower", "confidence_upper"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    if type == "recommendations":
        rows = db.query(RouteSummary).order_by(RouteSummary.performance_score.asc()).limit(50).all()
        headers = ["route_id", "route_name", "performance_score", "tier",
                   "avg_delay_minutes", "avg_occupancy_pct", "suggested_action", "priority"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    if type == "stop_performance":
        rows = db.query(StopHotspot).order_by(StopHotspot.delay_events.desc()).all()
        headers = ["id", "stop_id", "stop_name", "latitude", "longitude", "delay_events"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    if type == "route_clustering":
        rows = db.query(RouteSummary).filter(RouteSummary.cluster_id.isnot(None)).all()
        headers = ["route_id", "route_name", "performance_score", "avg_occupancy_pct",
                   "avg_delay_minutes", "cluster_id", "cluster_label"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    if type == "model_comparison":
        rows = db.query(ModelMetrics).all()
        headers = ["id", "task_name", "pipeline_type", "model_name",
                   "metrics_json", "created_at", "effective_metric"]
        return _render(rows, headers, fmt, type) if rows else _empty(rows, headers, fmt, type)

    # default: model metrics
    rows = db.query(ModelMetrics).order_by(ModelMetrics.task_name, ModelMetrics.pipeline_type).all()
    headers = ["id", "task_name", "pipeline_type", "model_name", "metrics_json", "created_at"]
    return _render(rows, headers, fmt, "model_metrics") if rows else _empty(rows, headers, fmt, "model_metrics")