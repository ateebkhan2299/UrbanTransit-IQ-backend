from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models_db import ForecastResults
from backend.schemas import ForecastResultSchema

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

@router.get("/demand", response_model=List[ForecastResultSchema])
def get_demand_forecast(route_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(ForecastResults)
    if route_id:
        query = query.filter(ForecastResults.route_id == route_id)
    forecasts = query.all()
    return forecasts
