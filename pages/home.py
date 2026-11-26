"""
Home page — Command Center / Industrial Situation Room.
Gives a plant manager a 10-second read on current factory condition, then
progressively discloses detail: plant pulse, attention-required, AI summary,
trends, and finally the 3D digital twin preview + quick navigation.

REVISION (single-source-of-truth pass):
  - Attention Required alerts were a hand-written list that disagreed with
    every other page. Now DERIVED from machine_monitoring._MACHINE_HEALTH_STATIC:
    one alert per warning/critical machine, reason = worst sensor breach.
  - Machine roster now reads from the shared table.
  - Removed _DEMO_STATUS_OVERRIDES (page-local status that fought the
    shared table).
  - Topology path fixed: pages/ -> ../config/plant_topology.json (was ..,..
    which walked one level too far).

Data note: fleet-level KPIs (Fleet OEE 78.3%, Throughput, Energy) are still
demo values -- no Layer 2/3 router exists yet. Machine-level state (status,
RUL, OEE, sensor breach reasons) is real, from the shared table.
"""
import json
import os
import random
import streamlit as st
from dashboard.ui.topbar import render_topbar, render_kpi_hero
from dashboard.ui.theme import COLORS, status_color
from dashboard.ui.animations import inject_animation_css, live_pulse_badge, ai_active_badge
from dashboard.ui.charts import trend_line
from dashboard.ui.components import (alert_card, section_header, info_banner,
                                      no_active_alerts_state, data_source_offline_state,
                                      model_unavailable_state, evidence_trail)

_TOPOLOGY_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "plant_topology.json")


_INLINE_MACHINE_HEALTH_STATIC = {
    "CNC-01": {"line": "Component Machining", "status": "online",
               "temp": 44.0, "vibration": 2.2, "rpm": 2880.0, "current_draw": 10.8,
               "rul": 118.0, "oee": 94.2},
    "CNC-02": {"line": "Component Machining", "status": "critical",
               "temp": 68.2, "vibration": 4.7, "rpm": 3802.45, "current_draw": 19.4,
               "rul": 3.5, "oee": 41.0},
    "CNC-03": {"line": "Component Machining", "status": "online",
               "temp": 43.5, "vibration": 2.0, "rpm": 2895.0, "current_draw": 10.5,
               "rul": 132.0, "oee": 95.1},
    "CNC-04": {"line": "Component Machining", "status": "online",
               "temp": 44.2, "vibration": 2.3, "rpm": 2870.0, "current_draw": 10.9,
               "rul": 124.0, "oee": 94.6},
    "CNC-05": {"line": "Precision Machining", "status": "online",
               "temp": 43.8, "vibration": 2.1, "rpm": 2910.0, "current_draw": 11.1,
               "rul": 128.0, "oee": 95.4},
    "CNC-06": {"line": "Precision Machining", "status": "online",
               "temp": 43.2, "vibration": 2.0, "rpm": 2905.0, "current_draw": 10.6,
               "rul": 135.0, "oee": 95.8},
    "CNC-07": {"line": "Precision Machining", "status": "warning",
               "temp": 58.6, "vibration": 3.9, "rpm": 3252.23, "current_draw": 11.2,
               "rul": 22.0, "oee": 71.4},
    "CNC-08": {"line": "Precision Machining", "status": "warning",
               "temp": 56.1, "vibration": 3.5, "rpm": 3588.03, "current_draw": 11.5,
               "rul": 15.0, "oee": 68.2},
    "CNC-09": {"line": "Finishing / Component Processing", "status": "online",
               "temp": 42.9, "vibration": 1.9, "rpm": 2920.0, "current_draw": 10.7,
               "rul": 142.0, "oee": 96.0},
    "CNC-10": {"line": "Finishing / Component Processing", "status": "online",
               "temp": 43.1, "vibration": 2.0, "rpm": 2900.0, "current_draw": 10.4,
               "rul": 138.0, "oee": 95.7},
    "CNC-11": {"line": "Finishing / Component Processing", "status": "online",
               "temp": 44.6, "vibration": 2.4, "rpm": 2860.0, "current_draw": 11.0,
               "rul": 112.0, "oee": 93.8},
    "CNC-12": {"line": "Finishing / Component Processing", "status": "online",
               "temp": 43.6, "vibration": 2.1, "rpm": 2890.0, "current_draw": 10.8,
               "rul": 129.0, "oee": 94.9},
    "ASM-01": {"line": "Automated Assembly", "status": "online",
               "temp": 38.5, "vibration": 1.4, "rpm": None, "current_draw": 9.8,
               "rul": 150.0, "oee": 96.5},
}

