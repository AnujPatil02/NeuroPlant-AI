"""
Layer 8 Quality Intelligence API — quality KPIs, fault classification,
and contrastive SHAP explanations for flagged faults.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.layer8_quality_intelligence.quality_kpi import compute_quality_kpis, defect_rate_by_type
from src.layer8_quality_intelligence.fault_classifier import classify_quality_faults, FAULT_TYPE_LIBRARY
from src.layer8_quality_intelligence.shap_contrastive_explainer import generate_contrastive_explanation

router = APIRouter(prefix="/quality", tags=["quality"])


class QualityKPIRequest(BaseModel):
    total_units: int
    good_units: int
    scrapped_units: int
    reworked_units: int


class QualityRecord(BaseModel):
    machine_id: str
    shift: str
    product_sku: str
    dimension_mm: float
    surface_finish_ra: float
    weight_g: float


class ClassifyFaultsRequest(BaseModel):
    records: list[QualityRecord]
    contamination: float = 0.05


class DefectRecord(BaseModel):
    defect_type: str


class ContrastiveExplainRequest(BaseModel):
    machine_id: str
    fault_type: str
    fault_record: dict
    normal_baseline_records: list[dict]
    feature_cols: list[str]


@router.post("/kpis")
async def get_quality_kpis(req: QualityKPIRequest):
    """First-pass yield, scrap rate, rework % for a shift/line batch."""
    result = compute_quality_kpis(
        total_units=req.total_units,
        good_units=req.good_units,
        scrapped_units=req.scrapped_units,
        reworked_units=req.reworked_units,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/faults/classify")
async def classify_faults(req: ClassifyFaultsRequest):
    """Isolation Forest fault flagging across dimension/surface-finish/weight.
    e.g. CNC-07 producing SKU-118 on evening shift -> dimensional_variance."""
    records = [r.model_dump() for r in req.records]
    flagged = classify_quality_faults(records, contamination=req.contamination)
    return {"flagged_faults": flagged, "fault_type_library": FAULT_TYPE_LIBRARY}


@router.post("/faults/pareto")
async def defect_pareto(defects: list[DefectRecord]):
    """Defect counts by type, sorted desc — for Pareto chart."""
    records = [d.model_dump() for d in defects]
    return {"pareto": defect_rate_by_type(records)}


@router.post("/faults/explain")
async def explain_fault(req: ContrastiveExplainRequest):
    """Contrastive SHAP narrative — e.g. 'CNC-07 dimensional variance fault —
    primary contributor: spindle_rpm deviation...'."""
    try:
        result = generate_contrastive_explanation(
            fault_record=req.fault_record,
            normal_baseline_records=req.normal_baseline_records,
            feature_cols=req.feature_cols,
            machine_id=req.machine_id,
            fault_type=req.fault_type,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Explanation generation failed: {e}")
    return result