"""
Reusable UI components for NeuroPlant AI — header, sidebar status, KPI
cards, alerts, section headers, page headers, and state panels. All HTML
built single-line (no leading indentation before tags) — Streamlit's
markdown parser treats 4+ space indents as code blocks, which breaks
unsafe_allow_html rendering.

REVISION (bug-fix pass — see chat for full list):
  1. kpi_row() rewritten: card at index 0 is now ALWAYS the large hero card
     (kpi_card_hero — bigger, own sparkline slot) and ALL remaining cards
     use the SAME kpi_card_status size (previously home.py bypassed kpi_row
     entirely and hand-mixed kpi_card_trend (150px) with kpi_card_lg (118px),
     which is why cards looked uneven in the Command Center screenshot).
  4. kpi_card_status and kpi_card_lg now both carry: colored top border,
     resting box-shadow (from theme.SHADOWS), and a hover lift + glow —
     previously ONLY kpi_card_lg had a top border and NEITHER had a shadow
     beyond the generic .neuro-card default (which itself had no shadow
     before the theme.py fix). matrix_cell and machine_card also got the
     same shadow treatment so machine cards feel consistent with KPI cards.
"""
import streamlit as st
from datetime import datetime
from dashboard.ui.theme import COLORS, SHADOWS, status_dot, status_color, status_icon


