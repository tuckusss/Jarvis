"""JARVIS desktop entrypoint with packaged Windows integration checks."""
from __future__ import annotations
import sys
import os
import tempfile
import traceback


def _write_failure(label: str) -> None:
    """Capture packaged --windowed failures without exposing sensitive arguments."""
    folder = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
    path = os.path.join(folder, "jarvis-" + label + "-error.log")
    try:
        with open(path, "w", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        print("JARVIS_DIAGNOSTIC_LOG=" + path, file=sys.stderr)
    except OSError:
        pass


def package_check() -> int:
    """Check bundled dynamic dependencies without microphone, credentials or GUI display."""
    import jarvis.ui
    import jarvis.voice
    import jarvis.google_connector
    import keyring
    import googleapiclient.discovery
    import google_auth_oauthlib.flow
    import vosk
    import sounddevice
    import pyttsx3
    import kokoro_onnx
    from jarvis.neural_voice import neural_available
    if not neural_available():
        raise RuntimeError("Bundled neural voice model or voice definitions missing")
    from PySide6 import QtWidgets, QtGui, QtCore
    from jarvis.wake_model import packaged_model, is_valid_model
    if not is_valid_model(packaged_model()):
        raise RuntimeError("Bundled Vosk wake-word model missing or invalid")
    from jarvis.local_ai import has_local_bundle
    if not has_local_bundle():
        raise RuntimeError("Bundled local AI model or llama.cpp runtime missing")
    # These imports must work in a PyInstaller bundle on Windows.
    return 0


def offline_inference_check() -> int:
    """Check that the packaged local brain answers, without a cloud API key.

    This is not a microphone or real-user Windows test. It intentionally runs
    only on Windows CI/maintainer machines after PyInstaller packaging.
    """
    from jarvis.local_ai import LocalRuntime, MODEL_ALIAS
    runtime = LocalRuntime(connection_timeout=150)
    try:
        response = runtime.client().chat.completions.create(
            model=MODEL_ALIAS,
            messages=[{"role": "user", "content": "Reply with the word READY."}],
            temperature=0, max_tokens=12, stream=False,
        )
        message = (response.choices[0].message.content or "").strip()
        if not message:
            raise RuntimeError("Packaged local AI returned no content")
        return 0
    finally:
        runtime.stop()


def offline_voice_check() -> int:
    """Synthesize a real offline neural speech sample without audio hardware."""
    from jarvis.neural_voice import synthesize_neural_sample
    audio, rate = synthesize_neural_sample()
    if rate < 16000 or len(audio) < 8000:
        raise RuntimeError("Offline voice generation produced no usable audio")
    return 0


if __name__ == "__main__":
    if "--package-check" in sys.argv:
        try:
            sys.exit(package_check())
        except Exception as exc:
            _write_failure("package")
            print(f"Package check failed: {exc}", file=sys.stderr)
            sys.exit(1)
    if "--offline-voice-check" in sys.argv:
        try:
            sys.exit(offline_voice_check())
        except Exception:
            _write_failure("voice")
            sys.exit(1)
    if "--offline-inference-check" in sys.argv:
        try:
            sys.exit(offline_inference_check())
        except Exception as exc:
            _write_failure("inference")
            print(f"Offline inference check failed: {exc}", file=sys.stderr or sys.__stderr__)
            sys.exit(1)
    from jarvis.ui import run
    run()
