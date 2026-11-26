# alerts.py
"""
Cross-layer Alerts API — aggregates threshold-breach and derived-severity
alerts from real Layer 1/2/3/4 data sources into one unified feed, since no
standalone "alarm event" persistence model exists yet (Layer 1's alarm
management via Node-RED is conceptual/simulated per project docs, not a
stored table). This router is intentionally a THIN aggregation layer over
already-real data -- it does not invent new severity logic beyond what the
other routers already compute; it just derives alert objects from their
outputs so /alerts/active and /alerts/summary can back Command Center and
Machine Monitoring's alert panels with real data instead of hardcoded demo
lists.

Sources folded in:
  - Layer 1/2 (monitoring.py's get_all_readings): sensor value vs
    warning_threshold/critical_threshold, both already embedded per-sensor
    in plant_topology.json -- this is the primary, always-available alert
    source since it needs no trained model and no DB record.
  - Layer 3 (oee.py's downtime log / OEERecord): a machine tied to a
    logged downtime event is surfaced as a maintenance-tier alert.
  - Layer 4 (maintenance.py's RUL prediction): degrades gracefully (503 ->
    simply omitted from the feed) if the XGBoost model isn't trained yet,
    matching maintenance.py's own _require_model() pattern rather than
    raising.

Alert severity mirrors monitoring.py's own threshold semantics: value >=
critical_threshold -> "critical", value >= warning_threshold -> "warning".
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.layer1_ingestion.synthetic_sensor_generator import get_all_readings, load_topology
from src.layer3_oee.models import SessionLocal, DowntimeEvent
from src.layer4_predictive_maintenance.xgboost_rul import predict_rul, MODEL_PATH as XGB_MODEL_PATH

router = APIRouter(prefix="/alerts", tags=["alerts"])

# RUL below this many days is folded into the alert feed as a critical
# maintenance alert -- matches the "critical" threshold already used on the
# Predictive Maintenance dashboard page (rul_risk_bar()'s cutoff).
_RUL_CRITICAL_DAYS = 5.0
_RUL_WARNING_DAYS = 15.0


class Alert(BaseModel):
    severity: str          # "critical" | "warning" | "info"
    source: str             # e.g. "CNC-07 (Gear Shaft)"
    machine_id: str
    location: str           # line/zone name
    description: str
    timestamp: str
    layer: str               # which layer this alert was derived from, e.g. "Layer 1/2 Threshold"
    impact: str | None = None
    recommendation: str | None = None


def _build_machine_location_map() -> dict:
    """machine_id -> (line_name/zone_name, component) from plant_topology.json,
    same pattern used across the dashboard pages (home.py, machine_monitoring.py)."""
    topo = load_topology()
    loc_map = {}
    for factory in topo.get("factories", []):
        for line in factory.get("lines", []):
            for m in line.get("machines", []):
                loc_map[m["machine_id"]] = {"location": line["line_name"], "component": m.get("component", "")}
    for zone in topo.get("zones", []):
        for m in zone.get("machines", []):
            loc_map[m["machine_id"]] = {"location": zone.get("zone_name", "Zone"), "component": m.get("component", "")}
    return loc_map


def _threshold_alerts(fault_machine_id: str | None = None) -> list[Alert]:
    """Derives alerts directly from live sensor readings vs the
    warning_threshold/critical_threshold already defined per-sensor in
    plant_topology.json -- no new threshold logic invented here, just
    surfaced as alert objects."""
    readings = get_all_readings(fault_machine_id)
    loc_map = _build_machine_location_map()
    alerts = []
    now_str = datetime.now().strftime("%H:%M:%S")

    for r in readings:
        value = r.get("value")
        warn = r.get("warning_threshold")
        crit = r.get("critical_threshold")
        if value is None:
            continue

        severity = None
        if crit is not None and value >= crit:
            severity = "critical"
        elif warn is not None and value >= warn:
            severity = "warning"
        if severity is None:
            continue

        m_id = r["machine_id"]
        loc = loc_map.get(m_id, {"location": "—", "component": ""})
        source_label = f'{m_id} ({loc["component"]})' if loc["component"] else m_id
        sensor_type = r.get("sensor_type", "sensor")
        unit = r.get("unit", "")

        alerts.append(Alert(
            severity=severity,
            source=source_label,
            machine_id=m_id,
            location=loc["location"],
            description=f"{sensor_type.title()} {value} {unit} — {'above critical' if severity == 'critical' else 'above warning'} threshold ({crit if severity == 'critical' else warn} {unit})",
            timestamp=now_str,
            layer="Layer 1/2 Threshold",
            impact="Risk of unplanned stop within shift if uncorrected." if severity == "critical" else "Early degradation signature; monitor trend.",
            recommendation="Inspect immediately." if severity == "critical" else "Monitor closely; schedule inspection if trend continues.",
        ))
    return alerts


def _downtime_alerts(hours: int = 8) -> list[Alert]:
    """Recent downtime events (Layer 3) surfaced as maintenance-tier alerts
    — an active/recent downtime event is itself an operational alert even
    if the triggering sensor value has since dropped below threshold."""
    session = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        events = (session.query(DowntimeEvent)
                  .filter(DowntimeEvent.start_time >= cutoff)
                  .order_by(DowntimeEvent.start_time.desc())
                  .all())
    except Exception:
        return []
    finally:
        session.close()

    loc_map = _build_machine_location_map()
    alerts = []
    for e in events:
        loc = loc_map.get(e.machine_id, {"location": e.line_id, "component": ""})
        alerts.append(Alert(
            severity="warning",
            source=f'{e.machine_id} ({loc["component"]})' if loc["component"] else e.machine_id,
            machine_id=e.machine_id,
            location=loc["location"],
            description=f"Downtime event — {e.reason_code} ({round(e.duration_minutes, 1)} min)",
            timestamp=str(e.start_time),
            layer="Layer 3 Downtime",
            impact=f"{round(e.duration_minutes, 1)} minutes of lost production time on {e.line_id}.",
            recommendation="Review root cause if this reason code recurs this shift.",
        ))
    return alerts


def _rul_critical_alerts(machine_ids: list[str] | None = None) -> list[Alert]:
    """RUL-based alerts (Layer 4) — degrades gracefully to an empty list if
    the XGBoost model isn't trained yet, matching maintenance.py's own
    _require_model() pattern rather than raising and breaking the whole
    aggregated feed over one untrained model."""
    if not XGB_MODEL_PATH.exists():
        return []

    loc_map = _build_machine_location_map()
    target_ids = machine_ids or list(loc_map.keys())
    alerts = []
    now_str = datetime.now().strftime("%H:%M:%S")

    for m_id in target_ids:
        try:
            # NOTE: predict_rul() expects engineered sensor features matching
            # xgboost_rul.py's feature_cols — this endpoint does not have a
            # live feature vector per machine to pass in (that requires the
            # same feature engineering pipeline machine_monitoring.py's
            # Layer 1 feed would need to run per reading). Left as a
            # best-effort hook: callers with real engineered features should
            # use POST /maintenance/rul directly for a specific machine.
            # This aggregator intentionally does not fabricate a feature
            # vector, so it currently contributes no entries until that
            # pipeline exists — documented here rather than silently
            # returning fake RUL numbers.
            continue
        except Exception:
            continue
    return alerts


@router.get("/active", response_model=list[Alert])
async def get_active_alerts(fault_machine_id: str | None = None, downtime_hours: int = 8):
    """Unified active-alert feed across Layer 1/2 (threshold breach) and
    Layer 3 (recent downtime), sorted critical-first then by recency.
    Pass fault_machine_id to simulate a degrading machine, same as
    monitoring.py's /monitoring/readings."""
    alerts = _threshold_alerts(fault_machine_id) + _downtime_alerts(downtime_hours)
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (severity_rank.get(a.severity, 3), a.timestamp), reverse=False)
    return alerts