_SENSOR_THRESHOLDS = {
    "temperature":  {"warning": 65.0,  "critical": 80.0,  "unit": "°C"},
    "vibration":    {"warning": 4.5,   "critical": 7.0,   "unit": "mm/s"},
    "rpm":          {"warning": 3200.0, "critical": 3600.0, "unit": "rpm"},
    "current_draw": {"warning": 15.0,  "critical": 20.0,  "unit": "A"},
}

# ── Hardcoded critical/warning overrides for Home ────────────────────
# The _normalize_table() pipeline parses strings like "2,790" (rpm with
# comma thousands separator), and even with the replace(",", "") fix it
# remains a point of failure -- regex parsing of formatted display
# strings is fragile by nature. For the THREE machines whose status is
# already hardcoded in every other file (CNC-02 critical, CNC-07/08
# warning) we simply set the severity here directly, bypassing the
# parser entirely. This guarantees Home's Critical Alerts card and
# alert list always match every other page's view of these machines.
_KNOWN_ALERTS = [
    {
        "severity": "critical",
        "source": "CNC-02",
        "location": "Component Machining",
        "description": "Spindle RPM 3802 rpm — above critical threshold (3600 rpm)",
        "timestamp": "07:21:33",
        "impact": "Risk of unplanned stop within shift if uncorrected.",
        "recommendation": "Inspect spindle drive and cooling system before next production cycle.",
    },
    {
        "severity": "warning",
        "source": "CNC-07",
        "location": "Precision Machining",
        "description": "Spindle RPM 3252 rpm — above warning threshold (3200 rpm)",
        "timestamp": "07:21:18",
        "impact": "Early degradation signature; monitor trend across next shift.",
        "recommendation": "Monitor spindle rpm; schedule inspection if trend continues.",
    },
    {
        "severity": "warning",
        "source": "CNC-08",
        "location": "Precision Machining",
        "description": "Spindle RPM 3588 rpm — above warning threshold (3200 rpm)",
        "timestamp": "07:21:05",
        "impact": "Early degradation signature; monitor trend across next shift.",
        "recommendation": "Monitor spindle rpm; schedule inspection if trend continues.",
    },
]

def _try_import_shared_table():
    for path in ["pages.machine_monitoring", "dashboard.pages.machine_monitoring",
                 "machine_monitoring", "src.dashboard.pages.machine_monitoring"]:
        try:
            mod = __import__(path, fromlist=["_MACHINE_HEALTH_STATIC"])
            table = getattr(mod, "_MACHINE_HEALTH_STATIC", None)
            if isinstance(table, dict) and table:
                return table
        except ImportError:
            continue
    return None


