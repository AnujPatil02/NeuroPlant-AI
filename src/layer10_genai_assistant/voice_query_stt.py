"""
Whisper speech-to-text for voice queries to the GenAI factory assistant.
Records/accepts audio file, transcribes, routes to query_router.
"""
import whisper
from pathlib import Path
from src.layer10_genai_assistant.query_router import handle_query

_model = None


def load_whisper_model(size="base"):
    """base = 74M params, ~150MB — good speed/accuracy tradeoff for factory floor queries."""
    global _model
    if _model is None:
        _model = whisper.load_model(size)
    return _model


def transcribe_audio(audio_path: str) -> str:
    model = load_whisper_model()
    result = model.transcribe(audio_path)
    return result["text"].strip()


def voice_query_to_assistant(audio_path: str, line_id: str) -> dict:
    """Full pipeline: audio -> text -> factory assistant answer."""
    transcribed_text = transcribe_audio(audio_path)
    answer = handle_query(transcribed_text, line_id)
    return {
        "transcribed_question": transcribed_text,
        "answer": answer,
    }


if __name__ == "__main__":
    # Test with a sample audio file — record a .wav/.mp3 asking a factory question
    audio_file = "data/raw/sample_voice_query.wav"
    if Path(audio_file).exists():
        result = voice_query_to_assistant(audio_file, line_id="LINE01")
        print(f"Transcribed: {result['transcribed_question']}")
        print(f"Answer: {result['answer']}")
    else:
        print(f"Place a test audio file at {audio_file} to test voice query")
        print("Record yourself asking: 'Why did OEE drop on this line?'")