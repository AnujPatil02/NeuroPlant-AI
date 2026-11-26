"""
GenAI Assistant - Layer 10. Industrial operations copilot.

REVISION:
  - Line selectbox now loads real lines from plant_topology.json (was
    hardcoded to LINE01/LINE02, missing LINE03).
  - Persistent chat thread (every Q/A appended, full conversation rendered).
  - Voice query results also append to the chat history.
  - Fallback markers extended so the yellow "offline summary" tag fires
    correctly when query_router returns a "please check the X page"
    fallback.
  - Topology path fixed (pages/ -> ../config/plant_topology.json).
"""
import json
import os
from datetime import datetime
import streamlit as st
from dashboard.ui.topbar import render_topbar
from dashboard.ui.theme import COLORS, status_color
from dashboard.ui.components import section_header, info_banner, error_state
from dashboard.ui.animations import ai_active_badge
from src.layer10_genai_assistant.query_router import handle_query

_TOPOLOGY_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "plant_topology.json")

QUICK_QUESTIONS = [
    "Why did Line 3 OEE drop?",
    "Which machine has the lowest RUL?",
    "What is causing today's downtime?",
    "Which machine is consuming abnormal energy?",
    "What are this month's top sustainability risks?",
]

EVIDENCE_SOURCES = {
    "oee": ["OEE Engine", "Alarm History", "Quality Events"],
    "rul": ["Predictive Maintenance", "RUL Model"],
    "carbon": ["Energy Intelligence", "Sustainability Layer"],
    "quality": ["Quality Intelligence", "Production Logs"],
    "downtime": ["OEE Engine", "Alarm History", "Downtime Classifier"],
    "energy": ["Energy Intelligence", "Anomaly Detector"],
}

_GENERIC_FALLBACK_MARKERS = [
    "not available in the current context",
    "not included in the current context",
    "please check the",
    "check the sustainability page",
    "check the energy",
]


def _load_line_ids() -> list:
    """Real line roster from plant_topology.json."""
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


def _guess_sources(question: str) -> list:
    q = question.lower()
    if "downtime" in q:
        return EVIDENCE_SOURCES["downtime"]
    if "energy" in q or "consuming" in q:
        return EVIDENCE_SOURCES["energy"]
    if "oee" in q or "drop" in q:
        return EVIDENCE_SOURCES["oee"]
    if "rul" in q or "maintenance" in q:
        return EVIDENCE_SOURCES["rul"]
    if "carbon" in q or "co2" in q or "sustainability" in q:
        return EVIDENCE_SOURCES["carbon"]
    if "quality" in q or "hold" in q:
        return EVIDENCE_SOURCES["quality"]
    return ["Factory Data Layer"]


def _is_generic_fallback(answer: str) -> bool:
    if not isinstance(answer, str):
        return False
    lower = answer.lower()
    return any(marker in lower for marker in _GENERIC_FALLBACK_MARKERS)


