import streamlit as st
from dashboard.ui.components import render_system_status_sidebar
from dashboard.ui.theme import COLORS

NAV_GROUPS = [
    ("COMMAND", [("home", "Command Center", "◆")]),
    ("MONITOR", [("machine_monitoring", "Machine Monitoring", "▣")]),
    ("INTELLIGENCE", [("oee_analytics", "OEE Analytics", "▦"),
                       ("predictive_maintenance", "Predictive Maintenance", "◈"),
                       ("production_quality", "Production & Quality", "▶")]),
    ("ENERGY", [("energy_sustainability", "Energy & ESG", "▲")]),
    ("AI", [("genai_assistant", "GenAI Assistant", "◇")]),
]

PAGES = [label for _, items in NAV_GROUPS for _, label, _ in items]
PAGE_KEYS = {label: key for _, items in NAV_GROUPS for key, label, _ in items}
PAGE_ICONS = {label: icon for _, items in NAV_GROUPS for _, label, icon in items}


import base64
from functools import lru_cache

@lru_cache(maxsize=1)
def _sidebar_logo_data_uri() -> str:
    with open("assets/logo1.png", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{encoded}"


def render_logo_block():
    st.sidebar.markdown(
        f'<div style="padding:18px 6px 18px 6px;border-bottom:1px solid {COLORS["border"]};margin-bottom:14px;'
        f'display:flex;flex-direction:column;align-items:center;text-align:center;">'
        f'<img src="{_sidebar_logo_data_uri()}" style="width:64px;height:64px;margin-bottom:10px;" />'
        f'<div style="font-size:1.02rem;font-weight:700;color:{COLORS["text_primary"]};letter-spacing:0.01em;'
        f'font-family:\'Space Grotesk\',sans-serif;">NEUROPLANT AI</div>'
        f'<div style="font-size:0.62rem;color:{COLORS["text_muted"]};text-transform:uppercase;'
        f'letter-spacing:0.08em;margin-top:5px;">Intelligence Engineered for Industry</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def render_sidebar() -> str:
    render_logo_block()

    if "nav_selected" not in st.session_state:
        st.session_state["nav_selected"] = PAGES[0]

    # Backward-compat: if a previously-saved session still has one of the
    # 3 now-merged page labels selected (e.g. from before this revision,
    # via browser localStorage/session persistence), redirect it to the
    # new merged page label instead of landing on an unknown selection.
    _LEGACY_REDIRECTS = {
        "Digital Twin": "Machine Monitoring",
        "Production Optimizer": "Production & Quality",
        "Quality Intelligence": "Production & Quality",
        "Energy Intelligence": "Energy & ESG",
        "Sustainability & ESG": "Energy & ESG",
    }
    if st.session_state["nav_selected"] in _LEGACY_REDIRECTS:
        st.session_state["nav_selected"] = _LEGACY_REDIRECTS[st.session_state["nav_selected"]]

    for group_label, items in NAV_GROUPS:
        st.sidebar.markdown(
            f'<div style="font-size:0.6rem;color:{COLORS["text_muted"]};text-transform:uppercase;'
            f'letter-spacing:0.1em;margin:16px 0 4px 6px;">{group_label}</div>',
            unsafe_allow_html=True
        )
        for key, label, icon in items:
            is_active = st.session_state["nav_selected"] == label
            display_label = f"{icon}  {label}"
            if st.sidebar.button(display_label, key=f"nav_{key}", use_container_width=True,
                                  type="primary" if is_active else "secondary"):
                st.session_state["nav_selected"] = label
                st.rerun()

    st.sidebar.markdown(f'<div style="margin-top:18px;border-top:1px solid {COLORS["border"]};"></div>', unsafe_allow_html=True)
    render_system_status_sidebar()

    return st.session_state["nav_selected"]