import streamlit as st
from datetime import datetime
from dashboard.ui.theme import COLORS
from dashboard.ui.components import kpi_pill_bar, kpi_row

PAGE_META = {
    "home": ("COMMAND", "Command Center", "Unified plant overview across all monitored lines and factories"),
    "machine_monitoring": ("MONITOR", "Machine Monitoring", "Real-time machine condition, telemetry and alarm intelligence"),
    "digital_twin": ("MONITOR", "Digital Twin", "Live factory state mirror with production and schedule simulation"),
    "oee_analytics": ("INTELLIGENCE", "OEE Analytics", "Availability, Performance and Quality - live and historical rollups"),
    "predictive_maintenance": ("INTELLIGENCE", "Predictive Maintenance", "RUL prediction, bearing fault detection and maintenance scheduling"),
    "production_optimizer": ("INTELLIGENCE", "Production Optimizer", "Bottleneck detection, line balancing and shift scheduling"),
    "quality_intelligence": ("INTELLIGENCE", "Quality Intelligence", "Fault classification, defect Pareto and SHAP contrastive explanations"),
    "energy_intelligence": ("ENERGY", "Energy Intelligence", "Electricity, compressed air, water and steam consumption intelligence"),
    "sustainability": ("ENERGY", "Sustainability & ESG", "Carbon footprint, energy cost trend and ESG scorecard reporting"),
    "genai_assistant": ("AI", "GenAI Factory Assistant", "Natural language plant queries and automated report generation"),
}

_STATE_STYLES = {
    "LIVE": ("success", "\u25cf"),
    "SIMULATION": ("maintenance", "\u25d0"),
    "OFFLINE": ("offline", "\u25cb"),
}


def _state_badge(state: str) -> str:
    tone, glyph = _STATE_STYLES.get(state, _STATE_STYLES["LIVE"])
    return f'<span class="status-pill status-{tone}">{glyph} {state}</span>'


import base64
from functools import lru_cache

@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    with open("assets/logo1.png", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{encoded}"


def _brand_block(state: str, ai_active: bool) -> str:
    """Logo + product name + status pills -- mirrors WindSense's persistent
    left-side brand cluster (logo, name, LIVE, AI ACTIVE badges in a row)."""
    ai_badge = f'<span class="status-pill status-ai">\u25c7 AI ACTIVE</span>' if ai_active else ""
    return (
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'<div style="display:flex;align-items:center;gap:9px;">'
        f'<img src="{_logo_data_uri()}" style="width:30px;height:30px;border-radius:7px;'
        f'box-shadow:0 0 12px rgba(32,214,210,0.15);" />'
        f'<div>'
        f'<div style="font-size:0.94rem;font-weight:750;color:{COLORS["text_primary"]};letter-spacing:0.01em;'
        f'font-family:\'Space Grotesk\',sans-serif;line-height:1.1;">NEUROPLANT AI</div>'
        f'<div style="font-size:0.6rem;color:{COLORS["text_muted"]};text-transform:uppercase;'
        f'letter-spacing:0.07em;">Intelligence Engineered for Industry</div></div></div>'
        f'<span style="width:1px;height:26px;background:{COLORS["border"]};display:inline-block;"></span>'
        f'<div style="display:flex;gap:8px;">{_state_badge(state)}{ai_badge}</div>'
        f'</div>'
    )


def render_topbar(page_title: str, page_subtitle: str = "", eyebrow: str = "",
                   plant: str = None, line: str = None, shift: str = None,
                   state: str = "LIVE", breadcrumb: str = "", ai_active: bool = True):
    # Server-render timestamp used as the initial value before the JS
    # ticker (rendered separately below) takes over -- avoids a blank
    # clock for the first frame and ensures something correct shows even
    # if JS injection is blocked in a given browser/embed context.
    now = datetime.now().strftime("%d %b %Y \u00b7 %H:%M:%S")

    eyebrow_html = (
        f'<div style="color:{COLORS["accent_bright"]};font-size:0.64rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.11em;margin-bottom:2px;">{eyebrow}</div>'
    ) if eyebrow else ""

    context_bits = []
    if plant:
        context_bits.append(f'<span style="color:{COLORS["text_secondary"]};">Plant <b style="color:{COLORS["text_primary"]};">{plant}</b></span>')
    if line:
        context_bits.append(f'<span style="color:{COLORS["text_secondary"]};">Line <b style="color:{COLORS["text_primary"]};">{line}</b></span>')
    if shift:
        context_bits.append(f'<span style="color:{COLORS["text_secondary"]};">Shift <b style="color:{COLORS["text_primary"]};">{shift}</b></span>')
    context_html = f'<div style="font-size:0.74rem;display:flex;gap:12px;margin-top:3px;">{"".join(context_bits)}</div>' if context_bits else ""

    html = (
        f'<div class="neuro-topbar">'
        f'<div style="display:flex;align-items:center;gap:22px;padding-left:10px;flex-wrap:wrap;">'
        f'{_brand_block(state, ai_active)}'
        f'<span style="width:1px;height:34px;background:{COLORS["border"]};display:inline-block;"></span>'
        f'<div style="flex:1;min-width:220px;">'
        f'{eyebrow_html}'
        f'<span style="font-size:1.28rem;font-weight:750;color:{COLORS["text_primary"]};letter-spacing:-0.01em;'
        f'font-family:\'Space Grotesk\',sans-serif;">{page_title}</span>'
        f'<div style="color:{COLORS["text_secondary"]};font-size:0.8rem;margin-top:2px;">{page_subtitle}</div>'
        f'{context_html}</div>'
        f'<div style="text-align:right;flex-shrink:0;">'
        f'<div style="display:flex;align-items:center;justify-content:flex-end;gap:7px;'
        f'font-family:\'JetBrains Mono\',monospace;color:{COLORS["text_secondary"]};font-size:0.8rem;">'
        f'<span id="neuro-live-clock">{now}</span>'
        f'<span class="pulse-live" style="width:5px;height:5px;flex-shrink:0;"></span>'
        f'</div>'
        f'</div></div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)
    _render_clock_ticker()


def _render_clock_ticker():
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        (function() {
            function pad(n) { return n.toString().padStart(2, "0"); }
            function tick() {
                var doc = window.parent.document;
                var el = doc.getElementById("neuro-live-clock");
                if (!el) return;
                var d = new Date();
                var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
                var dateStr = d.getDate() + " " + months[d.getMonth()] + " " + d.getFullYear();
                var timeStr = pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
                el.textContent = dateStr + " \u00b7 " + timeStr;
            }
            tick();
            // Clear any previous interval left running by an earlier
            // render of this same iframe (Streamlit can reuse/recreate
            // component iframes across reruns) so ticks don't stack up
            // and fire multiple times per second.
            if (window.parent._neuroClockInterval) {
                clearInterval(window.parent._neuroClockInterval);
            }
            window.parent._neuroClockInterval = setInterval(tick, 1000);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def render_topbar_for_page(page_key: str, **context):
    eyebrow, title, subtitle = PAGE_META.get(page_key, ("", page_key.replace("_", " ").title(), ""))
    render_topbar(title, subtitle, eyebrow=eyebrow, **context)


def render_kpi_strip(kpis: list):
    """Compact equal-weight strip -- kept for pages/sections that genuinely
    want flat KPIs (e.g. a small secondary metrics row)."""
    kpi_pill_bar(kpis)


def render_kpi_hero(kpis: list):
    """Tiered hero KPI row -- hero card (first) + uniform status cards (rest).
    This is the standard entry point for a page's top metric row; pages
    should prefer this over render_kpi_strip for their main KPI row."""
    kpi_row(kpis)