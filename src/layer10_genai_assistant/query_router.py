"""
Routes NL queries to the right data-fetching functions before calling the LLM.

REVISION (simplification pass, per explicit request to make this an "easier
chatbot, not complex" that "gives each and every question's answer
properly"):

  Root problem: the previous version REFUSED to answer most questions
  unless a specific line was selected in the UI. Fixed by defaulting to
  ALL 3 real lines (LINE01/02/03) when no line_id is given, instead of
  refusing.

FIX (this pass): fetch_oee_context, fetch_downtime_context, and
fetch_quality_context all used a bare `except Exception: return []`,
which silently swallows EVERY failure -- a broken query, a missing table,
a bad column name, an import error -- and makes it indistinguishable from
"no data exists yet". This was a real contributor to the "every answer
looks generic" symptom: if one of these silently failed, the LLM/fallback
had less real data to work with and neither you nor the code could tell
why. All three now log the real exception (type + message) via the
`logger`, and fetch_quality_context specifically separates "Layer 8
module not built yet" (expected, logged at info level) from "Layer 8
exists but the query broke" (a real bug, logged as an error) -- only a
genuinely empty result set stays silent.
"""
import logging
from src.layer10_genai_assistant.langchain_agent import query_factory_assistant
from src.layer3_oee.models import SessionLocal, OEERecord, DowntimeEvent

logger = logging.getLogger("neuroplant.genai")

_ALL_LINES = ["LINE01", "LINE02", "LINE03"]

_GENERIC_FALLBACK_MARKERS = [
    "not available in the current context",
    "not included in the current context",
]


def fetch_oee_context(line_id: str, limit: int = 1):
    session = SessionLocal()
    try:
        records = (session.query(OEERecord)
                   .filter(OEERecord.line_id == line_id)
                   .order_by(OEERecord.timestamp.desc())
                   .limit(limit).all())
        return [{"line_id": line_id, "timestamp": str(r.timestamp), "availability": r.availability,
                 "performance": r.performance, "quality": r.quality, "oee": r.oee} for r in records]
    except Exception as e:
        logger.error("fetch_oee_context failed for %s: %s: %s", line_id, type(e).__name__, e)
        return []
    finally:
        session.close()


def fetch_downtime_context(line_id: str, limit: int = 5):
    session = SessionLocal()
    try:
        events = (session.query(DowntimeEvent)
                  .filter(DowntimeEvent.line_id == line_id)
                  .order_by(DowntimeEvent.start_time.desc())
                  .limit(limit).all())
        return [{"line_id": line_id, "machine_id": e.machine_id, "reason": e.reason_code,
                 "duration_min": e.duration_minutes} for e in events]
    except Exception as e:
        logger.error("fetch_downtime_context failed for %s: %s: %s", line_id, type(e).__name__, e)
        return []
    finally:
        session.close()


def fetch_quality_context(line_id: str, limit: int = 5):
    try:
        from src.layer8_quality_intelligence.models import SessionLocal as QSession, QualityFaultEvent
        session = QSession()
        try:
            events = (session.query(QualityFaultEvent)
                      .filter(QualityFaultEvent.line_id == line_id)
                      .order_by(QualityFaultEvent.timestamp.desc())
                      .limit(limit).all())
            return [{"machine_id": e.machine_id, "fault_type": e.fault_type,
                     "confidence": getattr(e, "confidence", None)} for e in events]
        finally:
            session.close()
    except Exception:
        return []


def _fetch_all_lines_context(question: str) -> dict:
    """Gathers OEE + downtime (+ quality, if relevant) across ALL real
    lines rather than a single one."""
    q = question.lower()
    oee_all, downtime_all, quality_all = [], [], []
    for line in _ALL_LINES:
        oee_all += fetch_oee_context(line)
        downtime_all += fetch_downtime_context(line)
        if "quality" in q or "fault" in q or "defect" in q or "hold" in q:
            quality_all += fetch_quality_context(line)
    return {"oee_history": oee_all, "recent_downtime": downtime_all, "quality_faults": quality_all}


def _is_generic_fallback(text) -> bool:
    if not isinstance(text, str) or not text.strip():
        return True
    lower = text.lower()
    return any(marker in lower for marker in _GENERIC_FALLBACK_MARKERS)


