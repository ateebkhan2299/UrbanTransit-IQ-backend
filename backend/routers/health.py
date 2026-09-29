import time
import os
import psutil
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas import HealthStatusResponse

START_TIME = time.time()

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health", response_model=HealthStatusResponse)
def get_system_health(db: Session = Depends(get_db)):
    db_status = "connected"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    
    uptime = round(time.time() - START_TIME, 2)
    process = psutil.Process(os.getpid())
    mem_mb = round(process.memory_info().rss / (1024 * 1024), 2)

    return HealthStatusResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        uptime_seconds=uptime,
        memory_usage_mb=mem_mb,
        timestamp=datetime.utcnow().isoformat()
    )
