# assistant.py
"""
Layer 10 GenAI Factory Assistant API — natural language factory queries
(text and voice), routed through query_router so answers use live OEE/
downtime context rather than requiring the caller to assemble it.
"""
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.layer10_genai_assistant.query_router import handle_query
from src.layer10_genai_assistant.voice_query_stt import voice_query_to_assistant

router = APIRouter(prefix="/assistant", tags=["assistant"])


class QueryRequest(BaseModel):
    question: str
    line_id: str


@router.post("/query")
async def ask_assistant(req: QueryRequest):
    """Text query — e.g. 'Why did Line 2 OEE drop to 71 percent on Friday evening?'
    Pulls live OEE history + recent downtime for line_id as LLM context."""
    try:
        answer = handle_query(req.question, req.line_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant query failed: {e}")
    return {"question": req.question, "line_id": req.line_id, "answer": answer}


@router.post("/query/voice")
async def ask_assistant_voice(line_id: str, audio: UploadFile = File(...)):
    """Voice query — accepts an audio file (.wav/.mp3), transcribes via Whisper,
    then routes through the same text pipeline as /query."""
    suffix = Path(audio.filename).suffix or ".wav"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        result = voice_query_to_assistant(tmp_path, line_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice query failed: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"line_id": line_id, **result}