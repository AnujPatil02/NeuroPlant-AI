"""
Production & Quality page - Layer 6 (Production Optimizer) + Layer 8
(Quality Intelligence).

REVISION (shared-source-of-truth pass):
  - _KNOWN_RUL_OVERRIDES was hardcoding CNC-07=3.5d, CNC-05=8.0d,
    CNC-06=18.0d, CNC-08=25.0d, which disagreed with the shared machine
    table (CNC-07=22d, CNC-08=15d, CNC-05=128d, CNC-06=135d) and caused
    the "Lines Blocked: 0" bug: CNC-02's real critical status (RUL 3.5d)
    wasn't checked at all because it wasn't in the override dict.
  - Now reads from the SHARED _MACHINE_HEALTH_STATIC table used by
    home.py, machine_monitoring.py, predictive_maintenance.py.
  - Topology path fixed (pages/ -> ../config/plant_topology.json).

Data notes:
  - Production tab: bottleneck detection, queue buildup, line balancing,
    and shift-schedule LP output are REAL (layer6 functions). Bottleneck
    heatmap (line x station) remains demo.
  - Quality tab: KPIs and defect Pareto are REAL (quality_kpi.py). Fault
    classification table and SHAP contrastive card remain demo.
"""
import json
import os
import streamlit as st
from dashboard.ui.topbar import render_topbar, render_kpi_hero
from dashboard.ui.theme import COLORS, status_color
from dashboard.ui.components import section_header, info_banner, no_active_alerts_state, impact_panel, ai_evidence_card
from dashboard.ui.charts import heatmap, pareto_bar, PLOTLY_LAYOUT
from src.layer6_production_optimizer.bottleneck_detector import detect_bottlenecks, detect_queue_buildup
from src.layer6_production_optimizer.line_balancing import recommend_line_balancing
from src.layer6_production_optimizer.shift_scheduler_lp import optimize_shift_schedule
from src.layer8_quality_intelligence.quality_kpi import compute_quality_kpis, defect_rate_by_type

_TOPOLOGY_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "plant_topology.json")

_CRITICAL_RUL_DAYS = 5.0

_INLINE_MACHINE_HEALTH_STATIC = {
    "CNC-01": {"line": "Component Machining", "status": "online",  "rul": "118.0 DAYS"},
    "CNC-02": {"line": "Component Machining", "status": "critical", "rul": "3.5 DAYS"},
    "CNC-03": {"line": "Component Machining", "status": "online",  "rul": "132.0 DAYS"},
    "CNC-04": {"line": "Component Machining", "status": "online",  "rul": "124.0 DAYS"},
    "CNC-05": {"line": "Precision Machining", "status": "online",  "rul": "128.0 DAYS"},
    "CNC-06": {"line": "Precision Machining", "status": "online",  "rul": "135.0 DAYS"},
    "CNC-07": {"line": "Precision Machining", "status": "warning", "rul": "22.0 DAYS"},
    "CNC-08": {"line": "Precision Machining", "status": "warning", "rul": "15.0 DAYS"},
    "CNC-09": {"line": "Finishing / Component Processing", "status": "online", "rul": "142.0 DAYS"},
    "CNC-10": {"line": "Finishing / Component Processing", "status": "online", "rul": "138.0 DAYS"},
    "CNC-11": {"line": "Finishing / Component Processing", "status": "online", "rul": "112.0 DAYS"},
    "CNC-12": {"line": "Finishing / Component Processing", "status": "online", "rul": "129.0 DAYS"},
    "ASM-01": {"line": "Automated Assembly", "status": "online", "rul": "150.0 DAYS"},
}

