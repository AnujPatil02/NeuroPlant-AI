"""
OEE Analytics page - Layer 3. Manufacturing performance analysis workspace:
filters, OEE scoreboard, trend, Pareto loss analysis, shift table with
drill-down.

REVISION (single-source-of-truth + fallback consistency):
  Issue: when no OEERecord exists for a line (fresh DB, or before
  seed_demo_oee_data.py has been run), the fallback OEE was derived from
  random.Random(hash(line_id)) -- which produced numbers that disagreed
  with the per-machine OEE in machine_monitoring._MACHINE_HEALTH_STATIC
  and made OEE Analytics look like it was contradicting Machine Monitoring.

  Fix: fallback now derives line OEE from the SHARED machine health table
  (the same one home.py, machine_monitoring.py, predictive_maintenance.py,
  production_quality.py all read). Line OEE = mean of its machines' OEE.
  Once you run seed_demo_oee_data.py, real OEERecord rows take precedence
  and this fallback path never fires -- but when it does, the numbers now
  agree with what every other page shows.

Data note: OEE scoreboard (when OEERecord exists) and downtime Pareto are
REAL -- read directly from PostgreSQL. Trend line, component-breakdown-
by-shift chart, and shift table rows remain demo values (no historical
rollup query exists yet).
"""
import json
import os
import streamlit as st
from dashboard.ui.topbar import render_topbar
from dashboard.ui.theme import COLORS, status_color
from dashboard.ui.components import section_header, info_banner, breadcrumb
from dashboard.ui.charts import oee_gauge, pareto_bar, stacked_oee_components, trend_line, waterfall
from src.layer3_oee.models import SessionLocal, OEERecord
from src.layer3_oee.downtime_classifier import get_downtime_pareto

# FIX: path was os.path.join(dirname, "..", "..", "plant_topology.json")
# but pages live at neuroplant-ai/pages/ and topology at
# neuroplant-ai/config/plant_topology.json -- so it's ONE "..", not two.
_TOPOLOGY_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "plant_topology.json")

_DEMO_SHIFTS = [
    {"shift": "Morning - Thu", "shift_type": "Morning", "availability": 91.0, "performance": 87.0, "quality": 95.0, "oee": 75.2},
    {"shift": "Evening - Thu", "shift_type": "Evening", "availability": 88.0, "performance": 83.0, "quality": 93.0, "oee": 68.0},
    {"shift": "Night - Thu", "shift_type": "Night", "availability": 84.0, "performance": 80.0, "quality": 92.0, "oee": 61.8},
    {"shift": "Morning - Fri", "shift_type": "Morning", "availability": 93.0, "performance": 89.0, "quality": 96.0, "oee": 79.4},
    {"shift": "Evening - Fri", "shift_type": "Evening", "availability": 85.0, "performance": 79.0, "quality": 94.0, "oee": 71.0},
    {"shift": "Night - Fri", "shift_type": "Night", "availability": 82.0, "performance": 78.0, "quality": 91.0, "oee": 58.2},
    {"shift": "Morning - Sat", "shift_type": "Morning", "availability": 92.0, "performance": 88.0, "quality": 96.0, "oee": 77.7},
]

_DEMO_TREND_SHIFTS = ["Mon AM", "Mon PM", "Tue AM", "Tue PM", "Wed AM", "Wed PM", "Thu AM",
                      "Thu PM", "Fri AM", "Fri PM", "Sat AM", "Sat PM", "Sun AM", "Sun PM"]
_DEMO_AVAILABILITY = [88, 90, 85, 92, 89, 87, 91, 86, 90, 84, 93, 88, 89, 91]
_DEMO_PERFORMANCE = [82, 79, 88, 85, 87, 81, 84, 83, 86, 80, 89, 85, 82, 87]
_DEMO_QUALITY = [94, 96, 91, 95, 93, 94, 92, 95, 96, 91, 97, 94, 93, 95]

