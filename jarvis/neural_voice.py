"""Offline neural speech backend for JARVIS.

Uses permissively licensed Kokoro ONNX/voice assets packaged with the setup.
Falls back to Windows SAPI without network or API keys if synthesis fails.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

NEURAL_MODEL = "kokoro-v1.0.int8.onnx"
NEURAL_VOICES = "voices-v1.0.bin"
VOICE_CHOICES = {
    "bm_george": "George — British male",
    "bm_lewis": "Lewis — British male",
    "bf_emma": "Emma — British female",
    "bf_isabella": "Isabella — British female",
    "am_michael": "Michael — American male",
    "af_sarah": "Sarah — American female",
}

def voice_root() -> Path:
    """PyInstaller uses _MEIPASS even for onedir bundled data."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "tts"

def neural_available() -> bool:
    root = voice_root()
    model = root / NEURAL_MODEL
    voices = root / NEURAL_VOICES
    return (model.is_file() and model.stat().st_size > 75_000_000
            and voices.is_file() and voices.stat().st_size > 15_000_000)

def spoken_text(text: str) -> str:
    """Strip markup/URLs which otherwise make TTS stutter or read punctuation."""
    text = re.sub(r"(?s)\x60{3}.*?\x60{3}", " Code sample omitted. ", text)
    text = re.sub(r"https?://\S+", " a web link ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s*[-*]\s+", "", text)
    text = re.sub(r"[*_#~|<>]", "", text)
    return re.sub(r"\s+", " ", text).strip()[:1500]

def speech_segments(text: str, max_chars: int=220) -> list[str]:
    """Split at sentence boundaries so the first utterance starts promptly."""
    clean = spoken_text(text)
    if not clean:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    chunks: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > max_chars and current:
                chunks.append(current)
                current = ""
            current = (current + " " + word).strip()
        if current:
            chunks.append(current)
    return chunks

def create_neural_synthesizer():
    if not neural_available():
        raise RuntimeError("Offline neural TTS model is missing")
    from kokoro_onnx import Kokoro
    root = voice_root()
    return Kokoro(str(root / NEURAL_MODEL), str(root / NEURAL_VOICES))

def synthesize_neural_sample(text: str="JARVIS online. Voice systems ready.") -> tuple[object, int]:
    """Used in Windows CI without depending on a speaker/output device."""
    engine = create_neural_synthesizer()
    audio, rate = engine.create(text, voice="bm_george", speed=1.0, lang="en-gb")
    if len(audio) < 8000 or rate < 16000:
        raise RuntimeError("Neural synthesizer returned an invalid or empty sample")
    return audio, rate
