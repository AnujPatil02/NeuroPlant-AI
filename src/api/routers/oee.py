"""
Layer 3 OEE Analytics API — compute/store/retrieve OEE, downtime Pareto.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.layer3_oee.oee_calculator import compute_and_store_oee
from src.layer3_oee.downtime_classifier import log_downtime, get_downtime_pareto, VALID_REASON_CODES
from src.layer3_oee.models import SessionLocal, OEERecord

router = APIRouter(prefix="/oee", tags=["oee"])


class ComputeOEERequest(BaseModel):
    factory_id: str
    line_id: str
    planned_minutes: float
    total_units: int
    good_units: int
    product_sku: str
    # FIX: added so callers can specify which shift window Availability's
    # downtime lookup is scoped to (see oee_calculator.py's fix). Optional
    # -- when omitted, compute_and_store_oee() defaults to the
    # planned_minutes immediately preceding "now".
    shift_start: datetime | None = None
    shift_end: datetime | None = None


class LogDowntimeRequest(BaseModel):
    factory_id: str
    line_id: str
    machine_id: str
    reason_code: str
    start_time: datetime
    end_time: datetime


@router.post("/compute")
async def compute_oee(req: ComputeOEERequest):
    """Computes Availability x Performance x Quality and stores the record.
    product_sku must exist in sku_cycle_times (run seed_sku_cycle_times.py first)."""
    result = compute_and_store_oee(
        factory_id=req.factory_id,
        line_id=req.line_id,
        planned_minutes=req.planned_minutes,
        total_units=req.total_units,
        good_units=req.good_units,
        product_sku=req.product_sku,
        shift_start=req.shift_start,
        shift_end=req.shift_end,
    )
    return result


@router.get("/latest/{line_id}")
async def get_latest_oee(line_id: str, limit: int = 1):
    """Most recent OEE record(s) for a line — e.g. LINE02."""
    session = SessionLocal()
    records = (
        session.query(OEERecord)
        .filter(OEERecord.line_id == line_id)
        .order_by(OEERecord.timestamp.desc())
        .limit(limit)
        .all()
    )
    session.close()
    if not records:
        raise HTTPException(status_code=404, detail=f"No OEE records found for line '{line_id}'")
    return {
        "line_id": line_id,
        "records": [
            {
                "timestamp": str(r.timestamp),
                "availability": r.availability,
                "performance": r.performance,
                "quality": r.quality,
                "oee": r.oee,
            }
            for r in records
        ],
    }


@router.post("/downtime")
async def report_downtime(req: LogDowntimeRequest):
    """Logs a downtime event (e.g. CNC-06 coolant pump alarm on LINE02)."""
    if req.reason_code not in VALID_REASON_CODES:
        raise HTTPException(status_code=400, detail=f"Invalid reason_code. Must be one of {VALID_REASON_CODES}")
    duration = log_downtime(
        factory_id=req.factory_id,
        line_id=req.line_id,
        machine_id=req.machine_id,
        reason_code=req.reason_code,
        start_time=req.start_time,
        end_time=req.end_time,
    )
    return {"duration_minutes": round(duration, 2)}


@router.get("/downtime/pareto/{line_id}")
async def downtime_pareto(line_id: str, days: int = 7):
    """Downtime minutes grouped by reason code, sorted desc — for Pareto chart."""
    pareto = get_downtime_pareto(line_id, days=days)
    if not pareto:
        return {"line_id": line_id, "pareto": {}, "message": "No downtime events in range"}
    return {"line_id": line_id, "pareto": pareto}