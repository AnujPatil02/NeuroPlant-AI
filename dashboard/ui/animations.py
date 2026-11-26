"""
CSS animations/transitions for NeuroPlant AI ("Elite Industrial Intelligence").

Per design system rules: animations must communicate state (live status,
AI activity, loading, panel transitions) — never decoration. Kept
deliberately restrained: no floating effects, no constant motion on static
elements. Colors pulled from theme.COLORS so the teal-accent palette
applies automatically.
"""
import streamlit as st
from dashboard.ui.theme import COLORS


def inject_animation_css():
    """Call once per page (or globally in streamlit_app.py) to enable animation classes."""
    st.markdown(f"""
    <style>
    /* Live status pulse — used only for genuinely live/streaming indicators */
    @keyframes pulse-dot {{
        0% {{ box-shadow: 0 0 0 0 rgba(53,211,153,0.5); }}
        70% {{ box-shadow: 0 0 0 6px rgba(53,211,153,0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(53,211,153,0); }}
    }}

    .pulse-live {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: {COLORS['success']};
        animation: pulse-dot 2s infinite;
    }}

    /* AI engine activity pulse — teal, distinct cadence from live-status green */
    @keyframes pulse-ai {{
        0% {{ box-shadow: 0 0 0 0 rgba(32,214,210,0.5); }}
        70% {{ box-shadow: 0 0 0 7px rgba(32,214,210,0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(32,214,210,0); }}
    }}

    .pulse-ai {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: {COLORS['accent']};
        animation: pulse-ai 1.4s infinite;
    }}

    /* Panel / card entrance — short, once, on load only */
    @keyframes fade-in-up {{
        from {{ opacity: 0; transform: translateY(6px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    .fade-in {{
        animation: fade-in-up 0.25s ease-out;
    }}

    /* Staggered card entrance — apply .fade-in-stagger to each card with an
    inline animation-delay via stagger_delay() below, since Streamlit's DOM
    wrapping makes true nth-child sibling selectors unreliable. */
    .fade-in-stagger {{
        animation: fade-in-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
    }}

    /* Card hover — subtle elevation + border lift, no scale theatrics */
    .neuro-card, .neuro-card-elevated, div[data-testid="stMetric"] {{
        transition: border-color 180ms ease, transform 180ms ease;
    }}

    .neuro-card:hover, .neuro-card-elevated:hover {{
        border-color: {COLORS['accent']};
        transform: translateY(-2px);
    }}

    /* Critical alarm — slow, restrained blink (not urgent-strobe) */
    @keyframes alarm-blink-critical {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.55; }}
    }}

    .alarm-critical {{
        animation: alarm-blink-critical 1.6s infinite;
    }}

    /* Warning — slower breathing pulse, distinct cadence from critical */
    @keyframes alarm-breathe-warning {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.7; }}
    }}

    .alarm-warning {{
        animation: alarm-breathe-warning 2.2s infinite;
    }}

    /* Maintenance — slow rotation, used only on a small indicator icon */
    @keyframes rotate-maintenance {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
    }}

    .maintenance-spin {{
        display: inline-block;
        animation: rotate-maintenance 3s linear infinite;
    }}

    /* Loading skeleton — communicates "data incoming", not decorative */
    @keyframes shimmer {{
        0% {{ background-position: -200px 0; }}
        100% {{ background-position: 200px 0; }}
    }}

    .skeleton-loading {{
        background: linear-gradient(90deg, {COLORS['bg_surface']} 25%, {COLORS['border']} 50%, {COLORS['bg_surface']} 75%);
        background-size: 400px 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 4px;
        height: 60px;
    }}

    /* KPI value update flash — brief brightness pulse on value change */
    @keyframes value-update-flash {{
        0% {{ color: {COLORS['accent_bright']}; }}
        100% {{ color: {COLORS['text_primary']}; }}
    }}

    .value-updated {{
        animation: value-update-flash 0.6s ease-out;
    }}

    /* Page transition — directional slide + opacity, applied at page container level */
    @keyframes page-enter {{
        from {{ opacity: 0; transform: translateY(6px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    .page-transition {{
        animation: page-enter 0.2s ease-out;
    }}

    /* Selection ring — used on 2D machine matrix cells / twin fallback view */
    @keyframes selection-ring {{
        0% {{ box-shadow: 0 0 0 0 rgba(32,214,210,0.45); }}
        100% {{ box-shadow: 0 0 0 4px rgba(32,214,210,0); }}
    }}

    .selection-ring {{
        animation: selection-ring 1.2s ease-out infinite;
    }}
    </style>
    """, unsafe_allow_html=True)


def live_pulse_badge(text: str = "LIVE") -> str:
    """Returns HTML for a pulsing 'LIVE' badge — use inside st.markdown(..., unsafe_allow_html=True)."""
    return f'''
    <span style="display:inline-flex; align-items:center; gap:6px; background:rgba(53,211,153,0.1);
                 color:{COLORS['success']}; padding:3px 10px; border-radius:4px; font-size:0.7rem;
                 font-family:'JetBrains Mono',monospace; font-weight:600; letter-spacing:0.04em;">
        <span class="pulse-live"></span>{text}
    </span>
    '''


def ai_active_badge(text: str = "AI ACTIVE") -> str:
    """Returns HTML for a pulsing teal 'AI ACTIVE' badge — distinct from the
    green live-system pulse, per Elite spec §'AI STATUS SYSTEM'."""
    return f'''
    <span style="display:inline-flex; align-items:center; gap:6px; background:rgba(32,214,210,0.1);
                 color:{COLORS['accent_bright']}; padding:3px 10px; border-radius:4px; font-size:0.7rem;
                 font-family:'JetBrains Mono',monospace; font-weight:600; letter-spacing:0.04em;">
        <span class="pulse-ai"></span>{text}
    </span>
    '''


def stagger_delay(index: int, step_ms: int = 40) -> str:
    """Returns an inline style string for staggered card entrance — apply to
    the outermost div of each card in a loop: f'<div class="fade-in-stagger"
    style="{stagger_delay(i)}">...'. Keeps the 30-50ms stagger from the
    Elite spec without requiring real sibling CSS selectors, which
    Streamlit's per-widget DOM wrapping makes unreliable to target."""
    return f"animation-delay:{index * step_ms}ms;"