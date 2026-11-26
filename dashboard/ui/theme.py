"""
NeuroPlant AI — Global design system ("Elite Industrial Intelligence").
Palette: Obsidian / Graphite / Deep Navy backgrounds, electric-teal signature
accent, restrained semantic status colors. ~90% neutral dark surfaces,
~5-8% teal intelligence layer, ~5% semantic state colors.

REVISION (bug-fix pass):
  - Added box-shadow tokens (SHADOWS dict) used by kpi_card_lg / kpi_card_status
    / kpi_card_trend / machine_card so KPI + machine cards read as elevated,
    interactive surfaces instead of flat boxes with only a border.
  - Added .neuro-topbar CSS — the topbar previously rendered as bare text
    with no container, which is why it read as "missing" even though the
    function was firing. It now renders as an actual elevated bar.
  - .neuro-card / .neuro-card-elevated / .neuro-card-overlay now carry a
    resting shadow (not just on hover) so cards look intentionally raised.

Single source of truth — no page should hardcode colors.
"""

COLORS = {
    # ── Base backgrounds ─────────────────────────────────────────────
    "bg_primary": "#05080D",      # near-black graphite — app background
    "bg_deep": "#080D14",         # deep industrial navy — sidebar/topbar
    "bg_secondary": "#080D14",
    "bg_graphite": "#0D141D",
    "bg_steel_charcoal": "#111A24",
    "bg_blue_black": "#080D14",

    # ── Surfaces (panel depth system — 4 levels) ────────────────────
    "bg_surface": "#0D141D",         # Level 1 — standard panel
    "bg_card": "#0D141D",
    "bg_surface_alt": "#0F1720",
    "bg_elevated": "#111A24",        # Level 2 — elevated panel
    "bg_overlay": "#15222D",         # Level 3 — active overlay / hover surface
    "bg_hover": "#15222D",
    "bg_input": "#0A0F16",

    # ── Borders ──────────────────────────────────────────────────────
    "border": "rgba(255,255,255,0.06)",
    "border_muted": "rgba(255,255,255,0.04)",
    "border_blue_grey": "rgba(32,214,210,0.20)",   # hover border
    "border_active": "rgba(32,214,210,0.35)",
    "border_critical": "rgba(240,93,94,0.40)",

    # ── Primary NeuroPlant accent — electric industrial teal ───────
    "accent": "#20D6D2",
    "accent_bright": "#4EE8E4",
    "accent_secondary": "#159A97",
    "accent_dim": "rgba(32,214,210,0.12)",
    "accent_cyan": "#20D6D2",     # legacy alias, now = primary accent
    "accent_teal": "#20D6D2",     # legacy alias
    "slate": "#159A97",

    "chart_primary": "#20D6D2",
    "chart_secondary": "#5EA7FF",

    "accent_violet": "#A78BFA",

    # ── Text ─────────────────────────────────────────────────────────
    "text_primary": "#E9EDF2",
    "text_secondary": "#8B96A3",
    "text_muted": "#5A6472",

    # ── Semantic status colors ──────────────────────────────────────
    "success": "#35D399",
    "warning": "#F5B942",
    "danger": "#F05D5E",
    "critical": "#F05D5E",
    "offline": "#5A6472",
    "maintenance": "#F59E0B",
    "info": "#5EA7FF",
    "quality_anomaly": "#F472B6",
    "ai": "#A78BFA",
}

# Shadow tokens — used to give KPI cards / machine cards / panels real depth
# instead of a flat border-only look. Kept subtle (industrial, not "glossy").
SHADOWS = {
    "card_rest": "0 1px 2px rgba(0,0,0,0.35), 0 8px 20px -12px rgba(0,0,0,0.55)",
    "card_hover": "0 2px 4px rgba(0,0,0,0.4), 0 14px 32px -14px rgba(0,0,0,0.65), 0 0 0 1px rgba(32,214,210,0.12)",
    "card_glow_teal": "0 1px 2px rgba(0,0,0,0.35), 0 10px 24px -12px rgba(32,214,210,0.18)",
    "topbar": "0 4px 18px -8px rgba(0,0,0,0.6)",
}

