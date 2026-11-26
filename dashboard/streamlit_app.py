"""NeuroPlant AI - Main Streamlit router. 7 pages via centralized sidebar.

REVISION (10 -> 7 page merge):
  PAGE_MODULES updated to match sidebar.py's new 7-entry NAV_GROUPS.
  digital_twin, production_optimizer, quality_intelligence,
  energy_intelligence, and sustainability are no longer separate page_key
  values -- they were merged into machine_monitoring (now Live Sensors +
  Digital Twin tabs), production_quality (Production Optimizer + Quality
  Intelligence tabs), and energy_sustainability (Energy Intelligence +
  Sustainability & ESG tabs) respectively. Their render() logic still
  exists in full, just inside the merged page modules instead of
  standalone page files -- see machine_monitoring.py, production_quality.py,
  energy_sustainability.py in dashboard/pages/.
"""
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dashboard.ui.theme import inject_global_css
from dashboard.ui.animations import inject_animation_css
from dashboard.ui.sidebar import render_sidebar, PAGE_KEYS

import streamlit as st
from PIL import Image

logo_img = Image.open("assets/logo.png")

st.set_page_config(
    page_title="NeuroPlant AI",
    page_icon=logo_img,        # browser tab icon
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()
inject_animation_css()

selected_label = render_sidebar()
page_key = PAGE_KEYS.get(selected_label)

# 7-page structure (was 10) -- mirrors sidebar.py's NAV_GROUPS exactly.
# Each merged module's render() internally uses st.tabs() to switch
# between the sub-pages that used to be separate sidebar entries.
PAGE_MODULES = {
    "home": "pages.home",
    "machine_monitoring": "pages.machine_monitoring",       # Live Sensors + Digital Twin tabs
    "oee_analytics": "pages.oee_analytics",
    "predictive_maintenance": "pages.predictive_maintenance",
    "production_quality": "pages.production_quality",       # Production Optimizer + Quality Intelligence tabs
    "energy_sustainability": "pages.energy_sustainability", # Energy Intelligence + Sustainability & ESG tabs
    "genai_assistant": "pages.genai_assistant",
}

# Topbar's right-side badge is a static "LIVE" label describing the overall
# platform mode, NOT a per-page data-freshness claim — individual pages with
# real backend calls render their own freshness_badge() next to the actual
# data it describes (see components.py). This avoids the topbar implying
# freshness it can't verify.

module_path = PAGE_MODULES.get(page_key)
if module_path:
    import importlib
    page_module = importlib.import_module(module_path)
    page_module.render()
else:
    st.error(f"Unknown page: {selected_label}")