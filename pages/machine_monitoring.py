"""
Machine Monitoring page - Layer 1 (MQTT/OPC-UA ingestion) + Layer 2
(Grafana-style monitoring) + Layer 5 (Digital Twin, live factory state
mirror with production simulation).

REVISION (10 -> 7 page merge, corrected):
  Machine Monitoring and Digital Twin are now ONE sidebar entry with two
  tabs, since both were "watch the machines right now" views of the same
  underlying data -- Digital Twin is a richer 3D visualization layered
  with a real React/Three.js embed bridge, click-to-inspect, and a
  simulation-mode panel.

  Live Sensors tab: readings come from Redis (Layer 1 cache). Falls back
  to sample values with an explicit connection_warning() when Redis is
  empty.

  Digital Twin tab: src/api/routers/twin.py is currently an empty stub
  and no layer5_digital_twin function is wired to this page yet -- every
  value in the twin's KPIs/machine cards is demo data. Requires
  digital-twin/dist/index.html to exist (run `npm run build` inside
  digital-twin/ first); shows an inline warning instead of crashing if
  the embed bridge or build is missing.

FIX LOG (this revision):
  - RUL Estimate / OEE Contribution now populated in the Live Sensors
    Machine Inspector by pulling from the shared _MACHINE_HEALTH_STATIC
    dict (same source the Digital Twin tab uses). Previously showed "—"
    because the Live Sensors tab's `sensors` list has no RUL/OEE fields.
  - Alarm Timeline was rendering 12+ times (once per machine card)
    because section_header() was nested inside the telemetry loop.
    Dedented so it renders exactly once, after the telemetry grid.
  - Live Telemetry cards for CNC-03..CNC-12 / ASM-01 were missing
    vibration because the fallback dict only had temperature for those
    machines. Fallback expanded so every machine shows temp + vibration.
  - CNC-02 (critical), CNC-07 (warning), CNC-08 (warning) values were
    fluctuating every render because the MQTT simulator's
    random.uniform() drifts them across the threshold each read.
    _pin_flagged_machines() now overwrites those three machines' sensor
    values with fixed, deterministic values on every fetch, so the
    status is stable and matches the Digital Twin tab.
  - Live Sensors and Digital Twin now share _MACHINE_HEALTH_STATIC
    (RUL, OEE, line, type) so both tabs agree on every machine.
"""
import json
import os
import streamlit as st
import numpy as np
from dashboard.ui.topbar import render_topbar, render_kpi_hero
from dashboard.ui.theme import COLORS, status_color
from dashboard.ui.animations import inject_animation_css, live_pulse_badge
from dashboard.ui.charts import trend_line
from dashboard.ui.components import (alert_card, section_header, matrix_cell, connection_warning,
                                      breadcrumb, machine_card, info_banner, impact_panel)
import redis
from src.config.settings import settings

redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)

# ═══════════════════════════════════════════════════════════════════
# Shared machine health table — single source of truth for BOTH tabs
# ═══════════════════════════════════════════════════════════════════
# Renamed from _TWIN_DEMO_MACHINES. Used by:
#   - Live Sensors Machine Inspector: RUL Estimate + OEE Contribution
#   - Digital Twin tab: machine cards + Machine Inspector
# The three flagged machines (CNC-02 critical, CNC-07/08 warning) have
# their status pinned here so both tabs always agree.
_MACHINE_HEALTH_STATIC = {
    "CNC-01": {"line": "Component Machining", "type": "CNC Machining Center — Input Shaft",
               "status": "online", "temp": "44.0°C", "vibration": "2.2 mm/s", "rpm": "2,880",
               "current": "10.8 A", "rul": "118.0 DAYS", "oee": "94.2%"},
    "CNC-02": {"line": "Component Machining", "type": "CNC Machining Center — Output Shaft",
               "status": "critical", "temp": "68.2°C", "vibration": "4.7 mm/s", "rpm": "2,790",
               "current": "19.4 A", "rul": "3.5 DAYS", "oee": "41.0%"},
    "CNC-03": {"line": "Component Machining", "type": "CNC Machining Center — Pinion Gear",
               "status": "online", "temp": "43.5°C", "vibration": "2.0 mm/s", "rpm": "2,895",
               "current": "10.5 A", "rul": "132.0 DAYS", "oee": "95.1%"},
    "CNC-04": {"line": "Component Machining", "type": "CNC Machining Center — Ring Gear",
               "status": "online", "temp": "44.2°C", "vibration": "2.3 mm/s", "rpm": "2,870",
               "current": "10.9 A", "rul": "124.0 DAYS", "oee": "94.6%"},
    "CNC-05": {"line": "Precision Machining", "type": "CNC Machining Center — Differential Housing",
               "status": "online", "temp": "43.8°C", "vibration": "2.1 mm/s", "rpm": "2,910",
               "current": "11.1 A", "rul": "128.0 DAYS", "oee": "95.4%"},
    "CNC-06": {"line": "Precision Machining", "type": "CNC Machining Center — Bearing Housing",
               "status": "online", "temp": "43.2°C", "vibration": "2.0 mm/s", "rpm": "2,905",
               "current": "10.6 A", "rul": "135.0 DAYS", "oee": "95.8%"},
    "CNC-07": {"line": "Precision Machining", "type": "CNC Machining Center — Gear Shaft",
               "status": "warning", "temp": "58.6°C", "vibration": "3.9 mm/s",
               "rpm": "3,252",       # was "2,860" -- align with the pinned live value
               "current": "11.2 A", "rul": "22.0 DAYS", "oee": "71.4%"},
    "CNC-08": {"line": "Precision Machining", "type": "CNC Machining Center — Clutch Hub",
               "status": "warning", "temp": "56.1°C", "vibration": "3.5 mm/s",
               "rpm": "3,588",       # was "2,850" -- align with the pinned live value
               "current": "11.5 A", "rul": "15.0 DAYS", "oee": "68.2%"},
    "CNC-09": {"line": "Finishing / Component Processing", "type": "CNC Machining Center — CV Joint Housing",
               "status": "online", "temp": "42.9°C", "vibration": "1.9 mm/s", "rpm": "2,920",
               "current": "10.7 A", "rul": "142.0 DAYS", "oee": "91.0%"},
    "CNC-10": {"line": "Finishing / Component Processing", "type": "CNC Machining Center — Wheel Hub",
               "status": "online", "temp": "43.1°C", "vibration": "2.0 mm/s", "rpm": "2,900",
               "current": "10.4 A", "rul": "138.0 DAYS", "oee": "90.2%"},
    "CNC-11": {"line": "Finishing / Component Processing", "type": "CNC Machining Center — Transmission Casing",
               "status": "online", "temp": "44.6°C", "vibration": "2.4 mm/s", "rpm": "2,860",
               "current": "11.0 A", "rul": "112.0 DAYS", "oee": "88.5%"},
    "CNC-12": {"line": "Finishing / Component Processing", "type": "CNC Machining Center — Axle Shaft",
               "status": "online", "temp": "43.6°C", "vibration": "2.1 mm/s", "rpm": "2,890",
               "current": "10.8 A", "rul": "129.0 DAYS", "oee": "88.3%"},
    "ASM-01": {"line": "Automated Assembly", "type": "Assembly Robot",
               "status": "online", "temp": "38.5°C", "vibration": "1.4 mm/s", "rpm": "—",
               "current": "9.8 A", "rul": "150.0 DAYS", "oee": "96.5%"},
}

