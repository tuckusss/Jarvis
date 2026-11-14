"""Push-to-talk + optional local Vosk wake phrase. Cloud transcription is opt-in by pressing Listen."""
from __future__ import annotations
import io
import json
import queue
import threading
import time
import wave
from functools import lru_cache
import numpy as np

SAMPLE_RATE = 16000


def record_phrase(max_seconds=11, stop_after_silence=1.3) -> bytes:
    import sounddevice as sd
    audio = []
    started = False
    silent_chunks = 0
    blocksize = 1600  # 0.1 seconds
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=blocksize, dtype="int16", channels=1) as stream:
        for _ in range(int(max_seconds * SAMPLE_RATE / blocksize)):
            chunk, overflowed = stream.read(blocksize)
            b = bytes(chunk)
            audio.append(b)
            arr = np.frombuffer(b, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(arr * arr)))
            if rms > 380:
                started = True
                silent_chunks = 0
            elif started:
                silent_chunks += 1
            if started and silent_chunks >= int(stop_after_silence * SAMPLE_RATE / blocksize):
                break
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(audio))
    return out.getvalue()


def transcribe(wav_bytes: bytes, openai_client, model: str) -> str:
    data = io.BytesIO(wav_bytes)
    data.name = "command.wav"
    result = openai_client.audio.transcriptions.create(model=model, file=data)
    return (result.text or "").strip()


@lru_cache(maxsize=2)
def _local_vosk_model(path: str):
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    return Model(path)


def transcribe_local(wav_bytes: bytes, model_path: str) -> str:
    """Recognize the command using bundled Vosk, without network/API usage."""
    from vosk import KaldiRecognizer
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("Unsupported microphone format for offline transcription")
        recognizer = KaldiRecognizer(_local_vosk_model(str(model_path)), SAMPLE_RATE)
        segments = []
        while True:
            block = wav.readframes(4000)
            if not block:
                break
            if recognizer.AcceptWaveform(block):
                segment = json.loads(recognizer.Result()).get("text", "").strip()
                if segment:
                    segments.append(segment)
        tail = json.loads(recognizer.FinalResult()).get("text", "").strip()
        if tail:
            segments.append(tail)
        return " ".join(segments).strip()


class Speaker:
    """Single non-blocking TTS worker to avoid simultaneous SAPI engine calls."""
    def __init__(self, on_finished=None):
        self.on_finished = on_finished
        self.pending: queue.Queue = queue.Queue(maxsize=8)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._work, daemon=True, name="jarvis-tts")
        self.thread.start()

    def speak(self, text: str) -> None:
        if not text.strip() or self.stop_event.is_set():
            return
        try:
            self.pending.put_nowait(text[:2500])
        except queue.Full:
            pass

    def _work(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 178)
        except Exception:
            # Surface failure to the owner so its wake listener is not held off.
            while not self.stop_event.is_set():
                try:
                    entry = self.pending.get(timeout=0.2)
                    if entry is None: break
                    if self.on_finished: self.on_finished()
                except queue.Empty:
                    continue
            return
        while not self.stop_event.is_set():
            try:
                text = self.pending.get(timeout=0.2)
            except queue.Empty:
                continue
            if text is None:
                break
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
            finally:
                if self.on_finished:
                    self.on_finished()

    def stop(self):
        self.stop_event.set()
        try:
            self.pending.put_nowait(None)
        except queue.Full:
            pass


class WakeListener:
    """Offline wake-word (small Vosk model required). The microphone isn't sent online.
    Uses a narrow grammar; it is not speaker authentication. No privileged action follows without policy checks.
    """
    def __init__(self, model_path: str, on_wake, on_error):
        self.model_path = model_path
        self.on_wake = on_wake
        self.on_error = on_error
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name="jarvis-wake")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        # Give the audio device time to release before push-to-talk opens it.
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=0.65)

    def _run(self):
        try:
            from vosk import KaldiRecognizer
            import sounddevice as sd
            model = _local_vosk_model(self.model_path)
            recognizer = KaldiRecognizer(model, SAMPLE_RATE, json.dumps(["jarvis", "hey jarvis", "[unk]"]))
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000, dtype="int16", channels=1) as stream:
                while not self.stop_event.is_set():
                    chunk, _ = stream.read(4000)
                    if recognizer.AcceptWaveform(bytes(chunk)):
                        words = json.loads(recognizer.Result()).get("text", "")
                        if "jarvis" in words.lower():
                            self.stop_event.set()
                            self.on_wake()
                            break
        except Exception as exc:
            self.on_error("Wake listener unavailable: " + str(exc))
