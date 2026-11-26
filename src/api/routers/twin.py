# twin.py
"""
Layer 5 Digital Twin API — live twin state, production simulation, and
schedule-change testing. This is the contract the React digital-twin app
consumes.

REVISION (Approach A, corrected):
  The previous enrichment copied formatted strings ("68.2°C", "3.5 DAYS",
  "41.0%") straight onto the response. The client's `toNumber()` calls
  Number("3.5 DAYS") which returns NaN, so the inspector showed — for
  every field. The enrichment now parses every shared-table value to a
  RAW NUMBER before writing it onto the response, so the client always
  receives numbers, never formatted strings. Also fixed a key mismatch
  where the shared table uses "current" but the OPC-UA response uses
  "current_draw"; both are now normalized to the same key.
"""
import logging
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.layer5_digital_twin.twin_state import (
    refresh_twin_state, get_twin_state, enrich_with_oee_rul
)
from src.layer5_digital_twin.production_simulator import simulate_production, test_schedule_change
from src.layer5_digital_twin.downtime_impact_calculator import calculate_downtime_impact
from src.layer1_ingestion.synthetic_sensor_generator import load_topology

logger = logging.getLogger("neuroplant.twin")

router = APIRouter(prefix="/twin", tags=["twin"])


# ═══════════════════════════════════════════════════════════════════
# Shared machine health table — imported from the Streamlit page
# ═══════════════════════════════════════════════════════════════════
# This is the SAME dict pages/machine_monitoring.py uses. Values in it
# are formatted STRINGS ("68.2°C", "3.5 DAYS", "41.0%") -- the enrichment
# below parses them to raw numbers before putting them on the response.
_INLINE_MACHINE_HEALTH_STATIC = {
    "CNC-01": {"line": "Component Machining", "status": "online",
               "temp": "44.0°C", "vibration": "2.2 mm/s", "rpm": "2,880",
               "current": "10.8 A", "rul": "118.0 DAYS", "oee": "94.2%"},
    "CNC-02": {"line": "Component Machining", "status": "critical",
               "temp": "68.2°C", "vibration": "4.7 mm/s", "rpm": "2,790",
               "current": "19.4 A", "rul": "3.5 DAYS", "oee": "41.0%"},
    "CNC-03": {"line": "Component Machining", "status": "online",
               "temp": "43.5°C", "vibration": "2.0 mm/s", "rpm": "2,895",
               "current": "10.5 A", "rul": "132.0 DAYS", "oee": "95.1%"},
    "CNC-04": {"line": "Component Machining", "status": "online",
               "temp": "44.2°C", "vibration": "2.3 mm/s", "rpm": "2,870",
               "current": "10.9 A", "rul": "124.0 DAYS", "oee": "94.6%"},
    "CNC-05": {"line": "Precision Machining", "status": "online",
               "temp": "43.8°C", "vibration": "2.1 mm/s", "rpm": "2,910",
               "current": "11.1 A", "rul": "128.0 DAYS", "oee": "95.4%"},
    "CNC-06": {"line": "Precision Machining", "status": "online",
               "temp": "43.2°C", "vibration": "2.0 mm/s", "rpm": "2,905",
               "current": "10.6 A", "rul": "135.0 DAYS", "oee": "95.8%"},
    "CNC-07": {"line": "Precision Machining", "status": "warning",
               "temp": "58.6°C", "vibration": "3.9 mm/s", "rpm": "3,252",
               "current": "11.2 A", "rul": "22.0 DAYS", "oee": "71.4%"},
    "CNC-08": {"line": "Precision Machining", "status": "warning",
               "temp": "56.1°C", "vibration": "3.5 mm/s", "rpm": "3,588",
               "current": "11.5 A", "rul": "15.0 DAYS", "oee": "68.2%"},
    "CNC-09": {"line": "Finishing / Component Processing", "status": "online",
               "temp": "42.9°C", "vibration": "1.9 mm/s", "rpm": "2,920",
               "current": "10.7 A", "rul": "142.0 DAYS", "oee": "91.0%"},
    "CNC-10": {"line": "Finishing / Component Processing", "status": "online",
               "temp": "43.1°C", "vibration": "2.0 mm/s", "rpm": "2,900",
               "current": "10.4 A", "rul": "138.0 DAYS", "oee": "90.2%"},
    "CNC-11": {"line": "Finishing / Component Processing", "status": "online",
               "temp": "44.6°C", "vibration": "2.4 mm/s", "rpm": "2,860",
               "current": "11.0 A", "rul": "112.0 DAYS", "oee": "88.5%"},
    "CNC-12": {"line": "Finishing / Component Processing", "status": "online",
               "temp": "43.6°C", "vibration": "2.1 mm/s", "rpm": "2,890",
               "current": "10.8 A", "rul": "129.0 DAYS", "oee": "88.3%"},
    "ASM-01": {"line": "Automated Assembly", "status": "online",
               "temp": "38.5°C", "vibration": "1.4 mm/s", "rpm": "—",
               "current": "9.8 A", "rul": "150.0 DAYS", "oee": "96.5%"},
}


