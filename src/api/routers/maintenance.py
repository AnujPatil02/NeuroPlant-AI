"""
Layer 4 Predictive Maintenance API - RUL prediction, SHAP explanation,
anomaly detection, FFT bearing fault diagnosis. Also exposes Layer 5's
downtime impact calculator since maintenance decisions depend on it.

REVISION: added POST /maintenance/work-order and GET
/maintenance/work-order/{machine_id} -- the "Create Work Order" button on
the Digital Twin Machine Inspector was previously permanently disabled
with no backend endpoint to call at all. Uses work_order_models.py, which
is now confirmed against the real src/layer3_oee/models.py (imports
Base/SessionLocal directly from it, same table metadata as OEERecord/
DowntimeEvent) -- no remaining setup caveats. Run
`python -m src.layer3_oee.models` once to provision the work_orders table
alongside the existing tables if it doesn't already exist.

Note: predict_rul(), predict_anomaly(), and explain_single_machine() all
require their respective models to be trained first (run xgboost_rul.py /
isolation_forest_anomaly.py training scripts, which save to outputs/models/).
This router will 503 with a clear message if a model file is missing,
rather than crash.
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.layer4_predictive_maintenance.xgboost_rul import predict_rul, MODEL_PATH as XGB_MODEL_PATH
from src.layer4_predictive_maintenance.shap_explainer import explain_single_machine
from src.layer4_predictive_maintenance.isolation_forest_anomaly import (
    predict_anomaly, MODEL_PATH as IFOREST_MODEL_PATH
)
from src.layer4_predictive_maintenance.fft_bearing_fault import (
    diagnose_bearing_fault, calculate_fault_frequencies
)
from src.layer5_digital_twin.downtime_impact_calculator import calculate_downtime_impact
from src.layer4_predictive_maintenance.work_order_models import create_work_order, get_work_orders_for_machine

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


class RULRequest(BaseModel):
    machine_id: str
    sensor_readings: dict  # must match xgboost_rul.py's engineered feature_cols


class AnomalyRequest(BaseModel):
    machine_id: str
    sensor_values: dict  # AI4I feature schema: Air temperature [K], Torque [Nm], etc.


class DowntimeImpactRequest(BaseModel):
    machine_id: str
    rul_days: float
    units_per_hour: float
    product_value_per_unit: float
    downstream_dependent_lines: list[str] = []
    cascade_factor: float = 0.5


class WorkOrderRequest(BaseModel):
    machine_id: str
    line_id: str | None = None
    fault_type: str | None = None
    priority_score: float = 0.5
    rul_days: float | None = None
    assigned_technician_slot: str | None = None
    estimated_parts_required: str | None = None
    notes: str | None = None


def _require_model(path: Path, name: str):
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"{name} model not trained yet. Run the corresponding training script first.",
        )


@router.post("/rul")
async def get_rul_prediction(req: RULRequest):
    """Predicts Remaining Useful Life (days) for a machine (e.g. CNC-07)
    from its latest engineered sensor features."""
    _require_model(XGB_MODEL_PATH, "XGBoost RUL")
    try:
        rul = predict_rul(req.sensor_readings)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"RUL prediction failed: {e}")
    return {"machine_id": req.machine_id, "rul_days": round(rul, 1)}


@router.post("/rul/explain")
async def explain_rul(req: RULRequest):
    """Top-3 SHAP drivers behind a machine's RUL prediction."""
    _require_model(XGB_MODEL_PATH, "XGBoost RUL")
    try:
        drivers = explain_single_machine(req.sensor_readings, feature_cols=list(req.sensor_readings.keys()))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SHAP explanation failed: {e}")
    return {"machine_id": req.machine_id, "top_drivers": drivers}


@router.post("/anomaly")
async def check_anomaly(req: AnomalyRequest):
    """Isolation Forest fault check on AI4I-schema sensor values."""
    _require_model(IFOREST_MODEL_PATH, "Isolation Forest")
    try:
        is_anomaly = predict_anomaly(req.sensor_values)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Anomaly check failed: {e}")
    return {"machine_id": req.machine_id, "anomaly": is_anomaly}


@router.get("/bearing-fault-frequencies")
async def get_fault_frequencies(rpm: float):
    """BPFO/BPFI/BSF/FTF fault frequencies for a given shaft RPM
    (CWRU 6205-2RS bearing geometry)."""
    return {"rpm": rpm, "fault_frequencies_hz": calculate_fault_frequencies(rpm)}


@router.post("/downtime-impact")
async def get_downtime_impact(req: DowntimeImpactRequest):
    """Production/revenue loss if a machine fails at predicted RUL,
    with cascade impact on downstream zones (e.g. ZONE_ASSEMBLY)."""
    result = calculate_downtime_impact(
        machine_id=req.machine_id,
        rul_days=req.rul_days,
        units_per_hour=req.units_per_hour,
        product_value_per_unit=req.product_value_per_unit,
        downstream_dependent_lines=req.downstream_dependent_lines,
        cascade_factor=req.cascade_factor,
    )
    return result


@router.post("/work-order")
async def create_maintenance_work_order(req: WorkOrderRequest):
    """Creates a work order for a machine -- backs the Digital Twin's
    Machine Inspector "CREATE WORK ORDER" action, previously a permanently
    disabled button with no endpoint to call."""
    try:
        result = create_work_order(
            machine_id=req.machine_id, line_id=req.line_id, fault_type=req.fault_type,
            priority_score=req.priority_score, rul_days=req.rul_days,
            assigned_technician_slot=req.assigned_technician_slot,
            estimated_parts_required=req.estimated_parts_required, notes=req.notes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Work order creation failed: {e}")
    return result


@router.get("/work-order/{machine_id}")
async def list_machine_work_orders(machine_id: str, status: str | None = None):
    """Lists work orders for a machine (optionally filtered by status) --
    e.g. CNC-07 -- most recent first."""
    try:
        orders = get_work_orders_for_machine(machine_id, status=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch work orders: {e}")
    return {"machine_id": machine_id, "work_orders": orders}