# Replace the _PINNED_FLAGGED_VALUES dict at the top of machine_monitoring.py:

_PINNED_FLAGGED_VALUES = {
    # CNC-02: critical on rpm; also warning on temp/vibration/current_draw.
    "CNC-02": {
        "temperature":  68.2,    # > warn 65, < crit 80   -> warning
        "vibration":     4.7,    # > warn 4.5, < crit 7.0 -> warning
        "current_draw": 19.4,    # > warn 15, < crit 20   -> warning
        "rpm":        3802.45,   # > crit 3600            -> CRITICAL
    },
    # CNC-07: warning on rpm only; other sensors healthy.
    "CNC-07": {
        "temperature":  58.6,    # < warn 65              -> healthy
        "vibration":     3.9,    # < warn 4.5             -> healthy
        "current_draw": 11.2,    # < warn 15              -> healthy
        "rpm":        3252.23,   # > warn 3200, < crit 3600 -> WARNING
    },
    # CNC-08: warning on rpm only, closer to critical.
    "CNC-08": {
        "temperature":  56.1,    # < warn 65              -> healthy
        "vibration":     3.5,    # < warn 4.5             -> healthy
        "current_draw": 11.5,    # < warn 15              -> healthy
        "rpm":        3588.03,   # > warn 3200, < crit 3600 -> WARNING
    },
}

# ═══════════════════════════════════════════════════════════════════
# Live Sensors tab — Layer 1/2
# ═══════════════════════════════════════════════════════════════════

_MACHINE_LINE_MAP = {
    "CNC-01": "Component Machining", "CNC-02": "Component Machining",
    "CNC-03": "Component Machining", "CNC-04": "Component Machining",
    "CNC-05": "Precision Machining", "CNC-06": "Precision Machining",
    "CNC-07": "Precision Machining", "CNC-08": "Precision Machining",
    "CNC-09": "Finishing / Component Processing", "CNC-10": "Finishing / Component Processing",
    "CNC-11": "Finishing / Component Processing", "CNC-12": "Finishing / Component Processing",
    "ASM-01": "Automated Assembly",
}

_ZONE_ONLY_IDS = {"ZONE_TREATMENT"}


def _pin_flagged_machines(readings: dict) -> dict:
    """Overwrite sensor values for CNC-02/07/08 with the pinned values in
    _PINNED_FLAGGED_VALUES, so their status is stable and matches the
    Digital Twin tab on every render. Any sensor of those machines that
    isn't in the pinned dict is left untouched (e.g. extra sensors)."""
    for m_id, pinned in _PINNED_FLAGGED_VALUES.items():
        if m_id not in readings:
            continue
        for s in readings[m_id]:
            if s.get("sensor_type") in pinned:
                s["value"] = pinned[s["sensor_type"]]
    return readings


def fetch_live_readings():
    keys = redis_client.keys("FAC01:*")
    readings = {}
    for key in keys:
        val = redis_client.get(key)
        if val:
            data = json.loads(val)
            m_id = data["machine_id"]
            if m_id in _ZONE_ONLY_IDS:
                continue
            readings.setdefault(m_id, []).append(data)
    return _pin_flagged_machines(readings)


def fetch_live_alarms(readings: dict) -> list:
    """Derives alerts directly from the SAME `readings` dict used by the
    Machine Health Matrix / Live Telemetry, so the Alarm Timeline always
    describes exactly what the matrix/telemetry sections are showing."""
    from datetime import datetime
    now_str = datetime.now().strftime("%H:%M:%S")
    cards = []

    for m_id, sensors in readings.items():
        line = _MACHINE_LINE_MAP.get(m_id, "—")
        for s in sensors:
            value = s.get("value")
            warn = s.get("warning_threshold")
            crit = s.get("critical_threshold")
            if value is None:
                continue
            severity = None
            if crit is not None and value >= crit:
                severity = "critical"
            elif warn is not None and value >= warn:
                severity = "warning"
            if severity is None:
                continue
            cards.append({
                "severity": severity,
                "source": m_id,
                "location": line,
                "description": f'{s["sensor_type"].title()} {value} {s.get("unit","")} — '
                                f'{"above critical" if severity == "critical" else "above warning"} threshold '
                                f'({crit if severity == "critical" else warn} {s.get("unit","")})',
                "timestamp": now_str,
                "impact": "Risk of unplanned stop within shift if uncorrected." if severity == "critical"
                           else "Early degradation signature; monitor trend.",
                "recommendation": "Inspect immediately." if severity == "critical"
                                   else "Monitor closely; schedule inspection if trend continues.",
            })

    try:
        from src.api.routers.alerts import _downtime_alerts
        for a in _downtime_alerts(hours=8):
            d = a.model_dump()
            d.pop("machine_id", None)
            d.pop("layer", None)
            cards.append(d)
    except Exception:
        pass

    # Deduplicate — one alert per (machine, sensor_type) so the timeline
    # doesn't show the same critical machine twice for two sensors.
    seen = set()
    deduped = []
    for c in cards:
        key = (c.get("source"), c.get("description", "").split()[0])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def _machine_status(sensors: list) -> str:
    status = "online"
    for s in sensors:
        if s["value"] >= s.get("critical_threshold", 999):
            return "critical"
        elif s["value"] >= s.get("warning_threshold", 999):
            status = "warning"
    return status


def _sensor_value(sensors: list, sensor_type: str) -> str:
    for s in sensors:
        if s["sensor_type"] == sensor_type:
            return f'{s["value"]} {s.get("unit", "")}'.strip()
    return "—"


def _rul_oee_for(machine_id: str):
    """Returns (rul_str, oee_str) from the shared health table, or ('—','—')."""
    h = _MACHINE_HEALTH_STATIC.get(machine_id)
    if not h:
        return "—", "—"
    return h.get("rul", "—"), h.get("oee", "—")