_DATE_RANGE_DAYS = {"Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 14}

# Line id -> human-readable line_name in plant_topology.json
_LINE_NAME_BY_ID = {
    "LINE01": "Component Machining",
    "LINE02": "Precision Machining",
    "LINE03": "Finishing / Component Processing",
}

# ── Shared machine health table import (same pattern as home.py,
#    predictive_maintenance.py, production_quality.py) ──────────────────
_INLINE_MACHINE_HEALTH_STATIC = {
    "CNC-01": {"line": "Component Machining", "oee": "94.2%"},
    "CNC-02": {"line": "Component Machining", "oee": "41.0%"},
    "CNC-03": {"line": "Component Machining", "oee": "95.1%"},
    "CNC-04": {"line": "Component Machining", "oee": "94.6%"},
    "CNC-05": {"line": "Precision Machining", "oee": "95.4%"},
    "CNC-06": {"line": "Precision Machining", "oee": "95.8%"},
    "CNC-07": {"line": "Precision Machining", "oee": "71.4%"},
    "CNC-08": {"line": "Precision Machining", "oee": "68.2%"},
    "CNC-09": {"line": "Finishing / Component Processing", "oee": "96.0%"},
    "CNC-10": {"line": "Finishing / Component Processing", "oee": "95.7%"},
    "CNC-11": {"line": "Finishing / Component Processing", "oee": "93.8%"},
    "CNC-12": {"line": "Finishing / Component Processing", "oee": "94.9%"},
    "ASM-01": {"line": "Automated Assembly", "oee": "96.5%"},
}


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


_SHARED_TABLE = _try_import_shared_table() or _INLINE_MACHINE_HEALTH_STATIC


def _load_line_ids() -> list:
    """Real line roster from plant_topology.json -- LINE01/02/03."""
    try:
        with open(_TOPOLOGY_PATH, "r") as f:
            topo = json.load(f)
        lines = []
        for factory in topo.get("factories", []):
            for line in factory.get("lines", []):
                lines.append(line["line_id"])
        if lines:
            return lines
    except Exception:
        pass
    return ["LINE01", "LINE02", "LINE03"]


def _fallback_a_p_q_from_shared(line_id: str) -> tuple:
    """Derives (availability, performance, quality, oee) for a line from
    the SHARED _MACHINE_HEALTH_STATIC machine OEE values. Line OEE = mean
    of its machines' OEE. A/P/Q are split back out using stable, realistic
    ratios so the numbers look like a real shift's A/P/Q and always
    multiply back to the line OEE exactly."""
    import re
    line_name = _LINE_NAME_BY_ID.get(line_id)
    machine_oees = []
    for m_id, entry in _SHARED_TABLE.items():
        if entry.get("line") != line_name:
            continue
        m = re.search(r"(\d+\.?\d*)", str(entry.get("oee", "")))
        if m:
            machine_oees.append(float(m.group()) / 100.0)   # "94.2%" -> 0.942

    if not machine_oees:
        # Truly nothing to work with -- conservative fallback that at
        # least doesn't claim a suspiciously round 75%.
        return 0.90, 0.85, 0.95, 0.90 * 0.85 * 0.95

    oee = sum(machine_oees) / len(machine_oees)
    # Split into A/P/Q with realistic shift-level ratios. The choice:
    # quality ~96-97% (machined parts are usually high-quality),
    # availability ~91-93%, performance absorbs the residual. Then
    # quality is fine-tuned so A*P*Q == OEE exactly.
    qual = 0.965
    avail = min(oee / qual / 0.90, 0.97)   # solve for avail given perf ~0.90 first
    perf = oee / (avail * qual)
    # Clamp to plausible ranges and re-solve quality last to keep product exact
    avail = min(max(avail, 0.80), 0.97)
    perf = min(max(perf, 0.75), 0.98)
    qual = oee / (avail * perf)
    qual = min(max(qual, 0.85), 0.99)
    # Final tiny correction so A*P*Q == OEE to 4 decimals
    oee = round(avail * perf * qual, 4)
    return round(avail, 4), round(perf, 4), round(qual, 4), oee


def render():
    render_topbar("OEE Analytics", "Layer 3 - Availability x Performance x Quality", breadcrumb="Home")

    line_ids = _load_line_ids()

    f_cols = st.columns([2, 2, 2, 3])
    with f_cols[0]:
        st.markdown(
            f'<div style="margin-top:2px;">'
            f'<div style="color:{COLORS["text_secondary"]};font-size:0.82rem;margin-bottom:4px;">Plant</div>'
            f'<div style="background:{COLORS["bg_input"]};border:1px solid {COLORS["border"]};border-radius:6px;'
            f'padding:9px 12px;color:{COLORS["text_primary"]};font-size:0.9rem;">FAC01</div></div>',
            unsafe_allow_html=True
        )
    with f_cols[1]:
        selected_line = st.selectbox("Line", line_ids, key="oee_filter_line")
    with f_cols[2]:
        selected_shift = st.selectbox("Shift", ["All Shifts", "Morning", "Evening", "Night"], key="oee_filter_shift")
    with f_cols[3]:
        selected_range = st.selectbox("Date Range", list(_DATE_RANGE_DAYS.keys()), key="oee_filter_range")

    line_display = selected_line.replace("LINE", "LINE ")
    st.markdown(breadcrumb(["NEUROPLANT", line_display]), unsafe_allow_html=True)

    # ── Primary: real seeded OEERecord from Postgres ─────────────────
    session = SessionLocal()
    latest = (session.query(OEERecord)
              .filter(OEERecord.line_id == selected_line)
              .order_by(OEERecord.timestamp.desc(), OEERecord.id.desc())
              .first())
    session.close()

    if latest:
        avail, perf, qual, oee = latest.availability, latest.performance, latest.quality, latest.oee
        data_is_live = True
    else:
        # ── Fallback: derive from shared machine health table so this
        #    page doesn't contradict Machine Monitoring / Command Center.
        avail, perf, qual, oee = _fallback_a_p_q_from_shared(selected_line)
        data_is_live = False

    if not data_is_live:
        info_banner(
            f"No OEE record found yet for {selected_line} - showing line OEE derived from the "
            f"shared machine health table (same source as Machine Monitoring and Command Center). "
            f"Run `python -m scripts.seed_demo_oee_data` to populate real shift-level records.",
            tone="maintenance"
        )

    section_header("OEE Scoreboard", selected_line)
    score_cols = st.columns([2, 1, 1, 1])
    with score_cols[0]:
        st.plotly_chart(oee_gauge(oee * 100, title="Overall OEE"), use_container_width=True)
    for col, (label, val) in zip(score_cols[1:], [("Availability", avail), ("Performance", perf), ("Quality", qual)]):
        with col:
            color = status_color("online" if val >= 0.85 else "warning" if val >= 0.7 else "critical")
            st.markdown(
                f'<div class="neuro-card" style="text-align:center;padding:18px 12px;border-top:2px solid {color};">'
                f'<div style="font-size:0.68rem;color:{COLORS["text_secondary"]};text-transform:uppercase;letter-spacing:0.07em;">{label}</div>'
                f'<div style="font-size:1.9rem;font-weight:700;color:{COLORS["text_primary"]};font-family:\'JetBrains Mono\',monospace;margin-top:8px;">{val*100:.1f}%</div>'
                f'</div>', unsafe_allow_html=True
            )

    # ---- Date Range now actually clips the demo trend series ----
    n_points = _DATE_RANGE_DAYS.get(selected_range, 7)
    range_note = "demo series pending historical rollup query"
    if selected_range == "Last 30 Days":
        range_note = "demo series only has 14 sample points — showing max available"
    section_header("OEE Trend", f"Target 85% - {range_note}")
    trend_labels = _DEMO_TREND_SHIFTS[-n_points:]
    avail_slice = _DEMO_AVAILABILITY[-n_points:]
    perf_slice = _DEMO_PERFORMANCE[-n_points:]
    qual_slice = _DEMO_QUALITY[-n_points:]
    trend_values = [round((a/100 * p/100 * q/100) * 100, 1) for a, p, q in zip(avail_slice, perf_slice, qual_slice)]
    fig = trend_line(trend_labels, trend_values, title="OEE % by Shift", y_label="%")
    fig.add_hline(y=85, line_dash="dash", line_color=COLORS["text_muted"],
                  annotation_text="Target 85%", annotation_font_color=COLORS["text_muted"])
    st.plotly_chart(fig, use_container_width=True)

    section_header("Loss Analysis", "Downtime reasons - Pareto")
    pareto = get_downtime_pareto(selected_line)
    if pareto:
        labels = list(pareto.keys())
        values = list(pareto.values())
        top_idx = values.index(max(values))
        fig = pareto_bar(labels, values, "Downtime Minutes by Reason Code", highlight_index=top_idx)
        if len(labels) == 1:
            fig.update_layout(xaxis=dict(range=[-1.5, 1.5]), bargap=0.6)

        if len(labels) >= 2:
            total = sum(values)
            cumulative_pct = []
            running = 0
            sorted_pairs = sorted(zip(labels, values), key=lambda x: -x[1])
            for _, v in sorted_pairs:
                running += v
                cumulative_pct.append(round(running / total * 100, 1))
            fig.add_scatter(x=[l for l, _ in sorted_pairs],
                            y=[c * max(values) / 100 for c in cumulative_pct],
                            mode="lines+markers", name="Cumulative %", yaxis="y2",
                            line=dict(color=COLORS["accent_bright"], width=2, dash="dot"))
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 100],
                                           showgrid=False,
                                           tickfont=dict(color=COLORS["text_secondary"])))
        st.plotly_chart(fig, use_container_width=True)
        if len(labels) < 2:
            info_banner(
                f"Only one downtime reason code ({labels[0]}) has been logged for {selected_line} so far — "
                f"log more downtime events via POST /oee/downtime to see a full Pareto breakdown.",
                tone="maintenance"
            )

        avail_loss = round((1 - avail) * 100, 1)
        perf_loss = round((avail * (1 - perf)) * 100, 1)
        qual_loss = round((avail * perf * (1 - qual)) * 100, 1)
        st.plotly_chart(
            waterfall(
                ["Theoretical Max", "Availability Loss", "Performance Loss", "Quality Loss", "Actual OEE"],
                [100, -avail_loss, -perf_loss, -qual_loss, oee * 100],
                title="OEE Loss Waterfall",
                measure=["absolute", "relative", "relative", "relative", "total"],
            ),
            use_container_width=True
        )
    else:
        from dashboard.ui.components import data_source_offline_state
        data_source_offline_state("OEE downtime event log")

    section_header("OEE Component Breakdown", f"{selected_range} - demo series")
    st.plotly_chart(
        stacked_oee_components(trend_labels, avail_slice, perf_slice, qual_slice),
        use_container_width=True
    )

    visible_shifts = _DEMO_SHIFTS if selected_shift == "All Shifts" else [
        s for s in _DEMO_SHIFTS if s["shift_type"] == selected_shift
    ]

    section_header("Shift Performance", f"{selected_shift} - click a shift to see its A/P/Q breakdown")
    if "oee_drilldown_shift" not in st.session_state:
        st.session_state["oee_drilldown_shift"] = None

    if not visible_shifts:
        info_banner(f"No shifts match the '{selected_shift}' filter in the demo dataset.", tone="maintenance")
    else:
        header_cols = st.columns([2, 1, 1, 1, 1, 1])
        for col, label in zip(header_cols, ["Shift", "Availability", "Performance", "Quality", "OEE", ""]):
            col.markdown(f'<span style="color:{COLORS["text_secondary"]};font-size:0.78rem;font-weight:600;">{label}</span>', unsafe_allow_html=True)

        for shift in visible_shifts:
            row_cols = st.columns([2, 1, 1, 1, 1, 1])
            oee_color = status_color("online" if shift["oee"] >= 75 else "warning" if shift["oee"] >= 60 else "critical")
            row_cols[0].markdown(f'<span style="color:{COLORS["text_primary"]};font-size:0.85rem;">{shift["shift"]}</span>', unsafe_allow_html=True)
            row_cols[1].markdown(f'<span style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};font-size:0.85rem;">{shift["availability"]:.1f}%</span>', unsafe_allow_html=True)
            row_cols[2].markdown(f'<span style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};font-size:0.85rem;">{shift["performance"]:.1f}%</span>', unsafe_allow_html=True)
            row_cols[3].markdown(f'<span style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};font-size:0.85rem;">{shift["quality"]:.1f}%</span>', unsafe_allow_html=True)
            row_cols[4].markdown(f'<span style="font-family:\'JetBrains Mono\',monospace;color:{oee_color};font-weight:700;font-size:0.85rem;">{shift["oee"]:.1f}%</span>', unsafe_allow_html=True)
            with row_cols[5]:
                if st.button("Detail", key=f"drill_{shift['shift']}"):
                    current = st.session_state["oee_drilldown_shift"]
                    st.session_state["oee_drilldown_shift"] = None if current == shift["shift"] else shift["shift"]
                    st.rerun()

        drilldown = st.session_state.get("oee_drilldown_shift")
        if drilldown:
            selected = next((s for s in visible_shifts if s["shift"] == drilldown), None)
            if selected:
                st.markdown(
                    f'<div class="neuro-card" style="border-left:3px solid {COLORS["accent"]};margin-top:10px;">'
                    f'<div style="font-weight:600;color:{COLORS["text_primary"]};margin-bottom:8px;">{drilldown} - Component Breakdown</div>'
                    f'<div style="display:flex;gap:24px;">'
                    + "".join([
                        f'<div><div style="font-size:0.68rem;color:{COLORS["text_secondary"]};text-transform:uppercase;">{k}</div>'
                        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:1.1rem;color:{COLORS["text_primary"]};font-weight:600;">{v:.1f}%</div></div>'
                        for k, v in [("Availability", selected["availability"]), ("Performance", selected["performance"]), ("Quality", selected["quality"])]
                    ])
                    + '</div></div>', unsafe_allow_html=True
                )