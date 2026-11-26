"""
Predictive Maintenance page — Layer 4. AI engineering workstation: risk
board, model benchmark, explainability, signal forensics, anomaly analysis,
maintenance priority queue.

REVISION (single-source-of-truth + robust-import pass):
  - Reads per-machine RUL/OEE/status from machine_monitoring.py's shared
    _MACHINE_HEALTH_STATIC. Import tries several module paths and falls
    back to an inline copy so the page always renders.
  - render() guards min() against an empty roster so it can never crash.
"""
import os
import random
import streamlit as st
from dashboard.ui.topbar import render_topbar, render_kpi_hero
from dashboard.ui.theme import COLORS, status_color
from dashboard.ui.components import section_header, info_banner, ai_evidence_card
from dashboard.ui.charts import pareto_bar, machine_risk_bar, rul_prediction_cone

_INLINE_MACHINE_HEALTH_STATIC = {
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
               "status": "warning", "temp": "58.6°C", "vibration": "3.9 mm/s", "rpm": "2,860",
               "current": "11.2 A", "rul": "22.0 DAYS", "oee": "71.4%"},
    "CNC-08": {"line": "Precision Machining", "type": "CNC Machining Center — Clutch Hub",
               "status": "warning", "temp": "56.1°C", "vibration": "3.5 mm/s", "rpm": "2,850",
               "current": "11.5 A", "rul": "15.0 DAYS", "oee": "68.2%"},
    "CNC-09": {"line": "Finishing / Component Processing", "type": "CNC Machining Center — CV Joint Housing",
               "status": "online", "temp": "42.9°C", "vibration": "1.9 mm/s", "rpm": "2,920",
               "current": "10.7 A", "rul": "142.0 DAYS", "oee": "96.0%"},
    "CNC-10": {"line": "Finishing / Component Processing", "type": "CNC Machining Center — Wheel Hub",
               "status": "online", "temp": "43.1°C", "vibration": "2.0 mm/s", "rpm": "2,900",
               "current": "10.4 A", "rul": "138.0 DAYS", "oee": "95.7%"},
    "CNC-11": {"line": "Finishing / Component Processing", "type": "CNC Machining Center — Transmission Casing",
               "status": "online", "temp": "44.6°C", "vibration": "2.4 mm/s", "rpm": "2,860",
               "current": "11.0 A", "rul": "112.0 DAYS", "oee": "93.8%"},
    "CNC-12": {"line": "Finishing / Component Processing", "type": "CNC Machining Center — Axle Shaft",
               "status": "online", "temp": "43.6°C", "vibration": "2.1 mm/s", "rpm": "2,890",
               "current": "10.8 A", "rul": "129.0 DAYS", "oee": "94.9%"},
    "ASM-01": {"line": "Automated Assembly", "type": "Assembly Robot",
               "status": "online", "temp": "38.5°C", "vibration": "1.4 mm/s", "rpm": "—",
               "current": "9.8 A", "rul": "150.0 DAYS", "oee": "96.5%"},
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


_MACHINE_HEALTH_STATIC = _try_import_shared_table() or _INLINE_MACHINE_HEALTH_STATIC


def _rul_days(machine_id: str) -> float:
    raw = str(_MACHINE_HEALTH_STATIC.get(machine_id, {}).get("rul", "")).strip()
    try:
        return float(raw.replace("DAYS", "").replace("DAY", "").strip())
    except (ValueError, TypeError):
        return 999.0


def _status_for(machine_id: str) -> str:
    return _MACHINE_HEALTH_STATIC.get(machine_id, {}).get("status", "online")


def _load_machines_rul() -> list:
    result = []
    for m_id, entry in _MACHINE_HEALTH_STATIC.items():
        rul = _rul_days(m_id)
        rng = random.Random(hash(m_id) % (2**31))
        if rul <= 5:
            conf = round(0.88 + rng.uniform(0, 0.06), 2)
        elif rul <= 15:
            conf = round(0.78 + rng.uniform(0, 0.08), 2)
        elif rul <= 30:
            conf = round(0.68 + rng.uniform(0, 0.08), 2)
        else:
            conf = round(0.55 + rng.uniform(0, 0.15), 2)
        if rul <= 5:
            impact = rng.randint(40, 60)
        elif rul <= 15:
            impact = rng.randint(25, 45)
        elif rul <= 30:
            impact = rng.randint(15, 30)
        else:
            impact = rng.randint(5, 20)
        result.append({"id": m_id, "rul": rul, "confidence": conf,
                       "impact_units": impact, "status": entry.get("status", "online")})
    return result


