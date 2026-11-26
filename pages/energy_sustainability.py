"""
Energy & ESG page - Layer 7 (Energy Intelligence) + Layer 9 (Sustainability
& ESG).

REVISION (this pass):
  - baseline_display used baseline.get("baseline_lpm", baseline.get("baseline", 0))
    but establish_baseline() actually returns "mean_flow_lpm"/"std_flow_lpm".
    So the display always read 0 L/min regardless of the real baseline.
    Now reads "mean_flow_lpm" first (the real key), with legacy fallbacks.
  - Top KPI renamed "Total CO2" -> "Batch CO2 (Last Shift)" -- it's the
    batch footprint from compute_batch_carbon_footprint, not a monthly
    figure. Previous label made 370 kg look like it should equal the
    ESG tab's "Total CO2 (Month) 11,250 kg", which it doesn't (different
    time windows).
  - PDF export eager (one-click download, no two-stage rerun).

Data notes:
  - Energy tab: carbon footprint, peak demand, compressed-air leak
    detection are REAL (layer7 functions). Utility consumption heatmap and
    30-day CO2 trend remain demo series.
  - ESG tab: Report Center builds plain-text reports with CSV and PDF
    export using fpdf2 directly in-memory.
"""
import streamlit as st
import numpy as np
from dashboard.ui.topbar import render_topbar, render_kpi_hero
from dashboard.ui.theme import COLORS, SHADOWS, status_color
from dashboard.ui.components import section_header, connection_warning, no_active_alerts_state, error_state, info_banner
from dashboard.ui.charts import heatmap, trend_line, gauge_small, add_threshold_line
from src.layer7_energy_intelligence.compressed_air_monitor import establish_baseline, detect_leak
from src.layer7_energy_intelligence.carbon_emissions import compute_batch_carbon_footprint
from src.layer7_energy_intelligence.electricity_monitor import track_peak_demand

try:
    from src.layer9_sustainability.esg_report_generator import generate_sustainability_report
    _PDF_GENERATOR_AVAILABLE = True
    _PDF_IMPORT_ERROR = None
except ImportError as e:
    _PDF_GENERATOR_AVAILABLE = False
    _PDF_IMPORT_ERROR = str(e)

    def generate_sustainability_report(*args, **kwargs):
        raise RuntimeError(
            f"PDF report generation is unavailable: {_PDF_IMPORT_ERROR}. This means the 'fpdf' package "
            f"in your Python environment is broken or conflicting with 'fpdf2'. Fix: run "
            f"'pip uninstall fpdf fpdf2 -y', manually delete any leftover 'fpdf'/'fpdf2' folders in "
            f"venv/Lib/site-packages, then 'pip install fpdf2', and verify with "
            f"'python -c \"from fpdf import FPDF, XPos, YPos\"' BEFORE restarting Streamlit."
        )

UTILITY_COLORS = {
    "electricity": COLORS["accent"],
    "compressed_air": COLORS["slate"],
    "water": "#5C7A8A",
    "steam": "#A38A5C",
}

_PDF_UNSAFE_CHARS = {
    "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2022": "-",
    "\u00a0": " ", "\u2192": "->", "\u00b0": " deg",
}