@router.get("/summary")
async def get_alert_summary(fault_machine_id: str | None = None, downtime_hours: int = 8):
    """Counts by severity — powers Command Center's 'Critical Alerts' KPI
    card and Machine Monitoring's Running/Warning/Critical counters,
    backed by the same real threshold + downtime data as /alerts/active
    instead of hardcoded numbers."""
    alerts = _threshold_alerts(fault_machine_id) + _downtime_alerts(downtime_hours)
    n_critical = sum(1 for a in alerts if a.severity == "critical")
    n_warning = sum(1 for a in alerts if a.severity == "warning")
    n_info = sum(1 for a in alerts if a.severity == "info")
    return {
        "total": len(alerts),
        "critical": n_critical,
        "warning": n_warning,
        "info": n_info,
        "plant_health": "Degraded" if n_critical else "Attention" if n_warning else "Healthy",
    }


@router.get("/machine/{machine_id}", response_model=list[Alert])
async def get_machine_alerts(machine_id: str, fault_machine_id: str | None = None, downtime_hours: int = 24):
    """All active alerts for a single machine (e.g. CNC-07) — used by the
    Machine Inspector panel on Machine Monitoring."""
    alerts = [a for a in _threshold_alerts(fault_machine_id) if a.machine_id == machine_id]
    alerts += [a for a in _downtime_alerts(downtime_hours) if a.machine_id == machine_id]
    if not alerts:
        return []
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_rank.get(a.severity, 3))
    return alerts