_DEMO_MACHINES_RUL = _load_machines_rul()
if not _DEMO_MACHINES_RUL:
    _DEMO_MACHINES_RUL = [{"id": "CNC-01", "rul": 100.0, "confidence": 0.65,
                           "impact_units": 10, "status": "online"}]

_DEMO_ANOMALY_BENCHMARK = {
    "Isolation Forest": {"precision": 0.81, "recall": 0.29, "fpr": 0.04},
    "Z-score": {"precision": 0.62, "recall": 0.18, "fpr": 0.11},
}

_SHAP_FEATURE_NAMES = ["s11_mean10", "s4_std10", "s9_lag1", "s7_mean10", "s2_std10",
                       "s12_ewm5", "s3_lag2", "s6_std20", "s8_mean5", "s1_rms"]
_FFT_BANDS = ["BPFO", "BPFI", "BSF", "FTF"]
_FFT_DIAGNOSIS = {
    "BPFO": "Outer race fault",
    "BPFI": "Inner race fault",
    "BSF": "Rolling element fault",
    "FTF": "Cage fault",
}

_MAX_RUL_FOR_SCALE = 150.0


def _machine_shap_profile(machine_id: str) -> tuple:
    rng = random.Random(hash(machine_id) % (2**31))
    rul = _rul_days(machine_id)
    urgency = 1.0 - min(rul / _MAX_RUL_FOR_SCALE, 1.0)
    base = 0.20 + urgency * 0.30
    feats = rng.sample(_SHAP_FEATURE_NAMES, 5)
    vals = sorted([round(base * rng.uniform(0.5, 1.15), 2) for _ in range(5)], reverse=True)
    return feats, vals


def _machine_fft_profile(machine_id: str) -> tuple:
    rng = random.Random((hash(machine_id) * 31) % (2**31))
    rul = _rul_days(machine_id)
    urgency = 1.0 - min(rul / _MAX_RUL_FOR_SCALE, 1.0)
    dominant_idx = rng.choices(range(4), weights=[0.2, 0.4, 0.25, 0.15])[0]
    energies = []
    for i in range(4):
        if i == dominant_idx:
            energies.append(round(0.15 + urgency * 0.35 + rng.uniform(0, 0.08), 3))
        else:
            energies.append(round(rng.uniform(0.005, 0.06), 3))
    return energies, dominant_idx


def _risk_score(rul_days: float) -> float:
    return round(max(0, min(100, (1 - rul_days / _MAX_RUL_FOR_SCALE) * 100)), 1)


