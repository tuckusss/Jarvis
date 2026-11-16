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


def record_phrase(max_seconds=9, stop_after_silence=0.7, start_timeout_s=4.0) -> bytes:
    import sounddevice as sd
    audio = []
    started = False
    silent_chunks = 0
    blocksize = 1600  # 0.1 seconds
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=blocksize, dtype="int16", channels=1) as stream:
        for index in range(int(max_seconds * SAMPLE_RATE / blocksize)):
            if not started and index * blocksize / SAMPLE_RATE >= start_timeout_s:
                break
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
    """Persistent neural TTS worker, with offline SAPI fallback.

    Each new utterance invalidates the previous one and replaces queued speech.
    No network, OpenAI key or extra installs are needed by the end user.
    """
    def __init__(self, on_finished=None, on_error=None, engine="neural",
                 voice="bm_george", speed=1.0):
        self.on_finished = on_finished
        self.on_error = on_error
        self.pending: queue.Queue = queue.Queue(maxsize=32)
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._generation = 0
        self._neural = None
        self._sapi = None
        self.configure(engine=engine, voice=voice, speed=speed)
        self.thread = threading.Thread(target=self._work, daemon=True, name="jarvis-tts")
        self.thread.start()

    def configure(self, *, engine: str, voice: str, speed: float):
        from .neural_voice import VOICE_CHOICES
        with self._lock:
            self.engine = engine if engine in {"neural", "sapi"} else "neural"
            self.voice = voice if voice in VOICE_CHOICES else "bm_george"
            self.speed = max(0.8, min(1.3, float(speed)))

    def speak(self, text: str) -> None:
        if not text.strip() or self.stop_event.is_set():
            return
        with self._lock:
            self._generation += 1
            generation = self._generation
            while True:
                try:
                    self.pending.get_nowait()
                except queue.Empty:
                    break
            self.pending.put_nowait((generation, text[:2500]))
        # Interrupt previous playback, but only if a newer generation exists.
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass


    def enqueue(self, text: str) -> None:
        """Append a sentence without cutting off the previous audio segment."""
        if not text.strip() or self.stop_event.is_set():
            return
        with self._lock:
            if self._generation == 0:
                self._generation = 1
            try:
                self.pending.put_nowait((self._generation, text[:1200]))
            except queue.Full:
                # Voice backlog must not accumulate without bound.
                if self.on_error:
                    self.on_error("Voice playback is behind; some speech was skipped")

    def interrupt(self):
        """Stop neural audio, discard queued fragments, keep worker alive."""
        with self._lock:
            self._generation += 1
            while True:
                try:
                    self.pending.get_nowait()
                except queue.Empty:
                    break
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    def _active(self, generation: int) -> bool:
        with self._lock:
            return not self.stop_event.is_set() and generation == self._generation

    def _speak_neural(self, text: str, generation: int, voice: str, speed: float):
        from .neural_voice import create_neural_synthesizer, speech_segments
        import sounddevice as sd
        if self._neural is None:
            self._neural = create_neural_synthesizer()
        lang = "en-gb" if voice.startswith("b") else "en-us"
        for segment in speech_segments(text):
            if not self._active(generation):
                break
            samples, sample_rate = self._neural.create(segment, voice=voice, speed=speed, lang=lang)
            if not self._active(generation):
                break
            # Playback of one continuous synthesised segment avoids tiny audio
            # chunks and prevents the discontinuities heard with repeated SAPI calls.
            sd.play(samples, samplerate=sample_rate, blocking=True)

    def _speak_sapi(self, text: str, voice: str, speed: float):
        # Initialise COM inside this persistent worker, never on the Qt UI thread.
        if self._sapi is None:
            import pyttsx3
            self._sapi = pyttsx3.init()
            try:
                preferred = ("george", "david") if voice.startswith("bm") else ("hazel", "zira")
                installed = self._sapi.getProperty("voices")
                match = next((v for hint in preferred for v in installed
                              if hint in (v.name + " " + v.id).lower()), None)
                if match:
                    self._sapi.setProperty("voice", match.id)
            except Exception:
                pass
        self._sapi.setProperty("rate", int(185 * speed))
        self._sapi.say(text[:900])
        self._sapi.runAndWait()

    def _work(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_ready = True
        except ImportError:
            com_ready = False
        try:
            while not self.stop_event.is_set():
                try:
                    task = self.pending.get(timeout=0.2)
                except queue.Empty:
                    continue
                if task is None:
                    break
                generation, text = task
                if not self._active(generation):
                    continue
                with self._lock:
                    engine, voice, speed = self.engine, self.voice, self.speed
                try:
                    if engine == "neural":
                        try:
                            self._speak_neural(text, generation, voice, speed)
                        except Exception as exc:
                            if self.on_error and self._active(generation):
                                self.on_error("Neural voice unavailable; using Windows voice. " + type(exc).__name__)
                            if self._active(generation):
                                self._speak_sapi(text, voice, speed)
                    else:
                        self._speak_sapi(text, voice, speed)
                except Exception as exc:
                    if self.on_error and self._active(generation):
                        self.on_error("Speech output unavailable: " + type(exc).__name__)
                finally:
                    if self.on_finished and self._active(generation) and self.pending.empty():
                        self.on_finished()
        finally:
            if com_ready:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def stop(self):
        self.stop_event.set()
        with self._lock:
            self._generation += 1
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
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
