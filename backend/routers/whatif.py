from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from backend.database import get_db
from backend.models_db import RouteSummary, WhatIfScenario
from backend.routers.auth import log_audit, require_roles
from backend.schemas import (
    WhatIfSimulateContractRequest,
    WhatIfSimulateContractResponse,
    WhatIfSimulateMetrics,
    WhatIfScenarioOut
)

router = APIRouter(prefix="/api/whatif", tags=["whatif"])

@router.get("/scenarios", response_model=List[WhatIfScenarioOut])
def list_whatif_scenarios(limit: int = 20, db: Session = Depends(get_db), current_user = Depends(require_roles(["Admin", "Operator", "Analyst"]))):
    rows = db.query(WhatIfScenario).order_by(WhatIfScenario.id.desc()).limit(limit).all()
    return [
        WhatIfScenarioOut(
            id=r.id,
            scenario_name=r.scenario_name,
            inputs=r.inputs_json or {},
            results=r.results_json or {},
            created_at=str(r.created_at)
        )
        for r in rows
    ]

@router.post("/simulate", response_model=WhatIfSimulateContractResponse)
def simulate_whatif_scenario(
    req: WhatIfSimulateContractRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["Admin", "Operator", "Analyst"])),
):
    route = db.query(RouteSummary).filter(RouteSummary.route_id == req.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {req.route_id} not found")

    base_occ = route.avg_occupancy_pct
    base_delay = route.avg_delay_minutes

    # Baseline metrics
    before = WhatIfSimulateMetrics(
        occupancy_pct=round(base_occ, 1),
        avg_wait_min=round(base_delay * 0.8, 1),
        overcrowd_risk_pct=round(min(100.0, base_occ * 1.1), 1),
        avg_delay_min=round(base_delay, 1)
    )

    # Heuristic model based on change_type
    change_type = req.change_type.lower()
    val = req.change_value
    after_delay = base_delay

    if change_type in ["frequency", "headway"]:
        # Increase frequency reduces wait min and occupancy
        factor = 1.0 + (val / 100.0) if val > 0 else 1.0
        after_occ = max(10.0, base_occ / max(0.5, factor))
        after_wait = max(2.0, before.avg_wait_min / max(0.5, factor))
        after_delay = max(3.0, base_delay / (factor ** 0.5))
    elif change_type in ["capacity", "fleet"]:
        factor = 1.0 + (val / 100.0) if val > 0 else 1.0
        after_occ = max(10.0, base_occ / max(0.5, factor))
        after_wait = before.avg_wait_min
        after_delay = base_delay * 0.98
    elif change_type == "add_trip":
        after_occ = max(10.0, base_occ * 0.85)
        after_wait = max(2.0, before.avg_wait_min * 0.8)
        after_delay = max(3.0, base_delay * 0.85)
    elif change_type == "remove_trip":
        after_occ = min(100.0, base_occ * 1.2)
        after_wait = before.avg_wait_min * 1.25
        after_delay = min(60.0, base_delay * 1.2)
    elif change_type == "shift_start_time":
        # Moving the trip away from a peak slot: load shifts proportionally to the
        # absolute hour change (minutes of headway window moved).
        shift_hours = abs(val) / 60.0
        factor = 1.0 + min(shift_hours, 4.0) * 0.03
        after_occ = min(100.0, max(10.0, base_occ / factor))
        after_wait = max(2.0, before.avg_wait_min / factor)
        after_delay = max(3.0, base_delay * (1.0 - min(shift_hours, 4.0) * 0.02))
    elif change_type == "add_vehicle":
        factor = 1.0 + (max(0.0, val) / 100.0)
        after_occ = max(10.0, base_occ / factor)
        after_wait = max(2.0, before.avg_wait_min / factor)
        after_delay = max(3.0, base_delay / (factor ** 0.5))
    elif change_type == "increase_demand":
        growth = 1.0 + (val / 100.0)
        after_occ = min(100.0, base_occ * growth)
        after_wait = before.avg_wait_min * growth
        after_delay = min(60.0, base_delay * (1.0 + (val / 100.0) * 0.2))
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown change_type '{change_type}'. Supported: "
                "frequency, headway, capacity, fleet, add_trip, remove_trip, "
                "shift_start_time, add_vehicle, increase_demand"
            ),
        )

    after_risk = min(100.0, after_occ * 1.1)

    after = WhatIfSimulateMetrics(
        occupancy_pct=round(after_occ, 1),
        avg_wait_min=round(after_wait, 1),
        overcrowd_risk_pct=round(after_risk, 1),
        avg_delay_min=round(after_delay, 1)
    )

    scenario_record = WhatIfScenario(
        scenario_name=f"Sim_{req.route_id}_{req.change_type}_{req.change_value}",
        inputs_json=req.model_dump(),
        results_json={
            "before": before.model_dump(),
            "after": after.model_dump(),
            "is_estimate": True
        }
    )
    db.add(scenario_record)
    db.commit()
    log_audit(
        db,
        current_user.username,
        current_user.role,
        "SIMULATE_WHAT_IF",
        "/api/whatif/simulate",
        f"Simulated {req.change_type}={req.change_value} for {req.route_id}",
    )

    return WhatIfSimulateContractResponse(
        before=before,
        after=after,
        is_estimate=True
    )
