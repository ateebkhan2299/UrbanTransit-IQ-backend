from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import os
import json
from backend.database import get_db
from backend.models_db import ModelMetrics

router = APIRouter(prefix="/api/models", tags=["models"])

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMPARISON_REPORT_PATH = os.path.join(BASE_DIR, "comparison", "model_comparison_report.json")

@router.get("/comparison")
def get_model_comparison():
    if not os.path.exists(COMPARISON_REPORT_PATH):
        raise HTTPException(status_code=404, detail="Model comparison report not found. Run comparison pipeline first.")

    with open(COMPARISON_REPORT_PATH, "r") as f:
        data = json.load(f)
    return data

@router.get("/registry")
def get_model_registry(db: Session = Depends(get_db)):
    rows = db.query(ModelMetrics).order_by(ModelMetrics.task_name, ModelMetrics.pipeline_type).all()
    return [
        {
            "id": r.id,
            "task_name": r.task_name,
            "pipeline_type": r.pipeline_type,
            "model_name": r.model_name,
            "metrics": r.metrics_json or {},
            "created_at": str(r.created_at),
        }
        for r in rows
    ]