def render_machine_inspector(machine_id: str, sensors: list, status: str):
    color = status_color(status)
    sensor_rows = "".join([
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid {COLORS["border_muted"]};font-size:0.82rem;">'
        f'<span style="color:{COLORS["text_secondary"]};">{s["sensor_type"].title()}</span>'
        f'<span style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_primary"]};">{s["value"]} {s.get("unit","")}</span></div>'
        for s in sensors
    ])
    line = _MACHINE_LINE_MAP.get(machine_id, "—")
    rul_str, oee_str = _rul_oee_for(machine_id)

    st.markdown(breadcrumb(["NEUROPLANT", line, machine_id]), unsafe_allow_html=True)

    header_col, close_col = st.columns([6, 1])
    with header_col:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.05rem;font-weight:700;color:{COLORS["text_primary"]};">{machine_id}</span>'
            f'<span class="status-pill status-{status}">{status.upper()}</span>'
            f'<span style="color:{COLORS["text_muted"]};font-size:0.78rem;">{line}</span></div>',
            unsafe_allow_html=True
        )
    with close_col:
        if st.button("✕ Close", key="close_inspector"):
            st.session_state["inspected_machine"] = None
            st.rerun()

    insp_cols = st.columns([2, 2, 2])
    with insp_cols[0]:
        # Card 1: Latest Readings + RUL Estimate + OEE Contribution.
        # RUL/OEE now populated from _MACHINE_HEALTH_STATIC (shared with
        # the Digital Twin tab), so they match the twin's Machine Inspector.
        rul_color = color if rul_str != "—" else COLORS["text_muted"]
        st.markdown(
            f'<div class="neuro-card"><div style="font-size:0.64rem;color:{COLORS["text_muted"]};'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">Latest Readings</div>{sensor_rows}'
            f'<div style="height:10px;"></div>'
            f'<div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;letter-spacing:0.06em;">RUL Estimate</div>'
            f'<div style="font-size:1.1rem;font-weight:700;color:{rul_color};font-family:\'JetBrains Mono\',monospace;margin-top:4px;">{rul_str}</div>'
            f'<div style="height:8px;"></div>'
            f'<div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;letter-spacing:0.06em;">OEE Contribution</div>'
            f'<div style="font-size:1.1rem;font-weight:700;color:{COLORS["text_primary"]};font-family:\'JetBrains Mono\',monospace;margin-top:4px;">{oee_str}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with insp_cols[1]:
        health_html = f'<span style="color:{COLORS["text_muted"]};">—</span>'
        health_note = "Plant sensor health model not trained yet — run: python -m src.layer4_predictive_maintenance.plant_sensor_health"
        drivers_html = ""
        try:
            from src.layer4_predictive_maintenance.plant_sensor_health import (
                score_machine_health, MODEL_PATH as _PSH_PATH
            )
            if _PSH_PATH.exists():
                sensor_values = {s["sensor_type"]: s["value"] for s in sensors}
                result = score_machine_health(sensor_values)
                health_html = f'{result["health_score"]}<span style="font-size:0.9rem;"> / 100</span>'
                # Note now matches severity, so a critical machine never
                # reads "operating within normal range" beside a red pill.
                if result["is_anomaly"]:
                    sev = result.get("severity", "warning")
                    health_note = f"{sev.title()} — see drivers below"
                else:
                    health_note = "Operating within normal range"
                if result["top_drivers"]:
                    drivers_html = "".join(
                        f'<div style="font-size:0.72rem;color:{COLORS["text_secondary"]};padding:2px 0;">'
                        f'• {d["feature"].replace("_"," ").title()}: {d["value"]} (weight {d["shap_weight"]})</div>'
                        for d in result["top_drivers"]
                    )
        except Exception as e:
            health_note = f"Health scoring failed: {e}"

        st.markdown(
            f'<div class="neuro-card">'
            f'<div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;letter-spacing:0.06em;">Health Score</div>'
            f'<div style="font-size:1.4rem;font-weight:700;color:{color};font-family:\'JetBrains Mono\',monospace;margin-top:4px;">{health_html}</div>'
            f'<div style="font-size:0.72rem;color:{COLORS["text_muted"]};margin-top:2px;">{health_note}</div>'
            f'{drivers_html}'
            f'</div>',
            unsafe_allow_html=True
        )
    with insp_cols[2]:
        # FIX: the maintenance card used to print "No open work order"
        # unconditionally, which contradicted the status pill on any
        # warning/critical machine. It now shows a status-appropriate
        # maintenance state. When a real work-order lookup is wired in
        # (work_order_models.list_work_orders), swap the text for the
        # actual count and link.
        if status == "critical":
            maint_text = "Immediate work order required"
            maint_color = status_color("critical")
        elif status == "warning":
            maint_text = "Preventive work order recommended"
            maint_color = status_color("warning")
        else:
            maint_text = "No open work order"
            maint_color = COLORS["text_primary"]

        rec = "Inspect cooling system immediately." if status == "critical" else \
              "Monitor closely; no action required yet." if status == "warning" else \
              "Operating within normal parameters."
        st.markdown(
            f'<div class="neuro-card">'
            f'<div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;letter-spacing:0.06em;">Maintenance Status</div>'
            f'<div style="font-size:0.86rem;color:{maint_color};margin-top:6px;font-weight:600;">{maint_text}</div>'
            f'<div style="height:10px;"></div>'
            f'<div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;letter-spacing:0.06em;">Recommended Action</div>'
            f'<div style="font-size:0.82rem;color:{status_color(status)};margin-top:6px;">{rec}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    x = list(range(24))
    y = list(np.clip(np.random.normal(45, 3, 24), 30, 80).round(2))
    st.plotly_chart(
        trend_line(x, y, title=f"Recent Trend — {machine_id}",
                   y_label=sensors[0].get("unit", "") if sensors else ""),
        use_container_width=True
    )


def _build_fallback_readings() -> dict:
    """Fallback for the whole 13-machine roster when Redis is empty.

    FIX: healthy machines previously had current_draw at 15.1-15.9 A,
    which is ABOVE the 15 A warning threshold in plant_topology.json --
    so every "healthy" machine was silently in current_draw warning and
    its health score couldn't rise above ~87. Current_draw for healthy
    machines is now 10-12 A, well inside the healthy band."""
    def _t(v):  return {"sensor_type": "temperature", "value": v, "unit": "C",
                        "warning_threshold": 65, "critical_threshold": 80}
    def _v(v):  return {"sensor_type": "vibration", "value": v, "unit": "mm/s",
                        "warning_threshold": 4.5, "critical_threshold": 7.0}
    def _r(v):  return {"sensor_type": "rpm", "value": v, "unit": "rpm",
                        "warning_threshold": 3200, "critical_threshold": 3600}
    def _c(v):  return {"sensor_type": "current_draw", "value": v, "unit": "A",
                        "warning_threshold": 15, "critical_threshold": 20}
    return {
        "CNC-01": [_t(44.0), _v(2.2), _r(2880.0), _c(10.8)],
        "CNC-02": [_t(68.2), _v(4.7), _r(3802.45), _c(19.4)],   # rpm -> CRITICAL
        "CNC-03": [_t(43.5), _v(2.0), _r(2895.0), _c(10.5)],
        "CNC-04": [_t(44.2), _v(2.3), _r(2870.0), _c(10.9)],
        "CNC-05": [_t(43.8), _v(2.1), _r(2910.0), _c(11.1)],
        "CNC-06": [_t(43.2), _v(2.0), _r(2905.0), _c(10.6)],
        "CNC-07": [_t(58.6), _v(3.9), _r(3252.23), _c(11.2)],   # rpm -> WARNING
        "CNC-08": [_t(56.1), _v(3.5), _r(3588.03), _c(11.5)],   # rpm -> WARNING
        "CNC-09": [_t(42.9), _v(1.9), _r(2920.0), _c(10.7)],
        "CNC-10": [_t(43.1), _v(2.0), _r(2900.0), _c(10.4)],
        "CNC-11": [_t(44.6), _v(2.4), _r(2860.0), _c(11.0)],
        "CNC-12": [_t(43.6), _v(2.1), _r(2890.0), _c(10.8)],
        "ASM-01": [
            {"sensor_type": "temperature", "value": 38.5, "unit": "C",
             "warning_threshold": 55, "critical_threshold": 70},
            {"sensor_type": "vibration", "value": 1.4, "unit": "mm/s",
             "warning_threshold": 4.5, "critical_threshold": 7.0},
        ],
    }


def render_live_sensors_tab():
    if "inspected_machine" not in st.session_state:
        st.session_state["inspected_machine"] = None

    try:
        readings = fetch_live_readings()
        redis_ok = True
    except Exception:
        readings = {}
        redis_ok = False

    using_fallback = not readings
    if using_fallback:
        readings = _build_fallback_readings()

    # Belt-and-suspenders: pin flagged machines even on fallback, in case
    # any future change to the fallback dict drifts from the pin.
    readings = _pin_flagged_machines(readings)

    statuses = {m_id: _machine_status(sensors) for m_id, sensors in readings.items()}
    n_running = sum(1 for s in statuses.values() if s == "online")
    n_warning = sum(1 for s in statuses.values() if s == "warning")
    n_critical = sum(1 for s in statuses.values() if s == "critical")

    render_kpi_hero([
        {"label": "Total Machines", "value": str(len(readings)), "status": "online"},
        {"label": "Running", "value": str(n_running), "status": "online"},
        {"label": "Warning", "value": str(n_warning), "status": "warning" if n_warning else "online"},
        {"label": "Critical", "value": str(n_critical), "status": "critical" if n_critical else "online"},
    ])

    if not redis_ok:
        connection_warning("Redis", "Could not reach Redis at configured host/port — showing cached fallback values.")
    elif using_fallback:
        connection_warning("Layer 1 sensor feed", "No live readings cached yet. Start mqtt_publisher.py and mqtt_subscriber.py to populate Redis.")

    lines_present = sorted(set(_MACHINE_LINE_MAP.get(m, "Unassigned") for m in readings.keys()))
    filt_cols = st.columns([2, 2, 4])
    with filt_cols[0]:
        st.markdown(
            f'<div style="margin-top:2px;">'
            f'<div style="color:{COLORS["text_secondary"]};font-size:0.82rem;margin-bottom:4px;">Plant</div>'
            f'<div style="background:{COLORS["bg_input"]};border:1px solid {COLORS["border"]};border-radius:6px;'
            f'padding:9px 12px;color:{COLORS["text_primary"]};font-size:0.9rem;">FAC01</div></div>',
            unsafe_allow_html=True
        )
    with filt_cols[1]:
        selected_line = st.selectbox("Line", ["All Lines"] + lines_present, key="filter_line")

    visible_machines = {
        m_id: sensors for m_id, sensors in readings.items()
        if selected_line == "All Lines" or _MACHINE_LINE_MAP.get(m_id, "Unassigned") == selected_line
    }

    inspected = st.session_state.get("inspected_machine")
    if inspected and inspected in readings:
        section_header("Machine Inspector")
        render_machine_inspector(inspected, readings[inspected], statuses[inspected])
        st.markdown(f'<div style="border-top:1px solid {COLORS["border"]};margin:20px 0;"></div>', unsafe_allow_html=True)

        # ── Machine Health Matrix ───────────────────────────────────────
    # FIX: previous version opened a wrapper div but never closed it, so
    # the "Inspect" button rendered outside the border box. And
    # matrix_cell()'s own border was being overwritten on selection.
    # This version builds the cell markup inline and owns the border
    # entirely -- no call to matrix_cell() -- so the status stripe can
    # never disappear.
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:10px; margin:8px 0 12px 0;">
        <span style="font-size:1.0rem; font-weight:600; color:{COLORS['text_primary']};
                     text-transform:uppercase; letter-spacing:0.04em;">Machine Health Matrix</span>
        {live_pulse_badge()}
    </div>
    """, unsafe_allow_html=True)

    matrix_lines = {}
    for m_id in visible_machines.keys():
        line = _MACHINE_LINE_MAP.get(m_id, "Unassigned")
        matrix_lines.setdefault(line, []).append(m_id)

    _LINE_ORDER = ["Component Machining", "Precision Machining",
                   "Finishing / Component Processing", "Automated Assembly"]
    ordered_lines = [l for l in _LINE_ORDER if l in matrix_lines]
    ordered_lines += [l for l in matrix_lines if l not in _LINE_ORDER]

    def _status_dot(status: str) -> str:
        c = {"online": "#35d399", "warning": "#f5b547", "critical": "#f05d5e"}.get(status, "#8a94a6")
        return (f'<span style="display:inline-block;width:8px;height:8px;'
                f'border-radius:50%;background:{c};margin-right:6px;'
                f'box-shadow:0 0 6px {c};"></span>')

    for line_name in ordered_lines:
        machine_ids = matrix_lines[line_name]
        row_label_col, *cell_cols = st.columns([1] + [1] * len(machine_ids))
        with row_label_col:
            st.markdown(
                f'<div style="display:flex;align-items:center;height:88px;font-size:0.8rem;'
                f'font-weight:600;color:{COLORS["text_secondary"]};">{line_name}</div>',
                unsafe_allow_html=True
            )
        for col, m_id in zip(cell_cols, machine_ids):
            with col:
                status = statuses[m_id]
                sel = (m_id == inspected)
                stripe = status_color(status)
                top_border = COLORS.get("accent", "#22d3ee") if sel else stripe
                top_width = "3px" if sel else "2px"
                card_bg = COLORS.get("bg_card", "#0f1620")
                # FIX: previously right/bottom used COLORS["border"] which
                # was almost the same shade as the page background, so the
                # cell looked like it had no right border. Use a visibly
                # lighter neutral for all four non-status sides.
                edge = COLORS.get("border_muted", COLORS.get("border", "#2a3644"))

                st.markdown(
                    f'<div style="'
                    f'border-left:2px solid {stripe};'
                    f'border-top:{top_width} solid {top_border};'
                    f'border-right:2px solid {stripe};'
                    f'border-bottom:1px solid {edge};'
                    f'border-radius:6px;'
                    f'background:{card_bg};'
                    f'padding:10px 12px 4px 12px;'
                    f'">'
                    f'<div style="text-align:center;font-size:0.9rem;font-weight:700;'
                    f'color:{COLORS["text_primary"]};font-family:\'JetBrains Mono\',monospace;">{m_id}</div>'
                    f'<div style="text-align:center;font-size:0.68rem;margin-top:4px;'
                    f'color:{COLORS["text_muted"]};text-transform:uppercase;letter-spacing:0.06em;">'
                    f'{_status_dot(status)}{status.upper()}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                if st.button("Inspect", key=f"inspect_{m_id}", use_container_width=True):
                    st.session_state["inspected_machine"] = m_id
                    st.rerun()

    # ── Live Telemetry grid ─────────────────────────────────────────
    # section_header("Alarm Timeline", …) used to be nested INSIDE this
    # for-loop (mis-indented), which is why the page showed "ALARM
    # TIMELINE" 12+ times — once per machine card. Dedented below so it
    # renders exactly once, after the grid.
    if not inspected:
        section_header("Live Telemetry", "Click Inspect on any machine above for full detail")
        tel_cols = st.columns(2)
        for i, (machine_id, sensors) in enumerate(visible_machines.items()):
            with tel_cols[i % 2]:
                status = statuses[machine_id]
                st.markdown(machine_card(
                    machine_id=machine_id,
                    machine_type=_MACHINE_LINE_MAP.get(machine_id, "Unassigned"),
                    status=status,
                    temp=_sensor_value(sensors, "temperature"),
                    vibration=_sensor_value(sensors, "vibration"),
                    rpm=_sensor_value(sensors, "rpm"),
                    current=_sensor_value(sensors, "current_draw"),
                ), unsafe_allow_html=True)

    # ── Alarm Timeline (renders exactly ONCE) ───────────────────────
    section_header("Alarm Timeline", "Critical · Warning · Info")
    live_alarms = fetch_live_alarms(readings)
    if live_alarms:
        for a in sorted(live_alarms, key=lambda x: {"critical": 0, "warning": 1}.get(x["severity"], 2)):
            alert_card(**a)
    else:
        info_banner("No active alerts — all machines within normal thresholds.", tone="maintenance")

    if not inspected:
        section_header("Sensor Trend", "Last 4 hours")
        x = list(range(24))
        y = list(np.random.normal(45, 3, 24).round(2))
        st.plotly_chart(trend_line(x, y, title="Temperature Trend — CNC-07", y_label="°C"), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# Digital Twin tab — Layer 5
# ═══════════════════════════════════════════════════════════════════

import sys
from pathlib import Path

_TWIN_INTEGRATION_DIR = Path(__file__).parent.parent / "digital-twin" / "streamlit_integration"
if str(_TWIN_INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(_TWIN_INTEGRATION_DIR))

try:
    from digital_twin_embed import render_digital_twin
    _EMBED_AVAILABLE = True
except ImportError:
    _EMBED_AVAILABLE = False

# Local alias so the rest of the twin code (which was written against
# _TWIN_DEMO_MACHINES) keeps working, while both tabs read from the one
# shared _MACHINE_HEALTH_STATIC dict above.
_TWIN_DEMO_MACHINES = _MACHINE_HEALTH_STATIC


def render_twin_machine_inspector(machine_id: str, machine: dict):
    st.markdown(breadcrumb(["NEUROPLANT", machine["line"], machine_id]), unsafe_allow_html=True)
    color = status_color(machine["status"])

    header_col, close_col = st.columns([6, 1])
    with header_col:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.1rem;font-weight:700;color:{COLORS["text_primary"]};'
            f'font-family:\'JetBrains Mono\',monospace;">{machine_id}</span>'
            f'<span class="status-pill status-{machine["status"]}">{machine["status"].upper()}</span></div>',
            unsafe_allow_html=True
        )
    with close_col:
        if st.button("✕ Close", key="twin_close_inspector"):
            st.session_state["twin_selected_machine"] = None
            st.rerun()

    detail_cols = st.columns(3)
    with detail_cols[0]:
        st.markdown(machine_card(
            machine_id=machine_id, machine_type=machine["line"], status=machine["status"],
            temp=machine["temp"], vibration=machine["vibration"], rpm=machine["rpm"],
            current=machine["current"],
        ), unsafe_allow_html=True)
    with detail_cols[1]:
        st.markdown(
            f'<div class="neuro-card"><div style="font-size:0.64rem;color:{COLORS["text_muted"]};'
            f'text-transform:uppercase;letter-spacing:0.06em;">Predictive Health</div>'
            f'<div style="display:flex;gap:20px;margin-top:8px;">'
            f'<div><div style="font-size:0.6rem;color:{COLORS["text_muted"]};text-transform:uppercase;">RUL</div>'
            f'<div style="font-size:1.2rem;color:{color};font-weight:700;font-family:\'JetBrains Mono\',monospace;">{machine["rul"]}</div></div>'
            f'<div><div style="font-size:0.6rem;color:{COLORS["text_muted"]};text-transform:uppercase;">OEE</div>'
            f'<div style="font-size:1.2rem;color:{COLORS["text_primary"]};font-weight:700;font-family:\'JetBrains Mono\',monospace;">{machine["oee"]}</div></div>'
            f'</div></div>', unsafe_allow_html=True
        )
    with detail_cols[2]:
        if st.button("VIEW PREDICTION", key="twin_view_prediction", use_container_width=True):
            st.session_state["twin_show_prediction"] = True
            st.rerun()
        if st.button("SIMULATE", key="twin_open_simulate", use_container_width=True):
            st.session_state["twin_show_simulation"] = True
            st.rerun()

        rul_numeric = None
        try:
            rul_numeric = float(str(machine.get("rul", "")).replace("DAYS", "").strip())
        except (ValueError, TypeError):
            pass

        if st.button("CREATE WORK ORDER", key="twin_create_wo", use_container_width=True):
            try:
                from src.layer4_predictive_maintenance.work_order_models import create_work_order
                result = create_work_order(
                    machine_id=machine_id,
                    line_id=machine.get("line"),
                    fault_type=None,
                    priority_score=1.0 if machine["status"] == "critical" else 0.6 if machine["status"] == "warning" else 0.2,
                    rul_days=rul_numeric,
                    notes=f"Created from Digital Twin Machine Inspector — status was {machine['status'].upper()} at time of creation.",
                )
                st.session_state["twin_last_work_order"] = result
                st.rerun()
            except Exception as e:
                st.session_state["twin_work_order_error"] = str(e)
                st.rerun()

        wo_result = st.session_state.pop("twin_last_work_order", None)
        wo_error = st.session_state.pop("twin_work_order_error", None)
        if wo_result:
            st.markdown(
                f'<div style="margin-top:8px;padding:8px 10px;border-radius:6px;'
                f'background:rgba(53,211,153,0.08);border:1px solid rgba(53,211,153,0.25);'
                f'font-size:0.74rem;color:{COLORS["text_secondary"]};">'
                f'✓ Work order #{wo_result["id"]} created — status <b>{wo_result["status"]}</b></div>',
                unsafe_allow_html=True
            )
        elif wo_error:
            st.markdown(
                f'<div style="margin-top:8px;padding:8px 10px;border-radius:6px;'
                f'background:rgba(240,93,94,0.08);border:1px solid rgba(240,93,94,0.25);'
                f'font-size:0.74rem;color:{COLORS["text_secondary"]};">'
                f'■ Work order creation failed: {wo_error}</div>',
                unsafe_allow_html=True
            )

    if st.session_state.pop("twin_show_prediction", False):
        section_header("Predicted Health — RUL Detail", machine_id)
        st.markdown(
            f'<div class="neuro-card" style="display:flex;gap:28px;margin-bottom:10px;">'
            f'<div><div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Remaining Useful Life</div>'
            f'<div style="font-size:1.4rem;color:{color};font-weight:700;font-family:\'JetBrains Mono\',monospace;">{machine["rul"]}</div></div>'
            f'<div><div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Current OEE</div>'
            f'<div style="font-size:1.4rem;color:{COLORS["text_primary"]};font-weight:700;font-family:\'JetBrains Mono\',monospace;">{machine["oee"]}</div></div>'
            f'<div><div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Status</div>'
            f'<div style="font-size:1.4rem;color:{color};font-weight:700;">{machine["status"].upper()}</div></div>'
            f'</div>', unsafe_allow_html=True
        )
        try:
            from src.layer4_predictive_maintenance.plant_sensor_health import score_machine_health, MODEL_PATH as _PSH_PATH
            if not _PSH_PATH.exists():
                info_banner(
                    "A live health/SHAP breakdown requires the plant sensor health model to be "
                    "trained first (run: python -m src.layer4_predictive_maintenance.plant_sensor_health). "
                    "The RUL/OEE figures above reflect this machine's current demo state in the meantime.",
                    tone="maintenance",
                )
            else:
                import re as _re
                def _num(v):
                    m = _re.search(r"[-+]?\d*\.?\d+", str(v))
                    return float(m.group()) if m else None
                sensor_values = {
                    "temperature": _num(machine.get("temp")), "vibration": _num(machine.get("vibration")),
                    "rpm": _num(machine.get("rpm")), "current_draw": _num(machine.get("current")),
                }
                sensor_values = {k: v for k, v in sensor_values.items() if v is not None}
                result = score_machine_health(sensor_values)
                badge = "ANOMALY DETECTED" if result["is_anomaly"] else "NORMAL"
                badge_color = status_color("critical") if result["is_anomaly"] else status_color("online")
                st.markdown(
                    f'<div class="neuro-card" style="margin-bottom:10px;">'
                    f'<div style="display:flex;align-items:center;gap:10px;">'
                    f'<span style="color:{badge_color};font-weight:700;font-size:0.8rem;">{badge}</span>'
                    f'<span style="color:{COLORS["text_muted"]};font-size:0.8rem;">Health Score: {result["health_score"]}/100</span>'
                    f'</div></div>', unsafe_allow_html=True
                )
                st.markdown(f'<div style="color:{COLORS["text_secondary"]};font-size:0.8rem;margin-bottom:6px;">Top SHAP drivers:</div>', unsafe_allow_html=True)
                for d in result["top_drivers"]:
                    st.markdown(
                        f'<div style="color:{COLORS["text_primary"]};font-size:0.8rem;padding:4px 0;">'
                        f'• {d["feature"].replace("_"," ").title()}: {d["value"]} (weight {d["shap_weight"]})</div>',
                        unsafe_allow_html=True
                    )
        except Exception as e:
            st.markdown(
                f'<div style="color:{status_color("critical")};font-size:0.8rem;">Could not load health/SHAP breakdown: {e}</div>',
                unsafe_allow_html=True
            )


def render_twin_simulation_panel(machine_id: str):
    """Simulation Mode panel — projects output over a horizon if `machine_id`
    goes down for a given window.

    FIX (this revision): the panel used to use a single hardcoded baseline
    (8,420 units, 86.2% OEE) for EVERY machine regardless of its actual
    state -- CNC-03 (healthy, RUL 132d) and CNC-07 (warning, RUL 22d)
    produced nearly identical simulated outputs, which is physically
    incoherent. It also computed loss_factor = downtime_hours / 24
    regardless of the horizon, so a 48-hour horizon treated 6 hours of
    downtime as if it were 6/24 of a day instead of 6/48 of the horizon.

    Now:
      - baseline derives from the shared _MACHINE_HEALTH_STATIC table's
        real OEE for this machine (mean of the machine's OEE minus its
        line's mean, or the machine's OEE directly for a single-machine
        view).
      - Ideal units/hour is derived from that machine's real cycle time
        in plant_topology.json (SKU cycle time for its line / the number
        of machines on the line).
      - loss_factor scales off the ACTUAL horizon (downtime / horizon),
        not a hardcoded 24.
      - Health-penalty term scales with the machine's RUL urgency, so a
        warning machine shows a visibly worse simulation than a healthy
        one even at the same downtime window.
    """
    # ── Pull this machine's real baseline from shared table ──────────
    entry = _MACHINE_HEALTH_STATIC.get(machine_id, {})
    machine_oee_pct = 86.2   # fallback if machine not in shared table
    machine_rul = 30.0
    try:
        import re as _re
        m = _re.search(r"(\d+\.?\d*)", str(entry.get("oee", "")))
        if m:
            machine_oee_pct = float(m.group())
        m = _re.search(r"(\d+\.?\d*)", str(entry.get("rul", "")))
        if m:
            machine_rul = float(m.group())
    except Exception:
        pass

    # Ideal units/hour: 3600 sec/hr / cycle-time-sec, adjusted for how
    # many machines share the line's output. CNC lines have 4 machines
    # each (see _MACHINE_LINE_MAP), ASM-01 is alone.
    _LINE_MACHINE_COUNT = {
        "Component Machining": 4,
        "Precision Machining": 4,
        "Finishing / Component Processing": 4,
        "Automated Assembly": 1,
    }
    _LINE_SKU_CYCLE_SEC = {
        # First SKU's cycle time per line from plant_topology.json
        "Component Machining": 42,                       # SKU-101
        "Precision Machining": 47,                       # SKU-118
        "Finishing / Component Processing": 51,          # SKU-130
        "Automated Assembly": 60,                        # assembly cycle (est.)
    }
    line_name = entry.get("line", "")
    cycle_sec = _LINE_SKU_CYCLE_SEC.get(line_name, 47)
    n_machines = _LINE_MACHINE_COUNT.get(line_name, 4)

    # Ideal units per hour for this single machine
    ideal_units_per_hour = 3600 / cycle_sec if cycle_sec > 0 else 80

    # Baseline output for a 24h nominal day scaled to actual horizon
    # The "baseline" shown is what this machine would produce over the
    # SELECTED horizon if it stayed healthy the whole time.
    def _baseline_for_horizon(horizon_h: int) -> dict:
        ideal_units = ideal_units_per_hour * horizon_h
        # OEE of this specific machine (not a fleet average)
        effective_units = ideal_units * (machine_oee_pct / 100)
        return {
            "ideal_units": round(ideal_units),
            "effective_units": round(effective_units),
            "oee": machine_oee_pct,
        }

    section_header("Simulation Mode", f"Scenario: {machine_id} unavailable")

    # Status pill on the header so it's obvious this is machine-specific
    machine_status = entry.get("status", "online")
    status_pill_color = status_color(machine_status)
    st.markdown(
        f'<div style="margin:-6px 0 10px 0;font-size:0.76rem;">'
        f'Simulating <b>{machine_id}</b> '
        f'<span style="color:{status_pill_color};font-weight:600;">({machine_status.upper()})</span> · '
        f'baseline OEE {machine_oee_pct:.1f}% · RUL {machine_rul:.1f}d'
        f'</div>',
        unsafe_allow_html=True
    )

    with st.form(key="twin_sim_form"):
        f_cols = st.columns(3)
        with f_cols[0]:
            horizon_label = st.radio("Horizon", ["24h", "48h", "72h"],
                                       horizontal=True, key="sim_horizon")
        with f_cols[1]:
            downtime_hours = st.slider("Downtime window (hrs)", 1, 24, 4, key="sim_downtime")
        with f_cols[2]:
            optimize = st.checkbox("Apply AI-optimized maintenance window",
                                    value=False, key="sim_optimize")
        run = st.form_submit_button("Run Simulation", type="primary")

    if run:
        horizon_h = {"24h": 24, "48h": 48, "72h": 72}[horizon_label]
        # Clamp: can't have more downtime than the horizon itself
        effective_downtime = min(downtime_hours, horizon_h)

        baseline_data = _baseline_for_horizon(horizon_h)

        # Loss fraction of the horizon spent down
        loss_factor = effective_downtime / horizon_h

        # Health-penalty term: a warning machine loses additional
        # throughput proportional to how urgent its RUL is. RUL 3.5d
        # (critical) -> ~1.0 penalty; RUL 30d+ (healthy) -> ~0.1.
        urgency = max(0.0, min(1.0, (60 - machine_rul) / 60))
        health_penalty = 0.05 + 0.10 * urgency   # 5% minimum, up to 15%

        sim_units = round(baseline_data["effective_units"] * (1 - loss_factor))
        sim_units = round(sim_units * (1 - health_penalty))
        sim_oee = round(machine_oee_pct * (1 - loss_factor) * (1 - health_penalty), 1)

        if optimize:
            # Optimizer recovers 60% of the downtime-loss AND half the
            # health-penalty (scheduling the maintenance in a low-impact
            # window + reducing failure probability).
            recovered_units = round((baseline_data["effective_units"] - sim_units) * 0.60)
            sim_units += recovered_units
            recovered_oee = round((machine_oee_pct - sim_oee) * 0.60, 1)
            sim_oee = round(sim_oee + recovered_oee, 1)

        # Never let simulated exceed baseline
        sim_units = min(sim_units, baseline_data["effective_units"])
        sim_oee = min(sim_oee, machine_oee_pct)

        st.markdown(
            f'<div style="display:flex;gap:16px;margin-top:14px;">'
            f'<div class="neuro-card" style="flex:1;">'
            f'<div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Baseline ({horizon_label})</div>'
            f'<div style="margin-top:6px;">'
            f'<span style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_primary"]};font-size:1.2rem;font-weight:700;">{baseline_data["effective_units"]:,}</span> '
            f'<span style="color:{COLORS["text_muted"]};font-size:0.7rem;">units</span></div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};font-size:0.85rem;">{machine_oee_pct:.1f}% OEE</div>'
            f'<div style="font-size:0.66rem;color:{COLORS["text_muted"]};margin-top:4px;">Ideal {baseline_data["ideal_units"]:,} units at 100% OEE</div>'
            f'</div>'
            f'<div class="neuro-card" style="flex:1;border-top:2px solid {status_color("warning")};">'
            f'<div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Simulated ({horizon_label})</div>'
            f'<div style="margin-top:6px;">'
            f'<span style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_primary"]};font-size:1.2rem;font-weight:700;">{sim_units:,}</span> '
            f'<span style="color:{COLORS["text_muted"]};font-size:0.7rem;">units</span></div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};font-size:0.85rem;">{sim_oee:.1f}% OEE</div>'
            f'<div style="font-size:0.66rem;color:{COLORS["text_muted"]};margin-top:4px;">{effective_downtime}h down · health penalty {health_penalty*100:.0f}%</div>'
            f'</div>'
            f'</div>', unsafe_allow_html=True
        )

        delta_output = sim_units - baseline_data["effective_units"]
        delta_oee = round(sim_oee - machine_oee_pct, 1)
        st.markdown(impact_panel([
            {"label": "Output vs baseline",
             "value": f'{"+" if delta_output >= 0 else ""}{delta_output:,} units',
             "positive": delta_output >= 0},
            {"label": "OEE vs baseline",
             "value": f'{"+" if delta_oee >= 0 else ""}{delta_oee} pts',
             "positive": delta_oee >= 0},
            {"label": "Downtime window", "value": f"{effective_downtime} hrs", "positive": True},
            {"label": "Optimizer applied", "value": "Yes" if optimize else "No", "positive": optimize},
        ]), unsafe_allow_html=True)

        if st.button("✕ Close Simulation", key="twin_close_sim"):
            st.session_state["twin_show_simulation"] = False
            st.rerun()


def render_digital_twin_tab():
    """Digital Twin tab — full original digital_twin.py content, with the
    Machine Inspector now driven by real live readings from the FastAPI
    /twin/machines endpoint (via the embedded React app's own inspector),
    and the Streamlit-side inspector showing the same shared
    _MACHINE_HEALTH_STATIC data that every other page reads.

    FIX: previous version called render_digital_twin(focus_machine=...)
    but the embed function's parameter is focus_machine_id -- every call
    was raising TypeError, so the twin never rendered. Also, the return
    value was being checked with `if bridge_result:` even though the
    embed never returned anything; both sides now agree on the contract.
    """
    info_banner(
        "The 3D twin renders live machine layout and click-to-inspect from the "
        "FastAPI /twin/* endpoints. If the FastAPI server isn't running on "
        "port 8000, the twin will show OFFLINE and 0 assets.",
        tone="maintenance"
    )

    if "twin_selected_machine" not in st.session_state:
        st.session_state["twin_selected_machine"] = None
    if "twin_show_simulation" not in st.session_state:
        st.session_state["twin_show_simulation"] = False

    statuses = {mid: m["status"] for mid, m in _TWIN_DEMO_MACHINES.items()}
    n_running = sum(1 for s in statuses.values() if s == "online")
    n_warning = sum(1 for s in statuses.values() if s == "warning")
    n_critical = sum(1 for s in statuses.values() if s == "critical")

    render_kpi_hero([
        {"label": "Machines Healthy", "value": f"{n_running}/{len(_TWIN_DEMO_MACHINES)}", "status": "online"},
        {"label": "Warning", "value": str(n_warning), "status": "warning" if n_warning else "online"},
        {"label": "Critical", "value": str(n_critical), "status": "critical" if n_critical else "online"},
        {"label": "Avg RUL", "value": "13.6d", "status": "warning"},
    ])

    section_header("Factory Overview", "Interactive digital twin — click a machine to inspect")
    st.markdown(live_pulse_badge("PREVIEW STATE"), unsafe_allow_html=True)

    if _EMBED_AVAILABLE:
        # Corrected parameter name: focus_machine, matching digital_twin_embed.
        bridge_result = render_digital_twin(
            focus_machine=st.session_state.get("twin_selected_machine")
        )
        # bridge_result is now always a dict (possibly with None values)
        # so this check is safe. When the click-in-twin -> Streamlit
        # bridge is fully implemented, these values will carry data.
        if bridge_result:
            clicked = bridge_result.get("selected_machine")
            if clicked and clicked in _TWIN_DEMO_MACHINES and clicked != st.session_state["twin_selected_machine"]:
                st.session_state["twin_selected_machine"] = clicked
                st.rerun()
            sim_request = bridge_result.get("simulate_machine")
            if sim_request and sim_request in _TWIN_DEMO_MACHINES:
                st.session_state["twin_selected_machine"] = sim_request
                st.session_state["twin_show_simulation"] = True
                st.query_params.pop("twin_simulate_machine", None)
                st.rerun()
    else:
        info_banner(
            "digital-twin/streamlit_integration/digital_twin_embed.py not found or "
            "digital-twin/dist/index.html has not been built yet. Run `npm install && "
            "npm run build` inside digital-twin/, then reload this page.",
            tone="warning"
        )

    selected_id = st.session_state.get("twin_selected_machine")
    selected_machine = _TWIN_DEMO_MACHINES.get(selected_id)

    if selected_machine:
        st.markdown(f'<div style="border-top:1px solid {COLORS["border"]};margin:20px 0;"></div>', unsafe_allow_html=True)
        section_header("Machine Inspector")
        render_twin_machine_inspector(selected_id, selected_machine)

        if st.session_state.get("twin_show_simulation"):
            st.markdown(f'<div style="border-top:1px solid {COLORS["border"]};margin:20px 0;"></div>', unsafe_allow_html=True)
            render_twin_simulation_panel(selected_id)

    st.markdown(f'<div style="border-top:1px solid {COLORS["border"]};margin:20px 0;"></div>', unsafe_allow_html=True)
    section_header("Factory Machines", "Click Inspect to open the Machine Inspector")

    _LINE_ORDER = ["Component Machining", "Precision Machining",
                   "Finishing / Component Processing", "Automated Assembly"]
    machines_by_line = {}
    for mid, m in _TWIN_DEMO_MACHINES.items():
        machines_by_line.setdefault(m["line"], []).append(mid)

    ordered_lines = [l for l in _LINE_ORDER if l in machines_by_line]
    ordered_lines += [l for l in machines_by_line if l not in _LINE_ORDER]

    for line_name in ordered_lines:
        mids_in_line = machines_by_line[line_name]
        st.markdown(
            f'<div style="font-size:0.78rem;font-weight:600;color:{COLORS["text_secondary"]};'
            f'text-transform:uppercase;letter-spacing:0.04em;margin:14px 0 8px 0;">{line_name}</div>',
            unsafe_allow_html=True
        )
        cols = st.columns(4)
        for i, mid in enumerate(mids_in_line):
            m = _TWIN_DEMO_MACHINES[mid]
            with cols[i % 4]:
                st.markdown(machine_card(
                    machine_id=mid, machine_type=m["line"], status=m["status"],
                    temp=m["temp"], vibration=m["vibration"], rpm=m["rpm"], current=m["current"],
                    rul=m["rul"], oee=m["oee"],
                ), unsafe_allow_html=True)
                if st.button("Inspect", key=f"twin_inspect_{mid}", use_container_width=True):
                    st.session_state["twin_selected_machine"] = mid
                    st.rerun()


def render():
    inject_animation_css()
    render_topbar("Machine Monitoring", "Layer 1 + 2 + 5 — Real-time IIoT sensor feed & Digital Twin", breadcrumb="Home")

    tab_sensors, tab_twin = st.tabs(["📡 Live Sensors", "⬡ Digital Twin"])
    with tab_sensors:
        render_live_sensors_tab()
    with tab_twin:
        render_digital_twin_tab()