"""
GenAI Factory Assistant - LangChain + Gemini, answers NL queries by pulling
context from Layer 3 (OEE), Layer 2 (alarms), Layer 4 (RUL/faults), Layer 8 (quality).

REVISION #2 (model name correction):
  Previous revision incorrectly "fixed" the model string from
  "gemini-3.6-flash" to "gemini-2.0-flash", reasoning that no 3.6
  generation existed. That reasoning was based on static training-data
  knowledge, which has a cutoff and does not include later Gemini
  releases. The ACTUAL Gemini API error returned when this was deployed
  was authoritative and said the opposite: gemini-2.0-flash is no longer
  available (deprecated/retired) and the account should use
  gemini-3.6-flash. Reverted to gemini-3.6-flash, which is correct per
  that live API response.

  General lesson encoded here: a live 404 response FROM the API is always
  more trustworthy than an LLM's memorized model-name knowledge, which
  goes stale the moment a new model ships. GEMINI_MODEL is now read from
  settings (with gemini-3.6-flash as the coded default) specifically so
  future model deprecations/renames are a one-line settings change, not
  a code change requiring a redeploy.

  Root cause of issue #8 ("every answer looks the same generic non-answer")
  was NOT actually the model name being wrong in the original file — it was
  the combination of (a) no error handling around the Gemini call, so a
  transient/real failure produced no visible reason, and (b) query_router.py
  not distinguishing "LLM failed" from "LLM succeeded but had nothing to
  say". Both of those are still fixed below independent of whichever exact
  model string is correct at any given time.
"""
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from src.config.settings import settings

# Gemini model identifier. Defaults to gemini-3.6-flash per the live Gemini
# API's own guidance (see revision note above) — override via
# settings.gemini_model in config if your account is later migrated to a
# different model, without needing to edit this file again.
GEMINI_MODEL = getattr(settings, "gemini_model", None) or "gemini-3.6-flash"


def _validate_config():
    """Fails fast with a clear message if the Gemini API key is missing,
    instead of letting every query silently fail later with an opaque
    auth error buried inside LangChain's exception chain."""
    key = getattr(settings, "gemini_api_key", None)
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured (settings.gemini_api_key is empty/None). "
            "Set it in your environment/.env file before querying the GenAI assistant."
        )


_validate_config()

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=settings.gemini_api_key,
    temperature=0.3,
)

FACTORY_ASSISTANT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are NeuroPlant AI's factory assistant. Answer using the context given.
If the specific metric asked isn't in context, briefly say so and point to which
dashboard page covers it (e.g. "Check the Sustainability page for carbon data"),
rather than refusing outright. Be concise and actionable. Always reference the
actual numbers present in the context data when they are relevant to the question --
never claim data is unavailable if it is already present in the context you were given."""),
    ("human", "Context data:\n{context}\n\nQuestion: {question}")
])


def query_factory_assistant(question: str, context: dict) -> str:
    """
    context: dict combining relevant data from Layers 2,3,4,5,7,8
    e.g. {"oee_history": [...], "recent_downtime": [...], "quality_faults": [...]}

    Raises RuntimeError with a specific, diagnosable message if the Gemini
    call fails (previously this could raise a bare, hard-to-diagnose
    exception from deep inside langchain_google_genai, or -- worse --
    silently produce no real answer at all if the model name was invalid).
    """
    chain = FACTORY_ASSISTANT_PROMPT | llm
    try:
        response = chain.invoke({
            "context": json.dumps(context, indent=2, default=str),
            "question": question,
        })
    except Exception as e:
        err_str = str(e).lower()
        if "api key" in err_str or "unauthenticated" in err_str or "permission" in err_str:
            raise RuntimeError(f"Gemini API authentication failed — check GEMINI_API_KEY is valid. Original error: {e}")
        if "no longer available" in err_str or "deprecated" in err_str:
            raise RuntimeError(f"Gemini model '{GEMINI_MODEL}' has been retired by Google — the API response should name the replacement model to use; update GEMINI_MODEL accordingly. Original error: {e}")
        if "model" in err_str and ("not found" in err_str or "not supported" in err_str):
            raise RuntimeError(f"Gemini model '{GEMINI_MODEL}' not found/supported by this API key — verify the model name against your Google AI Studio account. Original error: {e}")
        if "quota" in err_str or "rate" in err_str or "429" in err_str:
            raise RuntimeError(f"Gemini API quota/rate limit hit — try again shortly. Original error: {e}")
        raise RuntimeError(f"Gemini call failed unexpectedly: {e}")

    if not response or not getattr(response, "content", None):
        raise RuntimeError("Gemini returned an empty response.")

    return response.content


if __name__ == "__main__":
    sample_context = {
        "oee": {"line_id": "LINE02", "shift": "evening", "availability": 0.85, "performance": 0.79, "quality": 0.94, "oee": 0.71},
        "alarms": [{"machine_id": "ST04", "type": "coolant_pump", "time": "19:23", "duration_min": 47}],
        "quality_faults": [{"sku": "SKU-118", "fault_type": "dimensional_variance", "count": 12, "machine_id": "SpindleB"}],
    }
    answer = query_factory_assistant(
        "Why did Line 2 OEE drop to 71 percent on Friday evening?",
        sample_context
    )
    print(answer)