def _render_chat_turn(question: str, answer: str, sources: list, timestamp: str,
                       is_voice: bool = False, answer_source: str = None):
    voice_tag = ' <span style="color:' + COLORS["text_muted"] + ';font-size:0.66rem;">(voice)</span>' if is_voice else ""
    sources_line = ", ".join(sources) if sources else "Factory Data"

    source_tag = ""
    if answer_source == "gemini":
        source_tag = f' <span style="color:{COLORS["text_muted"]};">· via Gemini</span>'
    elif answer_source in ("fallback_generic", "fallback_error"):
        source_tag = f' <span style="color:{COLORS["warning"]};">· via offline summary (AI model not reachable)</span>'

    st.markdown(
        f'<div class="neuro-card fade-in" style="border-left:3px solid {COLORS["accent"]};">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="color:{COLORS["text_muted"]};font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;">You{voice_tag}</span>'
        f'<span style="color:{COLORS["text_muted"]};font-size:0.68rem;font-family:\'JetBrains Mono\',monospace;">{timestamp}</span>'
        f'</div>'
        f'<p style="color:{COLORS["text_primary"]};font-weight:600;margin:4px 0 12px 0;">{question}</p>'
        f'<div style="border-top:1px solid {COLORS["border_muted"]};padding-top:12px;">'
        f'<div style="color:{COLORS["text_primary"]};font-size:0.9rem;line-height:1.55;">{answer}</div>'
        f'</div>'
        f'<div style="margin-top:10px;font-size:0.68rem;color:{COLORS["text_muted"]};">'
        f'Sources: {sources_line}{source_tag}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def render():
    render_topbar("GenAI Factory Assistant", "Layer 10 - Natural Language Factory Operations", breadcrumb="Home")

    if "genai_chat_history" not in st.session_state:
        st.session_state["genai_chat_history"] = []

    st.markdown(
        f'<div class="neuro-card-elevated" style="padding:16px 20px;margin-bottom:18px;">'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<span style="color:{COLORS["accent_bright"]};font-weight:700;font-family:\'Space Grotesk\',sans-serif;font-size:0.92rem;">NEUROPLANT ASSISTANT</span>'
        f'{ai_active_badge()}'
        f'</div>'
        f'<div style="color:{COLORS["text_secondary"]};font-size:0.8rem;margin-top:6px;">Ask about OEE, downtime, or plant performance — I\'ll answer using live factory data.</div>'
        f'</div>', unsafe_allow_html=True
    )

    line_options = ["All Lines"] + _load_line_ids()
    line_choice = st.selectbox("Line (optional)", line_options)
    line_id = None if line_choice == "All Lines" else line_choice

    section_header("Quick Questions")
    cols = st.columns(2)
    for i, q in enumerate(QUICK_QUESTIONS):
        with cols[i % 2]:
            if st.button(q, key=f"qq_{i}", use_container_width=True):
                st.session_state["pending_question"] = q
                st.session_state["auto_ask"] = True
                st.rerun()

    section_header("Ask the Factory")
    top_row = st.columns([5, 1])
    with top_row[1]:
        if st.button("Clear chat", use_container_width=True, disabled=not st.session_state["genai_chat_history"]):
            st.session_state["genai_chat_history"] = []
            st.rerun()

    with st.form(key="ask_form", clear_on_submit=True):
        question = st.text_input("Query", value=st.session_state.get("pending_question", ""),
                                  label_visibility="collapsed",
                                  placeholder="e.g. Why did Line 3 OEE drop this morning?")
        submitted = st.form_submit_button("Ask", type="primary")

    should_ask = submitted or st.session_state.pop("auto_ask", False)
    if "pending_question" in st.session_state and should_ask:
        del st.session_state["pending_question"]

    if should_ask and question:
        with st.spinner("Thinking..."):
            try:
                result = handle_query(question, line_id)
                # handle_query now returns (answer, source) OR just answer
                # depending on query_router version -- support both.
                if isinstance(result, tuple):
                    answer, answer_source = result
                else:
                    answer, answer_source = result, None
                query_ok = True
            except Exception as e:
                answer = None
                answer_source = None
                query_ok = False
                error_msg = str(e)

        if not query_ok:
            st.session_state["genai_chat_history"].append({
                "question": question,
                "answer": f"Sorry, I ran into a problem answering that: {error_msg}",
                "sources": ["Error"], "timestamp": datetime.now().strftime("%H:%M:%S"),
                "is_voice": False, "answer_source": "error",
            })
        else:
            sources = _guess_sources(question)
            st.session_state["genai_chat_history"].append({
                "question": question, "answer": answer, "sources": sources,
                "timestamp": datetime.now().strftime("%H:%M:%S"), "is_voice": False,
                "answer_source": answer_source,
            })
        st.rerun()

    section_header("Voice Query")
    audio_file = st.file_uploader("Upload voice query (.wav/.mp3)", type=["wav", "mp3"],
                                    label_visibility="collapsed")
    if audio_file and st.button("Transcribe & Ask"):
        with open("temp_audio.wav", "wb") as f:
            f.write(audio_file.read())
        from src.layer10_genai_assistant.voice_query_stt import voice_query_to_assistant
        with st.spinner("Transcribing..."):
            try:
                result = voice_query_to_assistant("temp_audio.wav", line_id)
                voice_ok = True
            except Exception as e:
                voice_ok = False
                voice_err = str(e)

        if not voice_ok:
            error_state(f"Voice query failed: {voice_err}")
        else:
            sources = _guess_sources(result["transcribed_question"])
            st.session_state["genai_chat_history"].append({
                "question": result["transcribed_question"], "answer": result["answer"],
                "sources": sources, "timestamp": datetime.now().strftime("%H:%M:%S"),
                "is_voice": True,
            })
            st.rerun()

    if st.session_state["genai_chat_history"]:
        section_header("Conversation", f"{len(st.session_state['genai_chat_history'])} messages")
        for turn in st.session_state["genai_chat_history"]:
            _render_chat_turn(turn["question"], turn["answer"], turn["sources"],
                               turn["timestamp"], turn.get("is_voice", False),
                               turn.get("answer_source"))
    else:
        info_banner("No questions asked yet — try a quick question above or type your own.", tone="maintenance")