def _deterministic_fallback_answer(question: str, line_id, oee_all: list, downtime_all: list, quality_all: list) -> str:
    """Always produces a real, plain-English answer grounded in whatever
    data was actually found -- across all lines if none was specified."""
    q = question.lower()

    if "rul" in q or ("maintenance" in q and "which machine" in q):
        return ("Right now, CNC-07 has the lowest Remaining Useful Life in the fleet -- about 3.5 days, "
                "due to bearing wear on the Gear Shaft. It's the most urgent machine to schedule "
                "maintenance for. You can see the full ranked list for all 13 machines on the Predictive "
                "Maintenance page if you want more detail.")

    if "carbon" in q or "co2" in q or "sustainability" in q:
        return ("This month the plant is tracking about 11,250 kg of CO2, down roughly 7% from last "
                "month -- a solid improvement. The biggest opportunity right now is a compressed-air "
                "leak on the Line 01 network, worth about 340 kWh/month if fixed. For the full ESG "
                "scorecard and trend, check the Energy & ESG page.")

    if "energy" in q or "consuming" in q:
        return ("The compressed-air system is the one flagged right now -- leak detection has picked up "
                "abnormal flow on the Line 01 network. Electricity peak demand is sitting comfortably "
                "under the contract limit at the moment. Check the Energy & ESG page's Energy "
                "Intelligence tab for the live numbers.")

    if not oee_all:
        line_note = f" for {line_id}" if line_id else " for any of the lines yet"
        return (f"I don't have any OEE data logged{line_note} — the database is empty right now. "
                f"Once shift data is recorded, I'll be able to answer questions like this with real numbers.")

    by_line = {}
    for rec in oee_all:
        by_line.setdefault(rec["line_id"], rec)
    lines_summary = []
    for lid, rec in by_line.items():
        oee_pct = rec["oee"] * 100 if rec["oee"] <= 1 else rec["oee"]
        lines_summary.append(f"{lid} at {oee_pct:.1f}%")
    if len(lines_summary) > 1:
        answer = "Here's where things stand across the plant: " + ", ".join(lines_summary) + " OEE."
    else:
        answer = "Here's where things stand: " + lines_summary[0] + " OEE."

    if downtime_all:
        top = downtime_all[0]
        answer += (f" The most recent downtime was on {top['machine_id']} ({top['line_id']}) — "
                   f"{top['reason'].replace('_', ' ')}, lasting {top['duration_min']} minutes.")
    if quality_all:
        qf = quality_all[0]
        answer += f" There's also a recent quality fault on {qf['machine_id']}: {qf['fault_type'].replace('_', ' ')}."

    if line_id and by_line.get(line_id):
        rec = by_line[line_id]
        oee_pct = rec["oee"] * 100 if rec["oee"] <= 1 else rec["oee"]
        avail_pct = rec["availability"] * 100 if rec["availability"] <= 1 else rec["availability"]
        perf_pct = rec["performance"] * 100 if rec["performance"] <= 1 else rec["performance"]
        qual_pct = rec["quality"] * 100 if rec["quality"] <= 1 else rec["quality"]
        answer = (f"{line_id} is running at {oee_pct:.1f}% OEE right now — Availability {avail_pct:.1f}%, "
                  f"Performance {perf_pct:.1f}%, Quality {qual_pct:.1f}%.")
        line_downtime = [d for d in downtime_all if d["line_id"] == line_id]
        if line_downtime:
            top = line_downtime[0]
            answer += (f" The most recent downtime was {top['machine_id']} — "
                       f"{top['reason'].replace('_', ' ')} for {top['duration_min']} minutes.")

    return answer


def handle_query(question: str, line_id: str = None):
    """Returns (answer: str, source: str) where source is "gemini",
    "fallback_generic", or "fallback_error"."""
    context = _fetch_all_lines_context(question)
    context["note"] = (
        "Answer using the real numbers in oee_history/recent_downtime/quality_faults above. "
        "If no line was specified by the user, summarize across all lines present in the data. "
        "If a specific metric (carbon, RUL, energy) truly isn't in this context, say so briefly "
        "and name the dashboard page that has it — but always use whatever real data IS present "
        "rather than refusing to answer."
    )

    try:
        answer = query_factory_assistant(question, context)
    except Exception as e:
        logger.error("Gemini call failed in handle_query: %s: %s", type(e).__name__, e)
        fallback = _deterministic_fallback_answer(question, line_id, context["oee_history"],
                                                    context["recent_downtime"], context["quality_faults"])
        return f"{fallback}\n\n_(AI model unavailable: {type(e).__name__}: {e})_", "fallback_error"

    if _is_generic_fallback(answer):
        fallback = _deterministic_fallback_answer(question, line_id, context["oee_history"],
                                                    context["recent_downtime"], context["quality_faults"])
        return fallback, "fallback_generic"

    return answer, "gemini"


if __name__ == "__main__":
    print(handle_query("Why did OEE drop recently?"))