def _load_shared_health_table() -> dict:
    candidates = [
        "pages.machine_monitoring",
        "dashboard.pages.machine_monitoring",
        "machine_monitoring",
    ]
    for path in candidates:
        try:
            mod = __import__(path, fromlist=["_MACHINE_HEALTH_STATIC"])
            table = getattr(mod, "_MACHINE_HEALTH_STATIC", None)
            if isinstance(table, dict) and table:
                logger.info("Twin enrichment: loaded _MACHINE_HEALTH_STATIC from %s", path)
                return table
        except Exception as e:
            logger.debug("Twin enrichment: import %s failed: %s", path, e)
            continue
    logger.warning(
        "Twin enrichment: using API's inline _MACHINE_HEALTH_STATIC. "
        "If the Streamlit page's shared table changes, mirror it here."
    )
    return _INLINE_MACHINE_HEALTH_STATIC


_SHARED_HEALTH = _load_shared_health_table()


# ── Numeric parsing helpers ────────────────────────────────────────
# The shared table stores formatted strings. The API must return raw
# numbers so the client doesn't have to parse "3.5 DAYS" or "68.2°C".
_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")


def _to_float(value):
    """Parses any numeric-ish value to a Python float, or returns None.
    Handles:
      - raw numbers (int, float) -> returned as-is
      - strings with units ("68.2°C", "3.5 DAYS", "2,790") -> parsed
      - None / "" / "—" -> None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s in ("—", "-", "N/A"):
        return None
    # Remove thousands separators before regex
    s_clean = s.replace(",", "")
    m = _NUM_RE.search(s_clean)
    if not m:
        return None
    try:
        return float(m.group())
    except (ValueError, TypeError):
        return None


def _to_float_pct(value):
    """Same as _to_float but the value is expected to be a percentage
    value already (e.g. "41.0%" -> 41.0). Kept separate so call sites
    are explicit about the semantics."""
    return _to_float(value)


def _enrich_machine(machine_id: str, raw_state: dict) -> dict:
    """Merges OPC-UA readings with the shared health table, returning a
    response where every sensor value is a RAW NUMBER (not a formatted
    string) so the client's MachineInspector can display it directly.

    For flagged machines (CNC-02/07/08) the sensor values are pinned to
    the shared table's values so the twin agrees with every other page.
    """
    if not isinstance(raw_state, dict):
        return raw_state

    shared = _SHARED_HEALTH.get(machine_id)
    enriched = dict(raw_state)

    if shared is None:
        return enriched

    # Status is a string ("online"/"warning"/"critical")
    enriched["status"] = shared.get("status", "online")

    # Line is a string
    enriched["line"] = shared.get("line", "")

    # RUL and OEE come as formatted strings in the shared table
    # ("3.5 DAYS", "41.0%"). Parse to raw numbers so the client can
    # render them without parsing.
    enriched["rul_days"] = _to_float(shared.get("rul"))
    enriched["oee_contribution"] = _to_float_pct(shared.get("oee"))

    # For flagged machines, overwrite the sensor values with the shared
    # table's pinned values (also parsed to raw numbers). This is what
    # makes CNC-02's temperature exactly 68.2, not a fluctuating
    # OPC-UA reading.
    if shared.get("status") in ("critical", "warning"):
        temp = _to_float(shared.get("temp"))
        vib = _to_float(shared.get("vibration"))
        rpm = _to_float(shared.get("rpm"))
        current = _to_float(shared.get("current"))

        if temp is not None:
            enriched["temperature"] = temp
        if vib is not None:
            enriched["vibration"] = vib
        if rpm is not None:
            enriched["rpm"] = rpm
        if current is not None:
            # Normalize key name: OPC-UA uses "current_draw", shared
            # table uses "current". Client expects "current_draw".
            enriched["current_draw"] = current

    return enriched


def _enrich_state(state: dict) -> dict:
    if not state:
        return state
    return {m_id: _enrich_machine(m_id, raw) for m_id, raw in state.items()}


# ═══════════════════════════════════════════════════════════════════
# Pydantic request models
# ═══════════════════════════════════════════════════════════════════

class EnrichRequest(BaseModel):
    machine_id: str
    oee_value: float
    rul_days: float


class SimulateRequest(BaseModel):
    line_id: str
    current_oee: float
    ideal_units_per_hour: float
    horizon_hours: int = 24
    scheduled_downtime_hours: float = 0.0
    machine_health_factor: float = 1.0


class ScheduleTestRequest(BaseModel):
    line_id: str
    baseline_oee: float
    ideal_units_per_hour: float
    proposed_shift_hours: float
    proposed_maintenance_hours: float
    machine_health_factor: float = 1.0


class DowntimeImpactRequest(BaseModel):
    machine_id: str
    rul_days: float
    units_per_hour: float
    product_value_per_unit: float
    downstream_dependent_lines: list[str] = []
    cascade_factor: float = 0.5


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════

@router.get("/plant")
async def get_plant():
    return load_topology()


@router.get("/machines")
async def get_twin_machines():
    state = get_twin_state()
    if not state:
        raise HTTPException(
            status_code=404,
            detail="Twin state is empty. Call POST /twin/refresh first to pull from OPC-UA.",
        )
    return {"machines": _enrich_state(state)}


@router.get("/machines/{machine_id}")
async def get_twin_machine(machine_id: str):
    state = get_twin_state(machine_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"No twin state cached for '{machine_id}'")
    return {"machine_id": machine_id, "state": _enrich_machine(machine_id, state)}


@router.post("/refresh")
async def refresh_twin():
    try:
        state = await refresh_twin_state()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"OPC-UA server unreachable: {e}")
    return {"machines_updated": len(state)}


@router.post("/machines/{machine_id}/enrich")
async def enrich_machine(machine_id: str, req: EnrichRequest):
    enrich_with_oee_rul(machine_id, req.oee_value, req.rul_days)
    return {"machine_id": machine_id, "oee_value": req.oee_value, "rul_days": req.rul_days}


@router.post("/simulation")
async def run_simulation(req: SimulateRequest):
    return simulate_production(
        req.line_id, req.current_oee, req.ideal_units_per_hour,
        req.horizon_hours, req.scheduled_downtime_hours, req.machine_health_factor,
    )


@router.post("/simulation/schedule-test")
async def test_schedule(req: ScheduleTestRequest):
    return test_schedule_change(
        req.line_id, req.baseline_oee, req.ideal_units_per_hour,
        req.proposed_shift_hours, req.proposed_maintenance_hours, req.machine_health_factor,
    )


@router.post("/simulation/downtime-impact")
async def simulate_downtime_impact(req: DowntimeImpactRequest):
    return calculate_downtime_impact(
        req.machine_id, req.rul_days, req.units_per_hour, req.product_value_per_unit,
        req.downstream_dependent_lines, req.cascade_factor,
    )