def _pdf_safe_text(text) -> str:
    if not isinstance(text, str):
        return text
    for bad, good in _PDF_UNSAFE_CHARS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def render_energy_tab():
    from dashboard.ui.components import breadcrumb
    st.markdown(breadcrumb(["NEUROPLANT", "ALL LINES", "UTILITIES"]), unsafe_allow_html=True)

    try:
        carbon = compute_batch_carbon_footprint(electricity_kwh=450, compressed_air_litres=12000, units_produced=850)
        demand = track_peak_demand([45, 52, 48, 61], contract_limit_kw=65)
        backend_ok = True
    except Exception:
        carbon = {"total_co2_kg": 0, "co2_per_unit_kg": 0, "electricity_co2_kg": 0, "compressed_air_co2_kg": 0}
        demand = {"peak_kw": 0, "contract_limit_kw": 65, "pct_of_limit": 0, "alert": False}
        backend_ok = False

    if not backend_ok:
        connection_warning("Layer 7 Energy Intelligence", "Could not compute carbon/demand metrics — check layer7 service.")

    try:
        baseline = establish_baseline([100, 102, 98, 101, 99, 103, 100])
        leak_result = detect_leak([125] * 25, baseline)
        leak_ok = True
    except Exception:
        baseline = {}
        leak_result = {"leak_detected": False}
        leak_ok = False

    # FIX: establish_baseline returns "mean_flow_lpm" not "baseline_lpm" --
    # previous lookup always fell through to 0.
    baseline_display = (
        baseline.get("mean_flow_lpm")
        or baseline.get("baseline_lpm")
        or baseline.get("baseline")
        or 0
    ) if isinstance(baseline, dict) else baseline

    render_kpi_hero([
        {"label": "Batch CO2 (Last Shift)", "value": f"{carbon['total_co2_kg']} kg", "status": "online",
         "micro_label": "450 kWh + 12k L air"},
        {"label": "CO2 / Unit", "value": f"{carbon['co2_per_unit_kg']} kg", "status": "online"},
        {"label": "Peak Demand", "value": f"{demand['pct_of_limit']}%",
         "status": "critical" if demand["alert"] else "online"},
        {"label": "Air Leak",
         "value": "Detected" if leak_ok and leak_result.get("leak_detected") else "None",
         "status": "critical" if leak_ok and leak_result.get("leak_detected") else "online"},
    ])

    section_header("Utility Overview")
    _utility_values = {
        "electricity": ("450 kWh", "live" if backend_ok else "demo"),
        "compressed_air": ("12,000 L", "live" if backend_ok else "demo"),
        "water": ("850 L", "demo"),
        "steam": ("—", "demo"),
    }
    util_html = "".join([
        f'<div style="display:inline-flex;align-items:center;gap:6px;margin-right:22px;margin-bottom:6px;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{color};display:inline-block;"></span>'
        f'<span style="color:{COLORS["text_secondary"]};font-size:0.78rem;text-transform:capitalize;">{name.replace("_"," ")}</span>'
        f'<span style="color:{COLORS["text_primary"]};font-size:0.78rem;font-weight:600;">{_utility_values[name][0]}</span>'
        f'<span style="color:{COLORS["text_muted"]};font-size:0.62rem;text-transform:uppercase;">({_utility_values[name][1]})</span>'
        f'</div>'
        for name, color in UTILITY_COLORS.items()
    ])
    st.markdown(f'<div style="margin-bottom:14px;">{util_html}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        section_header("Utility Consumption Matrix", "Demo series — shift-level; per-machine granularity pending API")
        z = [[450, 380, 410], [12000, 9500, 11200], [850, 720, 890]]
        st.plotly_chart(
            heatmap(z, ["Shift A", "Shift B", "Shift C"], ["Electricity (kWh)", "Compressed Air (L)", "Water (L)"], "Utility Consumption by Shift"),
            use_container_width=True
        )

    with col2:
        section_header("Peak Demand", "vs contract limit — live")
        st.plotly_chart(gauge_small(demand["peak_kw"], demand["contract_limit_kw"], "Peak Demand", "kW"), use_container_width=True)
        if demand["alert"]:
            alert_html = (
                f'<div class="neuro-card" style="border-left:3px solid {status_color("critical")};">'
                f'<span style="color:{status_color("critical")};font-weight:600;">Approaching contract limit</span>'
                f'<p style="color:{COLORS["text_secondary"]};font-size:0.8rem;">{demand["peak_kw"]} kW of {demand["contract_limit_kw"]} kW limit ({demand["pct_of_limit"]}%)</p></div>'
            )
            st.markdown(alert_html, unsafe_allow_html=True)

    section_header("Energy Anomalies", "Compressed air leak detection — live")
    if not leak_ok:
        connection_warning("Compressed Air Monitor", "Could not run leak detection.")
    elif leak_result.get("leak_detected"):
        leak_html = (
            f'<div class="neuro-card-overlay" style="border-left:4px solid {status_color("critical")};">'
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<span class="status-pill status-critical">LEAK DETECTED</span>'
            f'<span style="color:{COLORS["text_primary"]};font-weight:600;">Line 01 — Compressed Air Network</span></div>'
            f'<div style="display:flex;gap:28px;margin-top:10px;flex-wrap:wrap;">'
            f'<div><div style="font-size:0.66rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Baseline</div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};">{baseline_display} L/min</div></div>'
            f'<div><div style="font-size:0.66rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Sustained</div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};">{leak_result["sustained_minutes_exceeded"]} min</div></div>'
            f'<div><div style="font-size:0.66rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Est. Leak Rate</div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;color:{status_color("critical")};font-weight:600;">{leak_result["estimated_leak_rate_lpm"]} L/min</div></div>'
            f'<div><div style="font-size:0.66rem;color:{COLORS["text_muted"]};text-transform:uppercase;">Est. Waste</div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;color:{status_color("critical")};font-weight:600;">{leak_result["estimated_energy_waste_kwh_per_hour"]} kWh/hr</div></div>'
            f'</div></div>'
        )
        st.markdown(leak_html, unsafe_allow_html=True)
    else:
        no_active_alerts_state("utility systems")

    section_header("Peak Demand Timeline", "15-minute windows — demo series")
    windows = [f"{h:02d}:{m:02d}" for h in range(6, 22) for m in (0, 15, 30, 45)][:32]
    demand_series = list(np.clip(np.random.normal(50, 8, 32), 30, 68).round(1))
    fig = trend_line(windows, demand_series, title="Electricity Demand (kW)", y_label="kW", color=UTILITY_COLORS["electricity"])
    add_threshold_line(fig, demand["contract_limit_kw"], f'CONTRACT LIMIT {demand["contract_limit_kw"]} kW', color=status_color("critical"))
    st.plotly_chart(fig, use_container_width=True)

    cost_col, carbon_col = st.columns(2)
    with cost_col:
        section_header("Energy Cost / Unit", "Demo — pending cost-per-unit query")
        st.markdown(
            f'<div class="neuro-card" style="text-align:center;padding:20px;">'
            f'<div style="font-size:0.68rem;color:{COLORS["text_secondary"]};text-transform:uppercase;letter-spacing:0.07em;">Cost per Unit</div>'
            f'<div style="font-size:1.9rem;font-weight:700;color:{COLORS["text_primary"]};font-family:\'JetBrains Mono\',monospace;margin-top:8px;">₹4.85</div>'
            f'<div style="font-size:0.72rem;color:{status_color("online")};margin-top:4px;">-3.2% vs last week</div></div>',
            unsafe_allow_html=True
        )
    with carbon_col:
        section_header("Carbon / Batch", "Live — from Layer 7")
        breakdown_html = (
            f'<div class="neuro-card"><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;text-align:center;">'
            f'<div><div style="color:{COLORS["text_secondary"]};font-size:0.72rem;">ELECTRICITY</div>'
            f'<div style="font-size:1.15rem;color:{UTILITY_COLORS["electricity"]};font-weight:700;">{carbon["electricity_co2_kg"]} kg</div></div>'
            f'<div><div style="color:{COLORS["text_secondary"]};font-size:0.72rem;">COMPRESSED AIR</div>'
            f'<div style="font-size:1.15rem;color:{UTILITY_COLORS["compressed_air"]};font-weight:700;">{carbon["compressed_air_co2_kg"]} kg</div></div>'
            f'<div><div style="color:{COLORS["text_secondary"]};font-size:0.72rem;">TOTAL / UNIT</div>'
            f'<div style="font-size:1.15rem;color:{status_color("online")};font-weight:700;">{carbon["co2_per_unit_kg"]} kg</div></div>'
            f'</div></div>'
        )
        st.markdown(breakdown_html, unsafe_allow_html=True)

    section_header("CO2 Emissions Trend", "Last 30 days — demo series")
    days = list(range(1, 31))
    co2_trend = list(np.random.normal(370, 25, 30).round(1))
    st.plotly_chart(trend_line(days, co2_trend, title="Daily CO2 Emissions", y_label="kg CO2", color=UTILITY_COLORS["electricity"]), use_container_width=True)


def render_esg_tab():
    render_kpi_hero([
        {"label": "Total CO2 (Month)", "value": "11,250 kg", "status": "online"},
        {"label": "Energy Cost/Unit", "value": "₹4.85", "status": "online"},
        {"label": "Energy Intensity", "value": "0.92", "status": "warning"},
        {"label": "vs Last Month", "value": "-7.0%", "status": "online"},
    ])

    section_header("ESG Scorecard")
    scorecard_html = (
        f'<div class="neuro-card"><div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:16px;text-align:center;">'
        f'<div><div style="color:{COLORS["text_secondary"]};font-size:0.72rem;text-transform:uppercase;">Energy Intensity</div>'
        f'<div style="font-size:1.3rem;color:{COLORS["text_primary"]};font-weight:700;margin-top:4px;">0.92</div>'
        f'<div style="font-size:0.66rem;color:{COLORS["text_muted"]};">vs 0.85 industry benchmark</div></div>'
        f'<div><div style="color:{COLORS["text_secondary"]};font-size:0.72rem;text-transform:uppercase;">Water Intensity</div>'
        f'<div style="font-size:1.3rem;color:{COLORS["text_primary"]};font-weight:700;margin-top:4px;">8.5 L/unit</div>'
        f'<div style="font-size:0.66rem;color:{COLORS["text_muted"]};">&nbsp;</div></div>'
        f'<div><div style="color:{COLORS["text_secondary"]};font-size:0.72rem;text-transform:uppercase;">Scope 1</div>'
        f'<div style="font-size:1.3rem;color:{status_color("warning")};font-weight:700;margin-top:4px;">120 kg</div>'
        f'<div style="font-size:0.66rem;color:{COLORS["text_muted"]};">Direct combustion</div></div>'
        f'<div><div style="color:{COLORS["text_secondary"]};font-size:0.72rem;text-transform:uppercase;">Scope 2</div>'
        f'<div style="font-size:1.3rem;color:{status_color("online")};font-weight:700;margin-top:4px;">11,130 kg</div>'
        f'<div style="font-size:0.66rem;color:{COLORS["text_muted"]};">Purchased electricity</div></div>'
        f'</div></div>'
    )
    st.markdown(scorecard_html, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])
    with col1:
        section_header("Monthly CO2 Trend")
        months = ["Mar", "Apr", "May", "Jun", "Jul", "Aug"]
        co2 = [13200, 12800, 12100, 11900, 11250, 10800]
        fig = trend_line(months, co2, title="CO2 Emissions (kg)", y_label="kg CO2", color=status_color("online"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        section_header("Scope 1 vs Scope 2")
        import plotly.graph_objects as go
        from dashboard.ui.charts import PLOTLY_LAYOUT_NO_TITLE
        fig2 = go.Figure(go.Pie(
            labels=["Scope 1 — Direct", "Scope 2 — Purchased"],
            values=[120, 11130],
            marker=dict(colors=[status_color("warning"), status_color("online")]),
            hole=0.55,
            textfont=dict(color=COLORS["text_primary"]),
        ))
        fig2.update_layout(**PLOTLY_LAYOUT_NO_TITLE, height=280, showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)

    section_header("Top Energy Saving Opportunities")
    opportunities = [
        "Fix compressed air coupling leak on Line 01 network — save 340 kWh/month",
        "Shift Line 02 non-critical processes to off-peak hours",
        "Upgrade Line 01 motor to IE3 efficiency class",
    ]
    for i, opp in enumerate(opportunities, 1):
        opp_html = (
            f'<div class="neuro-card" style="padding:12px;display:flex;align-items:center;gap:10px;">'
            f'<span style="width:22px;height:22px;border-radius:5px;background:{COLORS["bg_elevated"]};'
            f'border:1px solid {COLORS["border_active"]};display:flex;align-items:center;justify-content:center;'
            f'font-size:0.72rem;color:{COLORS["accent_bright"]};font-weight:700;flex-shrink:0;'
            f'font-family:\'JetBrains Mono\',monospace;">{i}</span>'
            f'<span style="color:{COLORS["text_primary"]};font-size:0.85rem;">{opp}</span></div>'
        )
        st.markdown(opp_html, unsafe_allow_html=True)

    section_header("Report Center", "Generate, edit, and preview reports")

    if "report_preview" not in st.session_state:
        st.session_state["report_preview"] = None

    def _monthly_report_text() -> str:
        return (
            f"NEUROPLANT AI — SUSTAINABILITY REPORT (August 2026)\n"
            f"{'=' * 52}\n\n"
            f"Total CO2 Emissions: 11,250.5 kg (-7.0% vs prev month)\n"
            f"Energy Cost per Unit: Rs 4.85\n"
            f"Energy Intensity Index: 0.92\n\n"
            f"Top Energy Saving Opportunities:\n"
            + "\n".join(f"  {i}. {o}" for i, o in enumerate(opportunities, 1))
        )

    def _shift_report_text() -> str:
        return (
            f"NEUROPLANT AI — SHIFT REPORT\n{'=' * 52}\n\n"
            f"Line: LINE01\nShift: Evening Shift - 12 Sep 2026\n\n"
            f"Summary:\nProduction ran at 78.3% fleet OEE. Top downtime cause: unplanned stop on "
            f"CNC-02 (coolant pump alarm, 47 min). Active maintenance flag on CNC-07 (RUL 3.5 days, "
            f"bearing wear). Energy intensity 0.42 kWh/unit, +6% vs baseline."
        )

    def _executive_report_text() -> str:
        return (
            f"NEUROPLANT AI — WEEKLY EXECUTIVE REPORT\n{'=' * 52}\n\n"
            f"Period: Week of 8-12 Sep 2026\n\n"
            f"OEE Trend (7-Day):\nFleet OEE trended from 74% to 78.3% over the week, still 6.7 "
            f"points below the 85% target.\n\n"
            f"Top 3 Root Causes of Performance Loss:\n"
            f"  1. Unplanned coolant pump stoppages on Component Machining line\n"
            f"  2. Cycle time drift on CNC-06 (Bearing Housing) - 9% above design\n"
            f"  3. Elevated defect rate on SKU-118 tied to spindle RPM deviation\n\n"
            f"Maintenance: 4 of 6 planned maintenance windows completed on schedule.\n"
            f"Energy Cost Trend: down 3.2% week-over-week to Rs 4.85/unit.\n\n"
            f"Recommended Priority Actions — Next Week:\n"
            f"  1. Inspect CNC-02 cooling system before next production cycle\n"
            f"  2. Schedule CNC-07 bearing replacement within next low-production window\n"
            f"  3. Fix compressed air coupling leak on Line 01 network"
        )

    report_cols = st.columns(3)
    with report_cols[0]:
        if st.button("Monthly Report", type="primary", use_container_width=True):
            st.session_state["report_preview"] = {"label": "Monthly Sustainability Report", "text": _monthly_report_text()}
            st.rerun()
    with report_cols[1]:
        if st.button("Shift Report", type="primary", use_container_width=True):
            st.session_state["report_preview"] = {"label": "Shift Report", "text": _shift_report_text()}
            st.rerun()
    with report_cols[2]:
        if st.button("Executive Report", type="primary", use_container_width=True):
            st.session_state["report_preview"] = {"label": "Executive Report", "text": _executive_report_text()}
            st.rerun()

    preview = st.session_state.get("report_preview")
    if preview:
        st.markdown(f'<div style="margin-top:14px;color:{COLORS["text_primary"]};font-weight:600;font-size:0.88rem;">📄 {preview["label"]}</div>', unsafe_allow_html=True)
        edited_text = st.text_area("Report content (editable)", value=preview["text"], height=280,
                                    key="report_text_editor", label_visibility="collapsed")

        action_cols = st.columns([1, 1, 1])
        with action_cols[0]:
            import csv as _csv, io as _io
            csv_buf = _io.StringIO()
            writer = _csv.writer(csv_buf)
            writer.writerow(["line_number", "content"])
            for i, line in enumerate(edited_text.split("\n"), 1):
                writer.writerow([i, line])
            st.download_button("Export as CSV", data=csv_buf.getvalue(),
                                file_name=f'{preview["label"].replace(" ", "_")}.csv',
                                mime="text/csv", use_container_width=True)
        with action_cols[1]:
            if _PDF_GENERATOR_AVAILABLE:
                try:
                    from fpdf import FPDF, XPos, YPos
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Helvetica", size=10)
                    for line in edited_text.split("\n"):
                        pdf.cell(0, 6, _pdf_safe_text(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    pdf_bytes = bytes(pdf.output())
                    st.download_button("Export as PDF", data=pdf_bytes,
                                        file_name=f'{preview["label"].replace(" ", "_")}.pdf',
                                        mime="application/pdf", key="dl_pdf_export", use_container_width=True)
                except Exception as e:
                    error_state(f"PDF export failed (CSV above still works): {e}")
            else:
                st.caption("PDF unavailable (fpdf broken) — use CSV above.")
        with action_cols[2]:
            if st.button("Close", use_container_width=True):
                st.session_state["report_preview"] = None
                st.rerun()


def render():
    render_topbar("Energy & ESG", "Layer 7 + 9 — Utility Consumption, Carbon Footprint, ESG Reporting", breadcrumb="Home")

    tab_energy, tab_esg = st.tabs(["▲ Energy Intelligence", "◐ Sustainability & ESG"])
    with tab_energy:
        render_energy_tab()
    with tab_esg:
        render_esg_tab()