def rul_risk_bar(machine_id: str, rul_days: float, confidence: float, max_days: float = _MAX_RUL_FOR_SCALE):
    pct = min((rul_days / max_days) * 100, 100)
    status = "critical" if rul_days < 5 else "warning" if rul_days < 15 else "online"
    color = status_color(status)
    html = (
        f'<div class="neuro-card" style="padding:14px;">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:6px;">'
        f'<span style="font-weight:600;color:{COLORS["text_primary"]};">{machine_id}</span>'
        f'<span style="display:flex;gap:10px;align-items:center;">'
        f'<span style="font-size:0.7rem;color:{COLORS["text_muted"]};">conf {confidence*100:.0f}%</span>'
        f'<span style="font-family:\'JetBrains Mono\',monospace;color:{color};font-weight:600;">{rul_days} days</span></span></div>'
        f'<div style="background:{COLORS["border"]};border-radius:6px;height:8px;overflow:hidden;">'
        f'<div style="background:{color};width:{pct}%;height:100%;"></div></div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render():
    render_topbar("Predictive Maintenance", "Layer 4 — RUL, Anomaly Detection, FFT Fault Analysis", breadcrumb="Home")

    if not _DEMO_MACHINES_RUL:
        info_banner("Predictive Maintenance roster is empty.", tone="warning")
        return

    n_flagged = sum(1 for m in _DEMO_MACHINES_RUL if m["rul"] < 15)
    min_rul_machine = min(_DEMO_MACHINES_RUL, key=lambda m: m["rul"])

    render_kpi_hero([
        {"label": "Machines Monitored", "value": str(len(_DEMO_MACHINES_RUL)), "status": "online"},
        {"label": "Machines Flagged", "value": str(n_flagged), "status": "warning" if n_flagged else "online"},
        {"label": "Min RUL", "value": f"{min_rul_machine['rul']}d", "status": "critical",
         "micro_label": min_rul_machine["id"]},
        {"label": "XGBoost RMSE", "value": "19.9", "status": "online"},
        {"label": "IF Recall", "value": "29.2%", "status": "online"},
    ])

    section_header("Maintenance Risk Board",
                   f"Top 6 most urgent of {len(_DEMO_MACHINES_RUL)} machines — ranked by urgency "
                   f"(RUL source: Machine Monitoring shared state)")
    ranked = sorted(_DEMO_MACHINES_RUL, key=lambda m: m["rul"])
    top6 = ranked[:6]
    rest = ranked[6:]
    rank_cols = st.columns(2)
    for i, m in enumerate(top6):
        with rank_cols[i % 2]:
            rul_risk_bar(m["id"], m["rul"], m["confidence"])

    if rest:
        with st.expander(f"Show remaining {len(rest)} machines"):
            rest_cols = st.columns(2)
            for i, m in enumerate(rest):
                with rest_cols[i % 2]:
                    rul_risk_bar(m["id"], m["rul"], m["confidence"])

    section_header("Machine Risk Score",
                   f"All {len(_DEMO_MACHINES_RUL)} machines — derived from RUL, higher score = greater urgency")
    st.plotly_chart(
        machine_risk_bar([m["id"] for m in _DEMO_MACHINES_RUL],
                          [_risk_score(m["rul"]) for m in _DEMO_MACHINES_RUL]),
        use_container_width=True
    )

    section_header("RUL Health Trajectory", "History vs AI-projected degradation")
    traj_machine = st.selectbox("Machine", [m["id"] for m in _DEMO_MACHINES_RUL], key="rul_traj_machine")
    m = next(x for x in _DEMO_MACHINES_RUL if x["id"] == traj_machine)
    x_hist = list(range(-10, 1))
    y_hist = [max(40, 100 - (10 - i) * 3) for i in range(11)]
    x_fore = list(range(0, max(int(m["rul"]) + 1, 2)))
    y_fore_start = y_hist[-1]
    y_fore = [max(0, y_fore_start - (y_fore_start / max(m["rul"], 1)) * d) for d in x_fore]
    y_upper = [min(100, v + 8) for v in y_fore]
    y_lower = [max(0, v - 8) for v in y_fore]
    st.plotly_chart(
        rul_prediction_cone(x_hist, y_hist, x_fore, y_fore, y_upper, y_lower,
                             title=f"Health Trajectory — {traj_machine}", y_label="Health Index"),
        use_container_width=True
    )

    section_header("Model Benchmark", "XGBoost vs LSTM · TFT excluded (dependency issue)")
    benchmark_rows = (
        f'<tr style="color:{COLORS["text_primary"]};">'
        f'<td style="padding:8px;">XGBoost</td><td>19.88</td><td>14.70</td><td>—</td>'
        f'<td style="color:{status_color("online")};">High (SHAP)</td>'
        f'<td style="color:{status_color("online")};">Primary — recommended</td></tr>'
        f'<tr style="color:{COLORS["text_primary"]};">'
        f'<td style="padding:8px;">LSTM</td><td>24.31</td><td>18.62</td><td>—</td>'
        f'<td style="color:{status_color("warning")};">Low</td>'
        f'<td style="color:{COLORS["text_secondary"]};">Comparison model</td></tr>'
        f'<tr style="color:{COLORS["text_muted"]};">'
        f'<td style="padding:8px;">TFT</td><td colspan="3" style="font-style:italic;">Excluded — pytorch-forecasting lightning_cloud import error</td>'
        f'<td colspan="2" style="color:{COLORS["text_muted"]};">Evaluated, excluded</td></tr>'
    )
    benchmark_html = (
        f'<div class="neuro-card"><table style="width:100%;border-collapse:collapse;font-size:0.85rem;">'
        f'<tr style="color:{COLORS["text_secondary"]};text-align:left;border-bottom:1px solid {COLORS["border"]};">'
        f'<th style="padding:8px;">Model</th><th>RMSE</th><th>MAE</th><th>PI Coverage</th><th>Interpretability</th><th>Business Suitability</th></tr>'
        f'{benchmark_rows}</table></div>'
    )
    st.markdown(benchmark_html, unsafe_allow_html=True)

    section_header("Explainability", "SHAP feature importance")
    shap_machine = st.selectbox("Machine", [m["id"] for m in _DEMO_MACHINES_RUL], key="shap_machine_select")
    col3, col4 = st.columns(2)
    with col3:
        section_header("SHAP Feature Importance")
        features, importances = _machine_shap_profile(shap_machine)
        st.plotly_chart(pareto_bar(features, importances, f"Mean |SHAP value| — {shap_machine}", color=COLORS["accent"]), use_container_width=True)
        st.caption("Positive SHAP values push RUL prediction lower (higher urgency).")

    with col4:
        section_header("Signal Forensics", "FFT bearing fault bands")
        energies, dominant_idx = _machine_fft_profile(shap_machine)
        dominant_band = _FFT_BANDS[dominant_idx]
        st.plotly_chart(pareto_bar(_FFT_BANDS, energies, f"Energy — Faulty Signal — {shap_machine}", highlight_index=dominant_idx), use_container_width=True)
        st.caption(f"Dominant band: **{dominant_band}** → Diagnosis: {_FFT_DIAGNOSIS[dominant_band]}")

    section_header("Anomaly Analysis", "Isolation Forest vs Z-score — AI4I 2020 benchmark")
    anomaly_cols = st.columns(2)
    for col, (method, metrics) in zip(anomaly_cols, _DEMO_ANOMALY_BENCHMARK.items()):
        with col:
            is_primary = method == "Isolation Forest"
            accent = COLORS["accent"]
            st.markdown(
                f'<div class="neuro-card" style="border-top:2px solid {accent};">'
                f'<div style="font-weight:700;color:{COLORS["text_primary"]};margin-bottom:8px;">{method}'
                + (' <span class="status-pill status-online" style="margin-left:6px;">PRIMARY</span>' if is_primary else '')
                + '</div>'
                + "".join([
                    f'<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:0.82rem;">'
                    f'<span style="color:{COLORS["text_secondary"]};">{k.upper()}</span>'
                    f'<span style="font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_primary"]};">{v*100:.1f}%</span></div>'
                    for k, v in metrics.items()
                ])
                + '</div>', unsafe_allow_html=True
            )
    info_banner(
        "Isolation Forest catches multi-sensor fault signatures Z-score misses on "
        "single-variable thresholds — recall weighted over precision due to low "
        "maintenance-dispatch cost relative to missed failures.",
        tone="online"
    )

    section_header("Maintenance Priority Queue", f"All {len(_DEMO_MACHINES_RUL)} machines")
    priority_rows = ""
    for m in ranked:
        priority = 1.0 if m["rul"] < 15 else 0.3
        window = "Next 24h" if m["rul"] < 15 else "Defer"
        if m["rul"] <= 5:
            downtime = "4h"
        elif m["rul"] <= 15:
            downtime = "3h"
        elif m["rul"] <= 30:
            downtime = "2h"
        else:
            downtime = "1h"
        pill_class = "status-critical" if priority >= 1.0 else "status-online"
        row_color = COLORS["text_primary"] if priority >= 1.0 else COLORS["text_secondary"]
        priority_rows += (
            f'<tr style="color:{row_color};">'
            f'<td style="padding:8px;">{m["id"]}</td><td>{m["rul"]}d</td>'
            f'<td><span class="status-pill {pill_class}">{priority}</span></td>'
            f'<td>{window}</td><td>{downtime}</td><td>{m["impact_units"]} units</td></tr>'
        )
    priority_html = (
        f'<div class="neuro-card"><table style="width:100%;border-collapse:collapse;font-size:0.85rem;">'
        f'<tr style="color:{COLORS["text_secondary"]};text-align:left;border-bottom:1px solid {COLORS["border"]};">'
        f'<th style="padding:8px;">Machine</th><th>RUL</th><th>Priority</th><th>Window</th><th>Downtime</th><th>Impact</th></tr>'
        f'{priority_rows}</table></div>'
    )
    st.markdown(priority_html, unsafe_allow_html=True)

    section_header("SHAP Contrastive Fault Explanation")
    contrast_feats, contrast_vals = _machine_shap_profile(shap_machine)
    top_two = list(zip(contrast_feats[:2], contrast_vals[:2]))
    st.markdown(ai_evidence_card(
        f"{shap_machine} — {_FFT_DIAGNOSIS[dominant_band]} Risk Signature",
        confidence=f"{next((m['confidence'] for m in _DEMO_MACHINES_RUL if m['id'] == shap_machine), 0.75)*100:.0f}%",
        contributors=[
            {"label": f"{top_two[0][0]} (deviation driver)", "weight": top_two[0][1]},
            {"label": f"{top_two[1][0]} (secondary driver)", "weight": top_two[1][1] * 0.6},
        ],
        narrative=f"Dominant FFT band {dominant_band} is consistent with a {_FFT_DIAGNOSIS[dominant_band].lower()} pattern."
    ), unsafe_allow_html=True)