def render_header(page_title: str, page_subtitle: str = ""):
    """Legacy header — kept for backward compatibility."""
    now = datetime.now().strftime("%d %b %Y · %H:%M:%S")
    sub = f' — {page_subtitle}' if page_subtitle else ""
    html = (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:16px 0;border-bottom:1px solid {COLORS["border"]};margin-bottom:24px;">'
        f'<div><div style="display:flex;align-items:center;gap:10px;">'
        f'<span style="font-size:1.3rem;font-weight:700;color:{COLORS["text_primary"]};'
        f'letter-spacing:0.02em;">NEUROPLANT AI</span>'
        f'<span style="background:rgba(79,175,138,0.10);color:{COLORS["success"]};'
        f'padding:2px 9px;border:1px solid rgba(79,175,138,0.22);border-radius:4px;font-size:0.68rem;'
        f'font-family:\'JetBrains Mono\',monospace;letter-spacing:0.05em;">● LIVE</span></div>'
        f'<div style="color:{COLORS["text_secondary"]};font-size:0.85rem;margin-top:4px;">{page_title}{sub}</div>'
        f'</div>'
        f'<div style="text-align:right;font-family:\'JetBrains Mono\',monospace;'
        f'color:{COLORS["text_secondary"]};font-size:0.8rem;">{now}</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, description: str = ""):
    desc_html = f'<div style="color:{COLORS["text_secondary"]};font-size:0.85rem;margin-top:4px;">{description}</div>' if description else ""
    html = (
        f'<div style="margin:4px 0 18px 0;">'
        f'<div style="color:{COLORS["accent_bright"]};font-size:0.66rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.11em;margin-bottom:4px;">{eyebrow}</div>'
        f'<div style="font-size:1.25rem;font-weight:700;color:{COLORS["text_primary"]};">{title}</div>'
        f'{desc_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_system_status_sidebar():
    rows = [
        ("MQTT Broker", "online", "ONLINE"),
        ("OPC-UA", "online", "ONLINE"),
        ("InfluxDB", "online", "ONLINE"),
        ("PostgreSQL", "online", "ONLINE"),
        ("MLflow", "online", "TRACKING"),
        ("GenAI", "online", "ACTIVE"),
    ]
    rows_html = ""
    for label, status, badge in rows:
        color = status_color(status)
        rows_html += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:0.78rem;">'
            f'<span style="color:{COLORS["text_secondary"]};">{label}</span>'
            f'<span>{status_dot(status)}<span style="color:{color};font-size:0.68rem;'
            f'font-family:\'JetBrains Mono\',monospace;">{badge}</span></span></div>'
        )
    html = (
        f'<div style="background:{COLORS["bg_surface"]};border:1px solid {COLORS["border"]};'
        f'border-radius:8px;padding:14px;margin:14px 4px 8px 4px;box-shadow:{SHADOWS["card_rest"]};">'
        f'<div style="font-size:0.62rem;color:{COLORS["text_muted"]};text-transform:uppercase;'
        f'letter-spacing:0.09em;margin-bottom:10px;">System Status</div>{rows_html}</div>'
    )
    st.sidebar.markdown(html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# KPI CARD SYSTEM — rewritten
# ═══════════════════════════════════════════════════════════════════
#
# Hierarchy rule: a page's top metric row should NOT look like six identical
# boxes. kpi_row() below implements: ONE hero card (bigger, richer — the
# single most important number on the page) + N equal-sized status cards
# (same height/width as each other, colored top border + status glyph).
#
# All pages should call render_kpi_hero()/kpi_row() for their main metric
# row instead of hand-mixing kpi_card_lg/kpi_card_trend/kpi_card_status
# directly — that hand-mixing is exactly what caused the uneven-card bug.

_KPI_CARD_HEIGHT = 148  # HARD fixed height (not min-height) so every card in a
# row is pixel-identical regardless of internal content (sparkline present
# or absent, micro_label present or absent, etc). This is what min-height
# could not guarantee -- flex children still shrink-to-content unless the
# container itself has a fixed height.


def kpi_pill_bar(kpis: list[dict]):
    """Compact, equal-weight KPI strip — use for SECONDARY KPI rows only."""
    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        color = status_color(kpi.get("status", "online"))
        html = (
            f'<div style="background:{COLORS["bg_surface"]};border:1px solid {COLORS["border"]};'
            f'border-radius:8px;padding:12px;text-align:center;box-shadow:{SHADOWS["card_rest"]};">'
            f'<div style="font-size:0.64rem;color:{COLORS["text_secondary"]};text-transform:uppercase;'
            f'letter-spacing:0.07em;">{kpi["label"]}</div>'
            f'<div style="font-size:1.4rem;font-weight:700;color:{COLORS["text_primary"]};'
            f'font-family:\'JetBrains Mono\',monospace;margin-top:4px;'
            f'border-top:2px solid {color};padding-top:6px;display:inline-block;">{kpi["value"]}</div></div>'
        )
        with col:
            st.markdown(html, unsafe_allow_html=True)


def kpi_row(kpis: list[dict]):
    """Tiered KPI row — the standard entry point pages should use for their
    top metric strip. Card 0 = hero (2x visual weight, own column span).
    Cards 1..n = uniform status cards. Uses a [2,1,1,1,1] column ratio so
    the hero card is literally wider, not just taller, without breaking the
    row's shared height.

    kpi dict keys: label, value, unit (optional), status (optional),
    micro_label (optional), delta (optional), delta_positive (optional),
    target (optional), sparkline (optional list[float]).
    """
    if not kpis:
        return
    n = len(kpis)
    # Hero gets 2x column width; remaining cards split the rest evenly.
    ratios = [2] + [1] * (n - 1) if n > 1 else [1]
    cols = st.columns(ratios)
    for i, (col, kpi) in enumerate(zip(cols, kpis)):
        with col:
            if i == 0:
                st.markdown(kpi_card_hero(
                    kpi["label"], kpi["value"], kpi.get("unit", ""),
                    delta=kpi.get("delta", ""), delta_positive=kpi.get("delta_positive", True),
                    target=kpi.get("target", ""), status=kpi.get("status", "online"),
                    micro_label=kpi.get("micro_label", ""), sparkline=kpi.get("sparkline")
                ), unsafe_allow_html=True)
            else:
                st.markdown(kpi_card_status(
                    kpi["label"], kpi["value"], kpi.get("unit", ""),
                    status=kpi.get("status", "online"), micro_label=kpi.get("micro_label", "")
                ), unsafe_allow_html=True)


def kpi_card_hero(label: str, value: str, unit: str = "", delta: str = "", delta_positive: bool = True,
                   target: str = "", status: str = "online", micro_label: str = "",
                   sparkline: list = None) -> str:
    """Position-0 hero KPI card — larger type, optional sparkline, colored
    top border + glow shadow. This is THE single most important number on
    the page (e.g. Plant Health, Fleet OEE)."""
    color = status_color(status)
    icon = status_icon(status)
    delta_color = COLORS["success"] if delta_positive else COLORS["danger"]
    delta_arrow = "↑" if delta_positive else "↓"
    delta_html = (
        f'<span style="color:{delta_color};font-size:0.78rem;font-family:\'JetBrains Mono\',monospace;">'
        f'{delta_arrow} {delta}</span>' if delta else ""
    )
    target_html = (
        f'<span style="font-size:0.7rem;color:{COLORS["text_muted"]};margin-left:10px;">'
        f'TARGET <span style="color:{COLORS["text_secondary"]};font-family:\'JetBrains Mono\',monospace;">{target}</span></span>'
        if target else ""
    )
    micro_html = f'<div style="font-size:0.72rem;color:{COLORS["text_muted"]};margin-top:6px;">{micro_label}</div>' if micro_label else ""
    spark_html = _sparkline_svg(sparkline, color, width=120, height=34) if sparkline else ""
    return (
        f'<div class="neuro-card kpi-hero" style="border-top:3px solid {color};padding:18px 22px;margin-bottom:0;'
        f'height:{_KPI_CARD_HEIGHT}px;box-sizing:border-box;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between;'
        f'box-shadow:{SHADOWS["card_glow_teal"]};">'
        f'<div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between;">'
        f'<span style="font-size:0.68rem;color:{COLORS["text_secondary"]};text-transform:uppercase;letter-spacing:0.09em;font-weight:600;">{label}</span>'
        f'<span class="status-pill status-{status}">{icon} {status.upper()}</span></div>'
        f'<div style="display:flex;align-items:baseline;gap:6px;margin-top:10px;">'
        f'<span style="font-size:2.15rem;font-weight:750;color:{COLORS["text_primary"]};'
        f'font-family:\'JetBrains Mono\',monospace;line-height:1;">{value}</span>'
        f'<span style="font-size:0.82rem;color:{COLORS["text_muted"]};">{unit}</span></div>'
        f'<div style="margin-top:4px;">{delta_html}{target_html}</div>{micro_html}</div>'
        f'<div style="display:flex;justify-content:flex-end;margin-top:8px;">{spark_html}</div></div>'
    )


def kpi_card_status(label: str, value: str, unit: str = "", status: str = "online", micro_label: str = "") -> str:
    """Uniform secondary KPI card — same fixed height as its siblings so a
    row of these never looks jagged. Carries a colored top border + status
    glyph + resting shadow that lifts on hover (via .neuro-card CSS)."""
    color = status_color(status)
    icon = status_icon(status)
    micro_html = f'<div style="font-size:0.68rem;color:{COLORS["text_muted"]};margin-top:6px;min-height:14px;">{micro_label}</div>' if micro_label else '<div style="min-height:14px;"></div>'
    return (
        f'<div class="neuro-card" style="border-top:3px solid {color};padding:16px 18px;margin-bottom:0;'
        f'height:{_KPI_CARD_HEIGHT}px;box-sizing:border-box;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div>'
        f'<div style="font-size:0.64rem;color:{COLORS["text_secondary"]};text-transform:uppercase;'
        f'letter-spacing:0.07em;min-height:14px;">{label}</div>'
        f'<div style="display:flex;align-items:baseline;gap:4px;margin-top:8px;">'
        f'<span style="font-size:1.55rem;font-weight:700;color:{COLORS["text_primary"]};font-family:\'JetBrains Mono\',monospace;">{value}</span>'
        f'<span style="font-size:0.72rem;color:{COLORS["text_muted"]};">{unit}</span></div>'
        f'{micro_html}</div>'
        f'<div style="padding-top:8px;font-size:0.7rem;color:{color};display:flex;align-items:center;gap:4px;">'
        f'<span>{icon}</span><span style="text-transform:capitalize;">{status}</span></div></div>'
    )


def kpi_card_lg(label: str, value: str, unit: str = "", delta: str = "", status: str = "online", micro_label: str = ""):
    """Kept for backward compatibility with pages that call it directly —
    now visually identical to kpi_card_status (top border + shadow +
    fixed height) so mixing the two no longer produces uneven cards."""
    color = status_color(status)
    delta_html = f'<div style="font-size:0.72rem;color:{color};margin-top:2px;min-height:16px;">{delta}</div>' if delta else '<div style="min-height:16px;"></div>'
    micro_html = f'<div style="font-size:0.68rem;color:{COLORS["text_muted"]};margin-top:6px;min-height:14px;">{micro_label}</div>' if micro_label else '<div style="min-height:14px;"></div>'
    html = (
        f'<div class="neuro-card" style="border-top:3px solid {color};padding:16px 18px;margin-bottom:0;'
        f'height:{_KPI_CARD_HEIGHT}px;box-sizing:border-box;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-start;">'
        f'<div style="font-size:0.64rem;color:{COLORS["text_secondary"]};text-transform:uppercase;'
        f'letter-spacing:0.08em;min-height:14px;">{label}</div>'
        f'<div style="display:flex;align-items:baseline;gap:4px;margin-top:8px;">'
        f'<span style="font-size:1.55rem;font-weight:700;color:{COLORS["text_primary"]};'
        f'font-family:\'JetBrains Mono\',monospace;">{value}</span>'
        f'<span style="font-size:0.72rem;color:{COLORS["text_muted"]};">{unit}</span></div>'
        f'{delta_html}{micro_html}</div>'
    )
    return html


def kpi_card_trend(label: str, value: str, unit: str = "", delta: str = "", delta_positive: bool = True,
                    target: str = "", status: str = "online", sparkline: list = None) -> str:
    """Full signature KPI card with sparkline — kept for pages that want a
    trend-only card outside the hero/status pair. Now uses the same shared
    min-height token + top border + shadow as the rest of the system."""
    color = status_color(status)
    icon = status_icon(status)
    delta_color = COLORS["success"] if delta_positive else COLORS["danger"]
    delta_arrow = "↑" if delta_positive else "↓"
    delta_html = (
        f'<span style="color:{delta_color};font-size:0.74rem;font-family:\'JetBrains Mono\',monospace;">'
        f'{delta_arrow} {delta}</span>' if delta else ""
    )
    target_html = (
        f'<div style="font-size:0.66rem;color:{COLORS["text_muted"]};margin-top:2px;">'
        f'TARGET <span style="color:{COLORS["text_secondary"]};font-family:\'JetBrains Mono\',monospace;">{target}</span></div>'
        if target else ""
    )
    spark_html = _sparkline_svg(sparkline, color) if sparkline else ""
    return (
        f'<div class="neuro-card" style="border-top:3px solid {color};padding:16px 18px;margin-bottom:0;'
        f'height:{_KPI_CARD_HEIGHT}px;box-sizing:border-box;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div>'
        f'<div style="font-size:0.64rem;color:{COLORS["text_secondary"]};text-transform:uppercase;'
        f'letter-spacing:0.08em;">{label}</div>'
        f'<div style="display:flex;align-items:baseline;gap:5px;margin-top:8px;">'
        f'<span style="font-size:1.55rem;font-weight:750;color:{COLORS["text_primary"]};'
        f'font-family:\'JetBrains Mono\',monospace;">{value}</span>'
        f'<span style="font-size:0.76rem;color:{COLORS["text_muted"]};">{unit}</span></div>'
        f'<div style="margin-top:3px;">{delta_html}</div>'
        f'{target_html}</div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-end;margin-top:8px;">'
        f'<span style="color:{color};font-size:0.7rem;display:flex;align-items:center;gap:4px;">'
        f'<span>{icon}</span><span style="text-transform:uppercase;letter-spacing:0.04em;">{status}</span></span>'
        f'{spark_html}</div></div>'
    )


def status_card(title: str, value: str, subtitle: str = "", status: str = "online", icon: str = "●"):
    color = status_color(status)
    html = (
        f'<div style="background:{COLORS["bg_surface"]};border:1px solid {COLORS["border"]};'
        f'border-top:3px solid {color};border-radius:10px;padding:16px 18px;box-shadow:{SHADOWS["card_rest"]};">'
        f'<div style="font-size:0.66rem;color:{COLORS["text_secondary"]};text-transform:uppercase;'
        f'letter-spacing:0.08em;">{title}</div>'
        f'<div style="font-size:1.7rem;font-weight:700;color:{COLORS["text_primary"]};'
        f'font-family:\'JetBrains Mono\',monospace;margin:8px 0 4px 0;">{value}</div>'
        f'<div style="font-size:0.76rem;color:{color};">{icon} {subtitle}</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def alert_card(severity: str, source: str, description: str, timestamp: str = "",
                recommendation: str = "", impact: str = "", location: str = ""):
    """Alert card — always pairs color with an icon + text label (accessibility
    rule), never communicates severity through color alone."""
    color = status_color(severity)
    icon = status_icon(severity)
    badge_label = severity.upper()
    source_label = f'{source} <span style="color:{COLORS["text_muted"]};font-weight:400;">· {location}</span>' if location else source
    impact_html = ""
    if impact:
        impact_html = (
            f'<div style="margin-top:6px;font-size:0.78rem;color:{COLORS["text_secondary"]};">'
            f'<span style="color:{COLORS["text_muted"]};text-transform:uppercase;font-size:0.64rem;'
            f'letter-spacing:0.06em;">Impact</span> {impact}</div>'
        )
    rec_html = ""
    if recommendation:
        rec_html = (
            f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid {COLORS["border_muted"]};'
            f'font-size:0.78rem;color:{COLORS["text_secondary"]};">'
            f'<span style="color:{COLORS["text_muted"]};text-transform:uppercase;font-size:0.64rem;'
            f'letter-spacing:0.06em;">Recommended</span><br>{recommendation}</div>'
        )
    html = (
        f'<div style="background:{COLORS["bg_surface"]};border:1px solid {COLORS["border"]};'
        f'border-left:3px solid {color};border-radius:8px;padding:12px 16px;margin-bottom:10px;'
        f'box-shadow:{SHADOWS["card_rest"]};transition:transform 180ms ease,box-shadow 180ms ease;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="color:{color};font-size:0.68rem;font-weight:700;letter-spacing:0.06em;'
        f'font-family:\'JetBrains Mono\',monospace;display:flex;align-items:center;gap:5px;">'
        f'<span>{icon}</span>{badge_label}</span>'
        f'<span style="color:{COLORS["text_muted"]};font-size:0.7rem;'
        f'font-family:\'JetBrains Mono\',monospace;">{timestamp}</span></div>'
        f'<div style="color:{COLORS["text_primary"]};font-size:0.82rem;font-weight:600;margin-top:6px;">{source_label}</div>'
        f'<div style="color:{COLORS["text_secondary"]};font-size:0.8rem;margin-top:2px;">{description}</div>'
        f'{impact_html}{rec_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    sub_html = f'<span style="color:{COLORS["text_muted"]};font-size:0.78rem;margin-left:10px;">{subtitle}</span>' if subtitle else ""
    html = (
        f'<div style="display:flex;align-items:center;gap:9px;margin:22px 0 12px 0;">'
        f'<span style="width:3px;height:16px;background:{COLORS["accent"]};border-radius:2px;display:inline-block;"></span>'
        f'<span style="color:{COLORS["text_primary"]};font-size:0.92rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.07em;">{title}</span>{sub_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def info_banner(text: str, tone: str = "maintenance"):
    color = status_color(tone)
    icon = status_icon(tone)
    html = (
        f'<div style="background:{COLORS["bg_surface"]};border:1px solid {COLORS["border"]};'
        f'border-left:3px solid {color};border-radius:6px;padding:10px 14px;margin:8px 0;'
        f'font-size:0.82rem;color:{COLORS["text_secondary"]};display:flex;align-items:flex-start;gap:8px;'
        f'box-shadow:{SHADOWS["card_rest"]};">'
        f'<span style="color:{color};margin-top:1px;">{icon}</span><span>{text}</span></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def empty_state(message: str, hint: str = ""):
    hint_html = f'<div style="color:{COLORS["text_muted"]};font-size:0.76rem;margin-top:6px;">{hint}</div>' if hint else ""
    html = (
        f'<div style="background:{COLORS["bg_surface"]};border:1px dashed {COLORS["border"]};'
        f'border-radius:8px;padding:28px 20px;text-align:center;">'
        f'<div style="color:{COLORS["text_secondary"]};font-size:0.86rem;">{message}</div>{hint_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def no_active_alerts_state(scope: str = "monitored systems"):
    html = (
        f'<div class="neuro-card" style="border-left:3px solid {COLORS["success"]};display:flex;align-items:center;gap:10px;">'
        f'<span class="status-pill status-online">● NO ACTIVE ALERTS</span>'
        f'<span style="color:{COLORS["text_secondary"]};font-size:0.84rem;">All {scope} currently within configured thresholds.</span></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def data_source_offline_state(source_name: str):
    html = (
        f'<div class="neuro-card" style="border-left:3px solid {COLORS["offline"]};text-align:center;padding:26px 20px;">'
        f'<span class="status-pill status-offline">○ DATA SOURCE OFFLINE</span>'
        f'<div style="color:{COLORS["text_secondary"]};font-size:0.84rem;margin-top:10px;">'
        f'Waiting for {source_name} telemetry stream...</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def model_unavailable_state(model_name: str = "Prediction"):
    html = (
        f'<div class="neuro-card" style="border-left:3px solid {COLORS["maintenance"]};text-align:center;padding:26px 20px;">'
        f'<span class="status-pill status-maintenance">◆ MODEL UNAVAILABLE</span>'
        f'<div style="color:{COLORS["text_secondary"]};font-size:0.84rem;margin-top:10px;">'
        f'{model_name} service is currently unavailable.</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def connection_warning(service: str, detail: str = ""):
    detail_html = f'<div style="color:{COLORS["text_secondary"]};font-size:0.78rem;margin-top:4px;">{detail}</div>' if detail else ""
    html = (
        f'<div style="background:{COLORS["bg_surface"]};border:1px solid {COLORS["border"]};'
        f'border-left:3px solid {COLORS["warning"]};border-radius:6px;padding:12px 16px;margin:10px 0;'
        f'box-shadow:{SHADOWS["card_rest"]};">'
        f'<div style="color:{COLORS["warning"]};font-size:0.78rem;font-weight:700;letter-spacing:0.03em;">'
        f'▲ {service} — connection unavailable</div>{detail_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def error_state(message: str):
    html = (
        f'<div style="background:{COLORS["bg_surface"]};border:1px solid {COLORS["border"]};'
        f'border-left:3px solid {COLORS["danger"]};border-radius:6px;padding:12px 16px;margin:10px 0;'
        f'box-shadow:{SHADOWS["card_rest"]};">'
        f'<div style="color:{COLORS["danger"]};font-size:0.82rem;font-weight:600;">■ {message}</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def skeleton_block(height_px: int = 60):
    st.markdown(f'<div class="skeleton-loading" style="height:{height_px}px;"></div>', unsafe_allow_html=True)


def matrix_cell(machine_id: str, status: str, is_selected: bool = False) -> str:
    color = status_color(status)
    icon = status_icon(status)
    border = f'1px solid {color}' if is_selected else f'1px solid {COLORS["border"]}'
    bg = COLORS["bg_elevated"] if is_selected else COLORS["bg_surface"]
    shadow = SHADOWS["card_glow_teal"] if is_selected else SHADOWS["card_rest"]
    return (
        f'<div style="background:{bg};border:{border};border-top:2px solid {color};border-radius:8px;padding:10px 8px;'
        f'text-align:center;min-height:56px;display:flex;flex-direction:column;justify-content:center;gap:4px;'
        f'box-shadow:{shadow};transition:transform 180ms ease,box-shadow 180ms ease;">'
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:0.76rem;color:{COLORS["text_primary"]};'
        f'font-weight:600;">{machine_id}</div>'
        f'<div style="display:flex;align-items:center;justify-content:center;gap:4px;">'
        f'<span style="color:{color};font-size:0.6rem;">{icon}</span>'
        f'<span style="font-size:0.6rem;color:{COLORS["text_muted"]};text-transform:uppercase;'
        f'letter-spacing:0.03em;">{status}</span></div></div>'
    )


def freshness_badge(is_live: bool, last_sync_label: str = None) -> str:
    if is_live:
        label = last_sync_label or "just now"
        return (
            f'<span class="status-pill status-online">● LIVE</span>'
            f'<span style="color:{COLORS["text_muted"]};font-size:0.72rem;margin-left:6px;">Updated {label}</span>'
        )
    return (
        f'<span class="status-pill status-offline">○ LAST-KNOWN</span>'
        f'<span style="color:{COLORS["text_muted"]};font-size:0.72rem;margin-left:6px;">'
        f'{last_sync_label or "Live sync unavailable"}</span>'
    )


def _sparkline_svg(values: list, color: str, width: int = 84, height: int = 28) -> str:
    """Tiny inline SVG sparkline — no JS chart lib needed for a KPI card
    micro-trend. Renders a filled area + line from a short list of numbers."""
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    n = len(values)
    step = width / (n - 1)
    pts = [(i * step, height - ((v - lo) / span) * (height - 4) - 2) for i, v in enumerate(values)]
    line_path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_path = line_path + f" L{width},{height} L0,{height} Z"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="display:block;">'
        f'<path d="{area_path}" fill="{color}" opacity="0.12"></path>'
        f'<path d="{line_path}" fill="none" stroke="{color}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round"></path></svg>'
    )


def machine_card(machine_id: str, machine_type: str, status: str, temp: str = "", vibration: str = "",
                  rpm: str = "", current: str = "", rul: str = "", oee: str = "", last_update: str = "") -> str:
    """Elite-spec machine telemetry card (§'MACHINE CARD'). Machine body stays
    neutral — only the status label carries color, never the whole card."""
    color = status_color(status)
    icon = status_icon(status)
    rows = []
    for lbl, val in [("TEMP", temp), ("VIBRATION", vibration), ("RPM", rpm), ("CURRENT", current)]:
        if val:
            rows.append(
                f'<div style="display:flex;justify-content:space-between;font-size:0.78rem;padding:3px 0;">'
                f'<span style="color:{COLORS["text_muted"]};">{lbl}</span>'
                f'<span style="color:{COLORS["text_primary"]};font-family:\'JetBrains Mono\',monospace;">{val}</span></div>'
            )
    rows_html = "".join(rows)
    footer_html = ""
    if rul or oee:
        parts = []
        if rul:
            parts.append(f'<div><div style="font-size:0.6rem;color:{COLORS["text_muted"]};text-transform:uppercase;">RUL</div>'
                          f'<div style="font-size:0.9rem;color:{COLORS["text_primary"]};font-family:\'JetBrains Mono\',monospace;">{rul}</div></div>')
        if oee:
            parts.append(f'<div><div style="font-size:0.6rem;color:{COLORS["text_muted"]};text-transform:uppercase;">OEE</div>'
                          f'<div style="font-size:0.9rem;color:{COLORS["text_primary"]};font-family:\'JetBrains Mono\',monospace;">{oee}</div></div>')
        footer_html = (f'<div style="display:flex;gap:20px;margin-top:8px;padding-top:8px;'
                        f'border-top:1px solid {COLORS["border_muted"]};">' + "".join(parts) + '</div>')
    update_html = (f'<div style="font-size:0.64rem;color:{COLORS["text_muted"]};margin-top:8px;">'
                    f'LAST UPDATE <span style="font-family:\'JetBrains Mono\',monospace;">{last_update}</span></div>'
                    if last_update else "")
    return (
        f'<div class="neuro-card" style="padding:14px 16px;margin-bottom:0;border-left:3px solid {color};">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
        f'<div><div style="font-size:0.92rem;font-weight:700;color:{COLORS["text_primary"]};'
        f'font-family:\'JetBrains Mono\',monospace;">{machine_id}</div>'
        f'<div style="font-size:0.68rem;color:{COLORS["text_muted"]};text-transform:uppercase;'
        f'letter-spacing:0.04em;">{machine_type}</div></div>'
        f'<span class="status-pill status-{status}">{icon} {status.upper()}</span></div>'
        f'<div style="margin-top:10px;">{rows_html}</div>{footer_html}{update_html}</div>'
    )


def ai_evidence_card(title: str, confidence: str = "", contributors: list = None, narrative: str = "") -> str:
    """SHAP / AI-explanation panel per Elite spec §'AI EVIDENCE PANEL' and
    §'SHAP EXPLAINABILITY'. contributors: list of {"label": str, "weight": float
    in [-1,1]} rendered as small horizontal bars — positive weights use the
    AI accent color, negative (normalizing) factors are muted."""
    conf_html = (
        f'<span style="color:{COLORS["accent_violet"]};font-size:0.72rem;font-family:\'JetBrains Mono\',monospace;">'
        f'CONFIDENCE {confidence}</span>' if confidence else ""
    )
    bars_html = ""
    if contributors:
        max_abs = max(abs(c["weight"]) for c in contributors) or 1
        for c in contributors:
            w = c["weight"]
            pct = min(abs(w) / max_abs * 100, 100)
            bar_color = COLORS["accent_violet"] if w >= 0 else COLORS["text_muted"]
            sign = "+" if w >= 0 else ""
            bars_html += (
                f'<div style="margin:6px 0;">'
                f'<div style="display:flex;justify-content:space-between;font-size:0.76rem;margin-bottom:3px;">'
                f'<span style="color:{COLORS["text_secondary"]};">{c["label"]}</span>'
                f'<span style="color:{bar_color};font-family:\'JetBrains Mono\',monospace;">{sign}{w:.2f}</span></div>'
                f'<div style="background:{COLORS["bg_input"]};border-radius:3px;height:5px;overflow:hidden;">'
                f'<div style="background:{bar_color};height:100%;width:{pct:.0f}%;border-radius:3px;"></div></div></div>'
            )
    narrative_html = (
        f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid {COLORS["border_muted"]};'
        f'font-size:0.8rem;color:{COLORS["text_secondary"]};line-height:1.5;">{narrative}</div>' if narrative else ""
    )
    return (
        f'<div class="neuro-card-elevated">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="color:{COLORS["text_primary"]};font-size:0.86rem;font-weight:700;">{title}</span>{conf_html}</div>'
        f'<div style="margin-top:10px;">{bars_html}</div>{narrative_html}</div>'
    )


def impact_panel(items: list, title: str = "EXPECTED IMPACT") -> str:
    rows_html = ""
    for it in items:
        color = COLORS["success"] if it.get("positive", True) else COLORS["danger"]
        rows_html += (
            f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
            f'border-bottom:1px solid {COLORS["border_muted"]};font-size:0.82rem;">'
            f'<span style="color:{COLORS["text_secondary"]};">{it["label"]}</span>'
            f'<span style="color:{color};font-family:\'JetBrains Mono\',monospace;font-weight:600;">{it["value"]}</span></div>'
        )
    return (
        f'<div class="neuro-card-overlay">'
        f'<div style="font-size:0.68rem;color:{COLORS["accent_bright"]};text-transform:uppercase;'
        f'letter-spacing:0.09em;margin-bottom:8px;">{title}</div>{rows_html}</div>'
    )


def breadcrumb(path: list) -> str:
    sep = f'<span style="color:{COLORS["text_muted"]};margin:0 6px;">/</span>'
    crumbs = sep.join(
        f'<span style="color:{COLORS["text_primary"] if i == len(path)-1 else COLORS["text_muted"]};'
        f'font-family:\'JetBrains Mono\',monospace;font-size:0.76rem;">{p}</span>'
        for i, p in enumerate(path)
    )
    return f'<div style="margin-bottom:10px;">{crumbs}</div>'


def evidence_trail(steps: list) -> str:
    chain = f'<span style="color:{COLORS["text_muted"]};margin:0 8px;">→</span>'.join(
        f'<span style="color:{COLORS["accent_bright"]};font-size:0.72rem;font-family:\'JetBrains Mono\',monospace;'
        f'text-transform:uppercase;letter-spacing:0.03em;">{s}</span>' for s in steps
    )
    return (
        f'<div style="background:{COLORS["bg_input"]};border:1px solid {COLORS["border"]};border-radius:6px;'
        f'padding:10px 14px;margin:10px 0;display:flex;flex-wrap:wrap;align-items:center;gap:2px;">{chain}</div>'
    )


def context_filter_bar(labels: list, live: bool = True):
    chips = "".join(
        f'<span style="background:{COLORS["bg_input"]};border:1px solid {COLORS["border"]};border-radius:5px;'
        f'padding:4px 10px;font-size:0.74rem;color:{COLORS["text_secondary"]};margin-right:6px;'
        f'font-family:\'JetBrains Mono\',monospace;">{lbl} ▾</span>' for lbl in labels
    )
    live_chip = (
        f'<span class="status-pill status-online" style="margin-left:2px;"><span class="pulse-live"></span> LIVE</span>'
        if live else
        f'<span class="status-pill status-offline">○ STATIC</span>'
    )
    st.markdown(f'<div style="display:flex;align-items:center;flex-wrap:wrap;margin-bottom:14px;">{chips}{live_chip}</div>',
                unsafe_allow_html=True)