FONT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;650;700;750;800&family=Space+Grotesk:wght@500;600;700;750&family=JetBrains+Mono:wght@400;500;600&display=swap');
"""


def inject_global_css():
    """Call once at the top of streamlit_app.py to apply theme sitewide."""
    import streamlit as st
    st.markdown(f"""
    <style>
    {FONT_CSS}

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}

    /* Subtle industrial grid texture — barely visible, adds depth not attention */
    .stApp {{
        background-color: {COLORS['bg_primary']};
        background-image:
            linear-gradient(rgba(255,255,255,0.012) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.012) 1px, transparent 1px),
            radial-gradient(ellipse 900px 500px at 82% 0%, rgba(32,214,210,0.035), transparent 60%),
            radial-gradient(ellipse 700px 420px at 8% 100%, rgba(32,214,210,0.02), transparent 60%);
        background-size: 42px 42px, 42px 42px, 100% 100%, 100% 100%;
        background-attachment: fixed;
    }}

    .main .block-container {{
        padding-top: 0rem;
        max-width: 1520px;
    }}

    section[data-testid="stSidebar"] {{
        background-color: {COLORS['bg_deep']};
        border-right: 1px solid {COLORS['border']};
        width: 250px !important;
        min-width: 250px !important;
    }}
    section[data-testid="stSidebar"] > div {{
        padding-top: 0.4rem;
    }}
    /* Sidebar made permanent: hides the native collapse-to-icon arrow and
       forces the sidebar open at all times, since a portfolio/demo
       dashboard should never let a reviewer accidentally collapse primary
       navigation and lose their way. */
    button[data-testid="stSidebarCollapseButton"],
    button[data-testid="baseButton-headerNoPadding"][kind="header"] {{
        display: none !important;
    }}
    section[data-testid="stSidebar"][aria-expanded="false"] {{
        min-width: 250px !important;
        margin-left: 0px !important;
    }}

    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{
        background-color: transparent;
        height: 1.1rem;
    }}
    div[data-testid="stDecoration"] {{ display: none; }}
    div[data-testid="stStatusWidget"] {{ display: none; }}
    div[data-testid="stToolbar"] {{ right: 1rem; top: 0.15rem; }}

    /* The clock-ticker iframe (topbar.py's _render_clock_ticker) is
       purely a script host with no visible content -- force it to occupy
       zero layout space so it can never reintroduce topbar dead-space
       even if a given browser/Streamlit version reserves a minimum iframe
       height by default. */
    iframe[title="st.iframe"][height="0"],
    div[data-testid="stIFrame"]:has(iframe[height="0"]),
    div[data-testid="element-container"]:has(iframe[height="0"]) {{
        height: 0px !important;
        min-height: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
        border: none !important;
        overflow: hidden !important;
    }}

    /* ── Metric / KPI cards (native st.metric — kept in sync with kpi_card_*) */
    div[data-testid="stMetric"] {{
        background-color: {COLORS['bg_surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: {SHADOWS['card_rest']};
        transition: border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
    }}
    div[data-testid="stMetric"]:hover {{
        border-color: {COLORS['border_blue_grey']};
        transform: translateY(-2px);
        box-shadow: {SHADOWS['card_hover']};
    }}
    div[data-testid="stMetric"] label {{
        color: {COLORS['text_secondary']} !important;
        font-size: 0.7rem !important;
        text-transform: uppercase;
        letter-spacing: 0.09em;
    }}
    div[data-testid="stMetricValue"] {{
        color: {COLORS['text_primary']} !important;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
    }}
    div[data-testid="stMetricDelta"] svg {{ display: none; }}

    h1, h2, h3 {{
        color: {COLORS['text_primary']} !important;
        font-weight: 750 !important;
        font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    }}

    /* ── Status pills — color + icon glyph, never color alone ────── */
    .status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        border: 1px solid transparent;
        white-space: nowrap;
    }}
    .status-online       {{ background: rgba(53,211,153,0.10);  color: {COLORS['success']};  border-color: rgba(53,211,153,0.22); }}
    .status-warning      {{ background: rgba(245,185,66,0.10);  color: {COLORS['warning']};  border-color: rgba(245,185,66,0.22); }}
    .status-critical     {{ background: rgba(240,93,94,0.10);   color: {COLORS['danger']};   border-color: rgba(240,93,94,0.22); }}
    .status-maintenance  {{ background: rgba(245,158,11,0.10);  color: {COLORS['maintenance']}; border-color: rgba(245,158,11,0.22); }}
    .status-offline      {{ background: rgba(90,100,114,0.10);  color: {COLORS['offline']};  border-color: rgba(90,100,114,0.22); }}
    .status-ai            {{ background: rgba(167,139,250,0.10); color: {COLORS['accent_violet']}; border-color: rgba(167,139,250,0.22); }}
    .status-info          {{ background: rgba(94,167,255,0.10);  color: {COLORS['info']}; border-color: rgba(94,167,255,0.22); }}
    .status-quality       {{ background: rgba(244,114,182,0.10); color: {COLORS['quality_anomaly']}; border-color: rgba(244,114,182,0.22); }}

    /* ── Generic panel (Level 1) ──────────────────────────────────── */
    .neuro-card {{
        background-color: {COLORS['bg_surface']};
        border: 1px solid {COLORS['border_blue_grey']};
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 16px;
        box-shadow: {SHADOWS['card_rest']};
        transition: border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
    }}
    .neuro-card:hover {{
        border-color: {COLORS['accent']};
        transform: translateY(-2px);
        box-shadow: {SHADOWS['card_hover']};
    }}

    /* Level 2 — elevated panel (important operational info) */
    .neuro-card-elevated {{
        background-color: {COLORS['bg_elevated']};
        border: 1px solid {COLORS['border_blue_grey']};
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 16px;
        box-shadow: {SHADOWS['card_glow_teal']};
        transition: box-shadow 180ms ease, transform 180ms ease;
    }}
    .neuro-card-elevated:hover {{
        transform: translateY(-2px);
    }}

    /* Level 3 — active overlay (critical alerts, AI recommendations) */
    .neuro-card-overlay {{
        background-color: {COLORS['bg_overlay']};
        border: 1px solid {COLORS['border_active']};
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 16px;
        box-shadow: 0 0 28px rgba(32,214,210,0.08), {SHADOWS['card_rest']};
    }}

    /* ── Persistent Topbar container ──────────────────────────────
       Previously the topbar had NO background/border container — it was
       raw text floating at the top of the page, which read as "missing"
       even though render_topbar() was firing every page. Now it's a real
       elevated bar, sticky under Streamlit's own header. */
    .neuro-topbar {{
        background: linear-gradient(180deg, {COLORS['bg_elevated']} 0%, {COLORS['bg_deep']} 100%);
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 14px 24px;
        margin: 4px 0 22px 0;
        box-shadow: {SHADOWS['topbar']};
        position: relative;
        overflow: hidden;
    }}
    .neuro-topbar::before {{
        content: "";
        position: absolute;
        left: 0; top: 0; bottom: 0;
        width: 3px;
        background: linear-gradient(180deg, {COLORS['accent']}, {COLORS['accent_secondary']});
    }}

    /* ── Buttons ──────────────────────────────────────────────────── */
    .stButton button {{
        background-color: {COLORS['bg_input']};
        color: {COLORS['text_secondary']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        font-weight: 500;
        transition: border-color 180ms ease, color 180ms ease, background-color 180ms ease;
    }}
    .stButton button:hover {{
        border-color: {COLORS['accent']};
        color: {COLORS['accent_bright']};
    }}
    .stButton button:focus {{
        box-shadow: 0 0 0 1px {COLORS['accent']} !important;
    }}
    .stButton button[kind="primary"] {{
        background-color: {COLORS['bg_elevated']};
        color: {COLORS['accent_bright']};
        border: 1px solid {COLORS['accent']};
        border-left: 3px solid {COLORS['accent']};
        font-weight: 600;
    }}

    section[data-testid="stSidebar"] .stButton button {{
        text-align: left;
        justify-content: flex-start;
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 7px 10px;
        font-size: 0.84rem;
        font-weight: 500;
        color: {COLORS['text_secondary']};
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        background-color: {COLORS['bg_surface']};
        border-color: {COLORS['border']};
        color: {COLORS['text_primary']};
    }}
    section[data-testid="stSidebar"] .stButton button[kind="primary"] {{
        background-color: {COLORS['bg_elevated']};
        border: 1px solid {COLORS['border_blue_grey']};
        border-left: 3px solid {COLORS['accent']};
        color: {COLORS['text_primary']};
        font-weight: 600;
    }}

    /* ── Inputs ───────────────────────────────────────────────────── */
    div[data-baseweb="select"] > div, .stTextInput input {{
        background-color: {COLORS['bg_input']} !important;
        border: 1px solid {COLORS['border_blue_grey']} !important;
        color: {COLORS['text_primary']} !important;
        border-radius: 6px !important;
        transition: border-color 180ms ease;
    }}
    div[data-baseweb="select"] > div:hover, .stTextInput input:hover,
    div[data-baseweb="select"] > div:focus-within, .stTextInput input:focus {{
        border-color: {COLORS['accent']} !important;
    }}
    div[data-baseweb="popover"] {{
        background-color: {COLORS['bg_surface']} !important;
    }}

    button[data-baseweb="tab"] {{
        color: {COLORS['text_secondary']};
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {COLORS['accent_bright']};
        border-bottom-color: {COLORS['accent']} !important;
    }}

    details {{
        background-color: {COLORS['bg_surface']};
        border: 1px solid {COLORS['border_blue_grey']};
        border-radius: 8px;
        transition: border-color 180ms ease;
    }}
    details:hover {{
        border-color: {COLORS['accent']};
    }}
    summary {{
        color: {COLORS['text_primary']} !important;
    }}

    div[data-testid="stDataFrame"] {{
        border: 1px solid {COLORS['border_blue_grey']};
        border-radius: 8px;
    }}
    /* HTML tables built via raw st.markdown (used across most pages for
       benchmark/priority/allocation tables) -- these had no border at
       all previously since they're plain <table> tags inside .neuro-card,
       not a Streamlit-native component theme.py already styled. */
    .neuro-card table {{
        border: 1px solid {COLORS['border_blue_grey']};
        border-radius: 6px;
        overflow: hidden;
    }}

    div[data-testid="stAlert"] {{
        border-radius: 6px;
        border: 1px solid {COLORS['border']};
        background-color: {COLORS['bg_surface']};
    }}

    /* Slider — teal track/handle instead of Streamlit red default */
    div[data-testid="stSlider"] div[role="slider"] {{
        background-color: {COLORS['accent_bright']} !important;
    }}
    div[data-testid="stSlider"] > div > div > div {{
        background-color: {COLORS['accent']} !important;
    }}

    /* Radio — remove default red dot styling in favor of teal */
    div[role="radiogroup"] label span:first-child {{
        border-color: {COLORS['border_blue_grey']} !important;
    }}

    ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
    ::-webkit-scrollbar-track {{ background: {COLORS['bg_primary']}; }}
    ::-webkit-scrollbar-thumb {{ background: {COLORS['border']}; border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {COLORS['border_blue_grey']}; }}

    .main .block-container {{
        animation: neuro-page-fade 260ms cubic-bezier(0.16, 1, 0.3, 1);
    }}
    @keyframes neuro-page-fade {{
        from {{ opacity: 0; transform: translateY(8px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    @media (max-width: 1400px) {{
        .main .block-container {{ padding-left: 1.2rem; padding-right: 1.2rem; }}
    }}
    </style>
    """, unsafe_allow_html=True)


# Backward-compat alias — some earlier pages may import this name directly.
inject_theme = inject_global_css


def status_dot(status: str) -> str:
    color_map = {
        "online": COLORS["success"], "healthy": COLORS["success"], "running": COLORS["success"],
        "warning": COLORS["warning"],
        "critical": COLORS["danger"], "danger": COLORS["danger"],
        "maintenance": COLORS["maintenance"],
        "offline": COLORS["offline"], "idle": COLORS["offline"],
        "ai": COLORS["accent_violet"],
        "info": COLORS["info"],
        "quality": COLORS["quality_anomaly"],
    }
    color = color_map.get(status, COLORS["text_secondary"])
    return f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background-color:{color};margin-right:6px;"></span>'


def status_color(status: str) -> str:
    color_map = {
        "online": COLORS["success"], "healthy": COLORS["success"], "running": COLORS["success"],
        "warning": COLORS["warning"],
        "critical": COLORS["danger"], "danger": COLORS["danger"], "fault": COLORS["danger"],
        "maintenance": COLORS["maintenance"],
        "offline": COLORS["offline"], "idle": COLORS["offline"],
        "ai": COLORS["accent_violet"],
        "info": COLORS["info"],
        "quality": COLORS["quality_anomaly"],
    }
    return color_map.get(status, COLORS["accent"])


def status_icon(status: str) -> str:
    """Small text glyph paired with color so status is never color-only
    (accessibility rule: critical/warning/healthy = color + icon + label,
    never color alone)."""
    icon_map = {
        "online": "●", "healthy": "●", "running": "●",
        "warning": "▲",
        "critical": "■", "danger": "■", "fault": "■",
        "maintenance": "◆",
        "offline": "○", "idle": "○",
        "ai": "◇",
        "info": "●",
        "quality": "◈",
    }
    return icon_map.get(status, "●")


def panel_class(level: int = 1) -> str:
    """Returns the CSS class name for a given panel depth level (1-3)."""
    return {1: "neuro-card", 2: "neuro-card-elevated", 3: "neuro-card-overlay"}.get(level, "neuro-card")