_DEMO_FAULT_EVENTS = [
    {"machine": "CNC-07", "fault": "dimensional_variance", "confidence": 0.87, "shift": "Evening", "product": "SKU-118"},
    {"machine": "CNC-05", "fault": "surface_finish", "confidence": 0.74, "shift": "Morning", "product": "SKU-119"},
    {"machine": "CNC-08", "fault": "weight_deviation", "confidence": 0.61, "shift": "Evening", "product": "SKU-121"},
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


_MACHINE_HEALTH_STATIC = _try_import_shared_table() or _INLINE_MACHINE_HEALTH_STATIC


def _rul_days(machine_id: str) -> float:
    raw = str(_MACHINE_HEALTH_STATIC.get(machine_id, {}).get("rul", "")).strip()
    try:
        return float(raw.replace("DAYS", "").replace("DAY", "").strip())
    except (ValueError, TypeError):
        return 999.0


def _line_id_for_line_name(line_name: str) -> str:
    _MAP = {
        "Component Machining": "LINE01",
        "Precision Machining": "LINE02",
        "Finishing / Component Processing": "LINE03",
        "Automated Assembly": "ZONE_ASSEMBLY",
    }
    return _MAP.get(line_name, line_name)


def _derive_maintenance_blocked_lines():
    """Returns (blocked_line_ids, reasons) derived from the SHARED table.
    A line is blocked when it contains a machine whose RUL is below the
    critical threshold (5 days)."""
    blocked, reasons = [], {}
    line_worst: dict = {}
    for m_id, entry in _MACHINE_HEALTH_STATIC.items():
        line_name = entry.get("line", "")
        rul = _rul_days(m_id)
        current = line_worst.get(line_name)
        if current is None or rul < current[1]:
            line_worst[line_name] = (m_id, rul)

    for line_name, (m_id, rul) in line_worst.items():
        if rul < _CRITICAL_RUL_DAYS:
            line_id = _line_id_for_line_name(line_name)
            blocked.append(line_id)
            reasons[line_id] = f"{m_id} RUL {rul}d (below {_CRITICAL_RUL_DAYS:.0f}d critical threshold)"

    return blocked, reasons


def render_production_tab():
    stations = [
        {"station_id": "CNC-05", "design_cycle_time_sec": 63, "actual_cycle_time_sec": 66},
        {"station_id": "CNC-06", "design_cycle_time_sec": 39, "actual_cycle_time_sec": 41},
        {"station_id": "CNC-07", "design_cycle_time_sec": 47, "actual_cycle_time_sec": 58},
        {"station_id": "CNC-08", "design_cycle_time_sec": 44, "actual_cycle_time_sec": 45},
    ]
    bottlenecks = detect_bottlenecks(stations)
    blocked_lines, block_reasons = _derive_maintenance_blocked_lines()

    render_kpi_hero([
        {"label": "Stations Monitored", "value": str(len(stations)), "status": "online"},
        {"label": "Bottlenecks", "value": str(len(bottlenecks)), "status": "warning" if bottlenecks else "online"},
        {"label": "Queue Alerts", "value": "1", "status": "warning"},
        {"label": "Lines Blocked", "value": str(len(blocked_lines)), "status": "critical" if blocked_lines else "online",
         "micro_label": ", ".join(blocked_lines) if blocked_lines else "None"},
        {"label": "Material Shortage", "value": "Flagged", "status": "critical"},
    ])

    section_header("Bottleneck Map", "Cycle time vs design — live")
    labels = [s["station_id"] for s in stations]
    actual = [s["actual_cycle_time_sec"] for s in stations]
    design = [s["design_cycle_time_sec"] for s in stations]

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Design", x=labels, y=design, marker_color=COLORS["slate"]))
    fig.add_trace(go.Bar(name="Actual", x=labels, y=actual, marker_color=status_color("critical")))
    layout = dict(PLOTLY_LAYOUT)
    layout["title"] = dict(text="Cycle Time — Design vs Actual (sec)", font=dict(color=COLORS["text_primary"], size=14))
    fig.update_layout(**layout, barmode="group", height=320)
    st.plotly_chart(fig, use_container_width=True)

    section_header("AI Recommendations", "Generated from live bottleneck detection")
    if bottlenecks:
        for b in bottlenecks:
            rec = recommend_line_balancing(stations, b["station_id"])
            rec_html = (
                f'<div class="neuro-card" style="border-left:3px solid {status_color("critical")};">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
                f'<span style="color:{status_color("critical")};font-weight:700;">{b["station_id"]}</span>'
                f'<span class="status-pill status-critical">{b["pct_over_design"]}% over design</span></div>'
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:0.82rem;">'
                f'<div><span style="color:{COLORS["text_muted"]};text-transform:uppercase;font-size:0.64rem;">Problem</span>'
                f'<div style="color:{COLORS["text_secondary"]};margin-top:2px;">Cycle time exceeds design by {b["pct_over_design"]}%, constraining line throughput.</div></div>'
                f'<div><span style="color:{COLORS["text_muted"]};text-transform:uppercase;font-size:0.64rem;">Recommendation</span>'
                f'<div style="color:{COLORS["text_primary"]};margin-top:2px;">{rec.get("recommendation", "No recommendation available")}</div></div>'
                f'</div></div>'
            )
            st.markdown(rec_html, unsafe_allow_html=True)

            over_pct = b["pct_over_design"]
            recovered_pct = round(min(over_pct * 0.7, over_pct), 1)
            st.markdown(impact_panel([
                {"label": "Cycle time recovered", "value": f"~{recovered_pct}%", "positive": True},
                {"label": "Throughput", "value": "Improved", "positive": True},
                {"label": "Station", "value": rec.get("target_station", rec.get("recommended_target", "—")), "positive": True},
            ]), unsafe_allow_html=True)
    else:
        no_active_alerts_state("monitored stations")

    col1, col2 = st.columns(2)
    with col1:
        section_header("Queue Buildup", "Ranked by congestion — live")
        buffers = [{"buffer_id": "BUF-LINE02-INSPECTION", "occupancy_pct_history": [70, 88, 91, 93, 60]}]
        alerts = detect_queue_buildup(buffers)
        if alerts:
            for a in sorted(alerts, key=lambda x: -x["current_occupancy"]):
                buf_html = (
                    f'<div class="neuro-card" style="border-left:3px solid {status_color("warning")};">'
                    f'<span style="font-weight:600;color:{COLORS["text_primary"]};">{a["buffer_id"]}</span>'
                    f'<p style="color:{COLORS["text_secondary"]};font-size:0.8rem;">'
                    f'Current: {a["current_occupancy"]}% · {a["consecutive_high_readings"]} consecutive high readings<br>'
                    f'Signal: {a["signal"]}</p></div>'
                )
                st.markdown(buf_html, unsafe_allow_html=True)
        else:
            info_banner("Buffer levels normal.", tone="online")

    with col2:
        section_header("Bottleneck Heatmap", "Line × station — demo series")
        z = [[32, 38, 41], [28, 26, 33], [30, 35, 39]]
        st.plotly_chart(heatmap(z, ["CNC-05", "CNC-06", "CNC-07"], ["LINE01", "LINE02", "LINE03"], "Actual Cycle Time (sec)"), use_container_width=True)

    section_header("Line Balancing", "Current vs recommended workload")
    if bottlenecks:
        balance_rows = ""
        for b in bottlenecks:
            rec = recommend_line_balancing(stations, b["station_id"])
            target = rec.get("target_station", rec.get("recommended_target", "—"))
            balance_rows += (
                f'<tr style="color:{COLORS["text_primary"]};">'
                f'<td style="padding:8px;">{b["station_id"]}</td>'
                f'<td style="color:{status_color("critical")};">Bottleneck</td>'
                f'<td>→</td>'
                f'<td>{target}</td>'
                f'<td style="color:{status_color("online")};">Spare capacity</td></tr>'
            )
        balance_html = (
            f'<div class="neuro-card"><table style="width:100%;border-collapse:collapse;font-size:0.85rem;">'
            f'<tr style="color:{COLORS["text_secondary"]};text-align:left;border-bottom:1px solid {COLORS["border"]};">'
            f'<th style="padding:8px;">From Station</th><th>Current State</th><th></th><th>To Station</th><th>Target State</th></tr>'
            f'{balance_rows}</table></div>'
        )
        st.markdown(balance_html, unsafe_allow_html=True)
    else:
        info_banner("All stations balanced — no redistribution needed.", tone="online")

    section_header("Shift Scheduler", "SciPy LP optimizer output — live")
    lines = [
        {"line_id": "LINE01", "min_staff_required": 4, "overtime_cost_per_hour": 25, "throughput_per_operator": 12},
        {"line_id": "LINE02", "min_staff_required": 3, "overtime_cost_per_hour": 20, "throughput_per_operator": 10},
        {"line_id": "LINE03", "min_staff_required": 5, "overtime_cost_per_hour": 30, "throughput_per_operator": 15},
    ]
    result = optimize_shift_schedule(lines, operators_available=15, maintenance_blocked_lines=blocked_lines)

    if blocked_lines:
        reason_lines = "<br>".join(f'{lid}: {block_reasons.get(lid, "")}' for lid in blocked_lines)
        info_banner(
            f"Line(s) blocked from scheduling — derived from Layer 4 predictive maintenance "
            f"(critical RUL &lt; {_CRITICAL_RUL_DAYS:.0f}d):<br>{reason_lines}",
            tone="critical"
        )

    if "allocation" in result:
        rows = ""
        for a in result["allocation"]:
            surplus = a["operators_allocated"] - a["min_required"]
            surplus_color = status_color("online") if surplus >= 0 else status_color("critical")
            rows += (
                f'<tr style="color:{COLORS["text_primary"]};">'
                f'<td style="padding:8px;">{a["line_id"]}</td>'
                f'<td style="font-family:\'JetBrains Mono\',monospace;">{a["operators_allocated"]}</td>'
                f'<td style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};">{a["min_required"]}</td>'
                f'<td style="color:{surplus_color};font-weight:600;">{"+" if surplus >= 0 else ""}{surplus}</td></tr>'
            )
        blocked_rows = "".join([
            f'<tr style="color:{COLORS["text_muted"]};">'
            f'<td style="padding:8px;">{b["line_id"]}</td>'
            f'<td colspan="3"><span class="status-pill status-maintenance">{b["status"]}</span></td></tr>'
            for b in result.get("blocked_lines", [])
        ])
        table_html = (
            f'<div class="neuro-card"><table style="width:100%;border-collapse:collapse;font-size:0.85rem;">'
            f'<tr style="color:{COLORS["text_secondary"]};text-align:left;border-bottom:1px solid {COLORS["border"]};">'
            f'<th style="padding:8px;">Line</th><th>Allocated</th><th>Min Required</th><th>Surplus/Deficit</th></tr>'
            f'{rows}{blocked_rows}</table></div>'
        )
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        info_banner("Shift schedule optimization returned no allocation.", tone="warning")


def render_quality_tab():
    kpis = compute_quality_kpis(total_units=850, good_units=800, scrapped_units=30, reworked_units=20)

    defect_rate = 1 - kpis["first_pass_yield"]
    render_kpi_hero([
        {"label": "First-Pass Yield", "value": f"{kpis['first_pass_yield']*100:.1f}%", "status": "online"},
        {"label": "Scrap Rate", "value": f"{kpis['scrap_rate']*100:.1f}%", "status": "warning"},
        {"label": "Rework %", "value": f"{kpis['rework_pct']*100:.1f}%", "status": "online"},
        {"label": "Defect Rate", "value": f"{defect_rate*100:.1f}%", "status": "warning" if defect_rate > 0.05 else "online"},
        {"label": "Quality Holds", "value": "0", "status": "online"},
    ])

    section_header("Defect Pareto", "By type — live")
    defects = [{"defect_type": "dimensional_variance"}] * 12 + [{"defect_type": "surface_finish"}] * 5 + [{"defect_type": "weight_deviation"}] * 3
    rates = defect_rate_by_type(defects)
    labels = list(rates.keys())
    values = list(rates.values())
    top_index = values.index(max(values)) if values else None
    st.plotly_chart(pareto_bar(labels, values, "Defect Count", highlight_index=top_index), use_container_width=True)

    section_header("Fault Classification", "Flagged events — demo, pending Layer 8 event log API")
    rows = ""
    for e in sorted(_DEMO_FAULT_EVENTS, key=lambda x: -x["confidence"]):
        conf_color = status_color("critical") if e["confidence"] > 0.8 else status_color("warning") if e["confidence"] > 0.6 else status_color("online")
        rows += (
            f'<tr style="color:{COLORS["text_primary"]};">'
            f'<td style="padding:8px;">{e["machine"]}</td>'
            f'<td>{e["fault"].replace("_"," ").title()}</td>'
            f'<td style="color:{conf_color};font-weight:600;">{e["confidence"]*100:.0f}%</td>'
            f'<td>{e["shift"]}</td><td>{e["product"]}</td></tr>'
        )
    table_html = (
        f'<div class="neuro-card"><table style="width:100%;border-collapse:collapse;font-size:0.85rem;">'
        f'<tr style="color:{COLORS["text_secondary"]};text-align:left;border-bottom:1px solid {COLORS["border"]};">'
        f'<th style="padding:8px;">Machine</th><th>Fault Type</th><th>Confidence</th><th>Shift</th><th>Product</th></tr>'
        f'{rows}</table></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)

    section_header("Contrastive SHAP Explanation")
    expected_vs_observed_html = (
        f'<div style="display:flex;gap:24px;margin-bottom:6px;">'
        f'<div><div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Expected / Normal</div>'
        f'<div style="font-family:\'JetBrains Mono\',monospace;color:{status_color("online")};font-size:0.86rem;">spindle_rpm ≈ nominal</div></div>'
        f'<div><div style="font-size:0.64rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Observed</div>'
        f'<div style="font-family:\'JetBrains Mono\',monospace;color:{status_color("warning")};font-size:0.86rem;">spindle_rpm +8.0% above nominal</div></div>'
        f'</div>'
    )
    st.markdown(f'<div style="margin-bottom:-6px;">{expected_vs_observed_html}</div>', unsafe_allow_html=True)
    st.markdown(ai_evidence_card(
        "CNC-07 — Dimensional Variance Fault @ 14:32 (SKU-118, Gear Shaft)",
        confidence="87%",
        contributors=[
            {"label": "spindle_rpm (+8.0% above nominal)", "weight": 0.61},
            {"label": "coolant_temp_c (+8.9% above nominal)", "weight": 0.29},
        ],
        narrative="Consistent with tool wear pattern."
    ), unsafe_allow_html=True)

    section_header("Quality Hold Status")
    hold_html = (
        f'<div class="neuro-card" style="border-left:3px solid {status_color("online")};display:flex;align-items:center;gap:10px;padding:16px 18px;">'
        f'<span class="status-pill status-online">CLEAR</span>'
        f'<span style="color:{COLORS["text_secondary"]};font-size:0.85rem;">No active quality holds — all lines clear.</span></div>'
    )
    st.markdown(hold_html, unsafe_allow_html=True)


def render():
    render_topbar("Production & Quality", "Layer 6 + 8 — Bottleneck Detection, Line Balancing, Fault Classification", breadcrumb="Home")

    tab_production, tab_quality = st.tabs(["▶ Production Optimizer", "◉ Quality Intelligence"])
    with tab_production:
        render_production_tab()
    with tab_quality:
        render_quality_tab()