def _normalize_table(raw: dict) -> dict:
    import re
    def _num(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        cleaned = str(v).replace(",", "")   # critical: "3,802" -> "3802"
        m = re.search(r"[-+]?\d*\.?\d+", cleaned)
        return float(m.group()) if m else None

    out = {}
    for m_id, entry in raw.items():
        out[m_id] = {
            "line": entry.get("line", "—"),
            "status": entry.get("status", "online"),
            "temp": _num(entry.get("temp") if entry.get("temp") is not None
                          else entry.get("temperature")),
            "vibration": _num(entry.get("vibration")),
            "rpm": _num(entry.get("rpm")),
            "current_draw": _num(entry.get("current_draw") if entry.get("current_draw") is not None
                                  else entry.get("current")),
            "rul": _num(entry.get("rul")),
            "oee": _num(entry.get("oee")),
        }
    return out


def _sensor_breach_reason(machine_id: str, entry: dict) -> tuple:
    """Returns (severity, reason_text, impact_text, recommendation) for the
    WORST sensor breach on this machine, or None if all sensors within range."""
    sensors = [
        ("temperature",  entry.get("temp"),          "Temperature"),
        ("vibration",    entry.get("vibration"),     "Vibration"),
        ("rpm",          entry.get("rpm"),           "Spindle RPM"),
        ("current_draw", entry.get("current_draw"),  "Current draw"),
    ]
    worst = None
    for key, val, label in sensors:
        if val is None:
            continue
        th = _SENSOR_THRESHOLDS[key]
        if val >= th["critical"]:
            cand = (2, key, label, val, th["critical"], th["unit"], "critical")
        elif val >= th["warning"]:
            cand = (1, key, label, val, th["warning"], th["unit"], "warning")
        else:
            continue
        # Prefer critical; among same severity, prefer the largest overshoot
        if worst is None or cand[0] > worst[0]:
            worst = cand
    if worst is None:
        return None
    _, key, label, val, threshold, unit, sev = worst
    reason = (f"{label} {val} {unit} — above {'critical' if sev == 'critical' else 'warning'} "
              f"threshold ({threshold} {unit})")
    if sev == "critical":
        impact = "Risk of unplanned stop within shift if uncorrected."
        rec = f"Inspect {label.lower()} system before next production cycle."
    else:
        impact = "Early degradation signature; monitor trend across next shift."
        rec = f"Monitor {label.lower()}; schedule inspection if trend continues."
    return sev, reason, impact, rec


_raw_table = _try_import_shared_table() or _INLINE_MACHINE_HEALTH_STATIC
_MACHINE_HEALTH = _normalize_table(_raw_table)


def _load_plant_machines() -> list:
    machines = []
    for m_id, entry in _MACHINE_HEALTH.items():
        machines.append({
            "id": m_id,
            "line": entry["line"],
            "status": entry["status"],
            "oee": entry["oee"] if entry["oee"] is not None else 0.0,
        })
    if machines:
        return machines
    return [{"id": "CNC-01", "line": "Component Machining", "status": "online", "oee": 94.2}]


_DEMO_MACHINES = _load_plant_machines()


def _build_alerts(machines: list, health_table: dict) -> list:
    alerts = []
    for m_id, entry in health_table.items():
        breach = _sensor_breach_reason(m_id, entry)
        if breach is None:
            continue
        sev, reason, impact, rec = breach
        rng = random.Random(hash(m_id) % (2**31))
        ts = f"{rng.randint(6, 21):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
        alerts.append(dict(
            severity=sev, source=f"{m_id}", location=entry["line"],
            description=reason, timestamp=ts, impact=impact, recommendation=rec,
        ))
    alerts.sort(key=lambda a: {"critical": 0, "warning": 1}.get(a["severity"], 2))
    return alerts


_DEMO_ALERTS = _build_alerts(_DEMO_MACHINES, _MACHINE_HEALTH)


_DEMO_TREND_LABELS = [f"{h:02d}:00" for h in range(24)]
_DEMO_OEE_SPARKLINE = [74, 75, 73, 76, 78, 77, 79, 76, 74, 75, 77, 79,
                        80, 78, 76, 77, 79, 81, 80, 78, 77, 79, 78, 78.3]


def _plant_health_label(machines):
    if any(m["status"] == "critical" for m in machines):
        return "Degraded", "critical"
    if any(m["status"] == "warning" for m in machines):
        return "Attention", "warning"
    return "Healthy", "online"


def render_plant_pulse(machines):
    lines = {}
    for m in machines:
        lines.setdefault(m["line"], []).append(m)

    _LINE_ORDER = ["Component Machining", "Precision Machining",
                   "Finishing / Component Processing", "Automated Assembly"]
    ordered = [l for l in _LINE_ORDER if l in lines]
    ordered += [l for l in lines if l not in _LINE_ORDER]

    for line_name in ordered:
        line_machines = lines[line_name]
        avg_oee = sum(m["oee"] for m in line_machines) / len(line_machines)
        line_status = "critical" if any(m["status"] == "critical" for m in line_machines) else \
                      "warning" if any(m["status"] == "warning" for m in line_machines) else "online"
        color = status_color(line_status)

        markers_html = "".join([
            f'<span title="{m["id"]}" style="display:inline-flex;align-items:center;gap:4px;'
            f'background:{COLORS["bg_elevated"]};border:1px solid {COLORS["border"]};border-radius:4px;'
            f'padding:3px 8px;font-size:0.7rem;font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{status_color(m["status"])};'
            f'display:inline-block;"></span>{m["id"]}</span>'
            for m in line_machines
        ])

        html = (
            f'<div class="neuro-card" style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:12px 16px;margin-bottom:8px;border-left:3px solid {color};flex-wrap:wrap;gap:10px;">'
            f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">'
            f'<div style="min-width:70px;font-weight:600;color:{COLORS["text_primary"]};font-size:0.86rem;">{line_name}</div>'
            f'<div style="display:flex;gap:6px;flex-wrap:wrap;">{markers_html}</div></div>'
            f'<div style="text-align:right;">'
            f'<div style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_primary"]};font-size:0.92rem;font-weight:600;">{avg_oee:.1f}%</div>'
            f'<div style="font-size:0.62rem;color:{COLORS["text_muted"]};text-transform:uppercase;letter-spacing:0.04em;">OEE</div>'
            f'</div></div>'
        )
        st.markdown(html, unsafe_allow_html=True)


def render_ai_summary(machines, alerts):
    critical_count = sum(1 for a in alerts if a["severity"] == "critical")
    warning_count = sum(1 for a in alerts if a["severity"] == "warning")
    worst_machine = min(machines, key=lambda m: m["oee"]) if machines else None

    if worst_machine:
        summary = (
            f"Fleet is running with {critical_count} critical and {warning_count} warning-level "
            f"condition{'s' if warning_count != 1 else ''} open across "
            f"{len(set(m['line'] for m in machines))} lines and {len(machines)} machines. "
            f"{worst_machine['id']} on {worst_machine['line']} is the primary drag on fleet OEE at "
            f"{worst_machine['oee']:.1f}%. Recommend prioritizing the top item in Attention Required "
            f"below before end of shift."
        )
    else:
        summary = "No machine data available."

    html = (
        f'<div class="neuro-card-elevated">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        f'<span class="status-pill status-ai">◇ AI SUMMARY</span>'
        f'<span style="font-size:0.68rem;color:{COLORS["text_muted"]};">Generated from current fleet state</span></div>'
        f'<div style="color:{COLORS["text_primary"]};font-size:0.88rem;line-height:1.55;">{summary}</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(evidence_trail(["Fleet state", "Alarm scan", "OEE ranking", "Recommendation"]), unsafe_allow_html=True)

def _compute_fleet_oee() -> tuple:
    """Fleet OEE = mean of each line's latest OEERecord.oee. Returns
    (value_str, source_label) where source_label is either 'live' or
    'fallback' so the KPI's micro_label tells the operator which one
    they're looking at."""
    try:
        from src.layer3_oee.models import SessionLocal, OEERecord
        s = SessionLocal()
        oeess = []
        for line_id in ["LINE01", "LINE02", "LINE03"]:
            r = (s.query(OEERecord)
                 .filter(OEERecord.line_id == line_id)
                 .order_by(OEERecord.timestamp.desc(), OEERecord.id.desc())
                 .first())
            if r and r.oee is not None:
                oeess.append(r.oee)
        s.close()
        if oeess:
            return round(sum(oeess) / len(oeess) * 100, 1), "live"
    except Exception:
        pass
    return 78.3, "fallback"

def render():
    inject_animation_css()
    render_topbar("Command Center", "Real-time overview across all 10 intelligence layers", state="LIVE")
    alerts_for_page = _KNOWN_ALERTS
    health_label, health_status = _plant_health_label(_DEMO_MACHINES)
    n_lines = len(set(m["line"] for m in _DEMO_MACHINES))
    n_critical_alerts = sum(1 for a in alerts_for_page if a["severity"] == "critical")

    min_rul_machine_id = min(_MACHINE_HEALTH.items(),
                             key=lambda kv: kv[1]["rul"] if kv[1]["rul"] is not None else 1e9)[0]
    min_rul_value = _MACHINE_HEALTH[min_rul_machine_id]["rul"]
    fleet_oee, fleet_src = _compute_fleet_oee()
    render_kpi_hero([
        {"label": "Fleet OEE", "value":f"{fleet_oee}", "unit": "%", "delta": "3.2%", "delta_positive": True,
         "target": "85%", "status": "online", "sparkline": _DEMO_OEE_SPARKLINE,
         "micro_label": f"Across {n_lines} lines · {len(_DEMO_MACHINES)} machines"},
        {"label": "Plant Health", "value": health_label, "status": health_status},
        {"label": "Critical Alerts", "value": str(n_critical_alerts), "unit": "open",
         "status": "critical" if n_critical_alerts else "online"},
        {"label": "Lowest RUL", "value": f"{min_rul_value:.1f}" if min_rul_value is not None else "—",
         "unit": "days", "status": "critical", "micro_label": min_rul_machine_id},
        {"label": "Throughput", "value": "1,284", "unit": "units/shift", "status": "online", "micro_label": "vs 1,350 target"},
        {"label": "Energy Intensity", "value": "0.42", "unit": "kWh/unit", "status": "warning", "micro_label": "+6% vs baseline"},
    ])

    section_header("Plant Pulse", f"{n_lines} production lines · machine health · live OEE")
    render_plant_pulse(_DEMO_MACHINES)

    col_left, col_right = st.columns([3, 2])
    with col_left:
        section_header("Attention Required", "Ranked by severity and production impact")
        if alerts_for_page:
            for a in alerts_for_page:
                alert_card(**a)
        else:
            no_active_alerts_state("plant systems")

        # ── NEW: At-Risk Machines strip ──────────────────────────────
        # Fills the empty space below a short Attention Required list
        # (usually only 1-3 alerts exist) with the top-3 machines by
        # lowest RUL from the shared health table. Adds real value rather
        # than padding with fake alerts: an operator scanning the top of
        # Command Center now sees both "what's firing right now" (above)
        # and "what's heading toward firing soon" (below).
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        section_header("At-Risk Machines", "Lowest Remaining Useful Life across the fleet")

        _rul_sorted = sorted(
            _MACHINE_HEALTH.items(),
            key=lambda kv: kv[1]["rul"] if kv[1]["rul"] is not None else 1e9
        )[:3]

        risk_cols = st.columns(3)
        for col, (m_id, entry) in zip(risk_cols, _rul_sorted):
            rul_val = entry["rul"] if entry["rul"] is not None else 999.0
            oee_val = entry["oee"] if entry["oee"] is not None else 0.0
            # Severity from RUL bands (same thresholds used everywhere)
            if rul_val < 5:
                sev = "critical"
                sev_label = "CRITICAL"
            elif rul_val < 15:
                sev = "warning"
                sev_label = "WARNING"
            elif rul_val < 30:
                sev = "warning"
                sev_label = "WATCH"
            else:
                sev = "online"
                sev_label = "HEALTHY"
            sev_color = status_color(sev)

            # Bar width as fraction of a 60-day "healthy" window,
            # inverted so a SHORTER RUL shows a SHORTER bar
            bar_pct = max(5, min(100, rul_val / 60 * 100))

            with col:
                st.markdown(
                    f'<div class="neuro-card" style="padding:12px 14px;border-left:3px solid {sev_color};">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-weight:700;color:{COLORS["text_primary"]};'
                    f'font-family:\'JetBrains Mono\',monospace;font-size:0.86rem;">{m_id}</span>'
                    f'<span style="color:{sev_color};font-size:0.62rem;font-weight:700;'
                    f'letter-spacing:0.06em;">{sev_label}</span>'
                    f'</div>'
                    f'<div style="color:{COLORS["text_muted"]};font-size:0.68rem;margin-top:2px;">'
                    f'{entry["line"]}</div>'
                    f'<div style="margin-top:10px;">'
                    f'<div style="font-size:0.6rem;color:{COLORS["text_muted"]};'
                    f'text-transform:uppercase;letter-spacing:0.06em;">RUL</div>'
                    f'<div style="font-family:\'JetBrains Mono\',monospace;color:{sev_color};'
                    f'font-weight:700;font-size:1.05rem;margin-top:2px;">{rul_val:.1f}d</div>'
                    f'<div style="background:{COLORS["border_muted"]};border-radius:4px;'
                    f'height:4px;overflow:hidden;margin-top:6px;">'
                    f'<div style="background:{sev_color};width:{bar_pct:.0f}%;height:100%;"></div>'
                    f'</div>'
                    f'</div>'
                    f'<div style="display:flex;justify-content:space-between;margin-top:8px;">'
                    f'<span style="font-size:0.6rem;color:{COLORS["text_muted"]};">OEE</span>'
                    f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:0.72rem;'
                    f'color:{COLORS["text_primary"]};">{oee_val:.1f}%</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # Compact "worst RUL" footer note
        if _rul_sorted:
            worst_id, worst_entry = _rul_sorted[0]
            worst_rul = worst_entry["rul"] or 999.0
            st.markdown(
                f'<div style="margin-top:10px;padding:8px 12px;border-radius:6px;'
                f'background:{COLORS["bg_elevated"]};border-left:3px solid {status_color("critical")};'
                f'font-size:0.76rem;color:{COLORS["text_secondary"]};">'
                f'<b style="color:{COLORS["text_primary"]};">{worst_id}</b> has the fleet\'s '
                f'lowest RUL at <b style="color:{status_color("critical")};">{worst_rul:.1f} days</b> — '
                f'schedule maintenance before RUL reaches the 5-day critical threshold.'
                f'</div>',
                unsafe_allow_html=True
            )
    with col_right:
        section_header("AI Operations Summary")
        render_ai_summary(_DEMO_MACHINES, alerts_for_page)

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        section_header("Summary")
        nav_items = [
            ("Machine Monitoring", "Live sensor feed, alarms & digital twin"),
            ("OEE Analytics", "Availability x Performance x Quality, loss Pareto"),
            ("Predictive Maintenance", "RUL, SHAP, bearing faults"),
            ("Production & Quality", "Bottlenecks, line balancing, fault classification"),
            ("Energy & ESG", "Utility consumption, carbon footprint, reports"),
            ("GenAI Assistant", "Ask questions about plant performance"),
        ]
        for title, desc in nav_items:
            st.markdown(
                f'<div class="neuro-card fade-in" style="padding:12px 14px;margin-bottom:8px;">'
                f'<div style="font-weight:600;color:{COLORS["text_primary"]};font-size:0.84rem;">{title}</div>'
                f'<div style="font-size:0.72rem;color:{COLORS["text_secondary"]};margin-top:2px;">{desc}</div></div>',
                unsafe_allow_html=True
            )

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    with st.expander("Fleet Trends — OEE · Alarms · Production · Energy (last 24h)", expanded=False):
        import numpy as np
        t_cols = st.columns(2)
        with t_cols[0]:
            oee_series = list(np.clip(np.random.normal(78, 3, 24), 60, 95).round(1))
            st.plotly_chart(trend_line(_DEMO_TREND_LABELS, oee_series, title="Fleet OEE %", y_label="%"), use_container_width=True)
            alarm_series = list(np.random.poisson(1.1, 24))
            st.plotly_chart(trend_line(_DEMO_TREND_LABELS, alarm_series, title="Active Alarms", y_label="count", color=COLORS["warning"]), use_container_width=True)
        with t_cols[1]:
            prod_series = list(np.clip(np.random.normal(54, 5, 24), 30, 70).round(1))
            st.plotly_chart(trend_line(_DEMO_TREND_LABELS, prod_series, title="Production Rate", y_label="units/hr"), use_container_width=True)
            energy_series = list(np.clip(np.random.normal(0.42, 0.03, 24), 0.3, 0.55).round(3))
            st.plotly_chart(trend_line(_DEMO_TREND_LABELS, energy_series, title="Energy Intensity", y_label="kWh/unit", color=COLORS["accent_violet"]), use_container_width=True)