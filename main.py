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


def private_vault_check() -> int:
    """Exercise real CurrentUser DPAPI using a temporary, disposable database."""
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from jarvis.project_vault import ProjectVault
    with TemporaryDirectory() as directory:
        path = Path(directory) / "test-private-vault.sqlite"
        vault = ProjectVault(path)
        try:
            note_id = vault.remember("PayCore", "CI encrypted memory test: sample")
            notes = vault.search("PayCore", "memory")
            if len(notes) != 1 or notes[0]["id"] != note_id:
                raise RuntimeError("Encrypted memory search did not roundtrip")
            if b"CI encrypted memory test" in path.read_bytes():
                raise RuntimeError("Private memory stored plaintext in SQLite")
            if not vault.forget("PayCore", note_id):
                raise RuntimeError("Private memory deletion did not work")
        finally:
            vault.close()
    return 0


def secure_history_check() -> int:
    """Real Windows DPAPI encryption + opt-in legacy migration in a disposable DB."""
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from jarvis.memory import Memory
    from jarvis.secure_memory import SecureMemory
    from jarvis.legacy_migration import migrate_legacy
    with TemporaryDirectory() as folder:
        root = Path(folder)
        old = Memory(root / "legacy-jarvis.db")
        try:
            old.message("user", "Sensitive JARVIS 1.0 memory check")
            old.remember("Private note requiring legacy migration")
        finally:
            old.close()
        secure = SecureMemory(root / "new-secure-history.db")
        try:
            secure.message("assistant", "New DPAPI record")
            result = migrate_legacy(root / "legacy-jarvis.db", secure, approved=True)
            if result["copied"]["messages"] != 1 or result["copied"]["notes"] != 1:
                raise RuntimeError("Encrypted history migration did not preserve source counts")
            if len(secure.search_messages("Sensitive")) != 1:
                raise RuntimeError("Encrypted history search did not roundtrip")
            if b"Sensitive JARVIS" in secure.path.read_bytes():
                raise RuntimeError("Secure history retained plaintext content")
            if b"Private note requiring" in secure.path.read_bytes():
                raise RuntimeError("Secure notes retained plaintext content")
        finally:
            secure.close()
    return 0


def gui_smoke_check() -> int:
    """Check that the actual bundled Settings dialog opens without a display."""
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    from jarvis.config import Config
    from jarvis.ui import SettingsDialog
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Config())
    if dialog.layout() is None:
        raise RuntimeError("JARVIS Settings failed to initialise")
    dialog.close()
    return 0


if __name__ == "__main__":
    if "--secure-history-check" in sys.argv:
        try:
            sys.exit(secure_history_check())
        except Exception:
            _write_failure("secure-history")
            sys.exit(1)
    if "--private-vault-check" in sys.argv:
        try:
            sys.exit(private_vault_check())
        except Exception:
            _write_failure("private-vault")
            sys.exit(1)
    if "--gui-smoke-check" in sys.argv:
        try:
            sys.exit(gui_smoke_check())
        except Exception:
            _write_failure("gui")
            sys.exit(1)
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
