from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME")
    path = Path(base) / "JarvisLocal" if base else Path.home() / ".jarvis-local"
    path.mkdir(parents=True, exist_ok=True)
    return path


DEFAULT_SITES = {
    "gmail": "https://mail.google.com/",
    "calendar": "https://calendar.google.com/",
    "google": "https://www.google.com/",
    "chatgpt": "https://chatgpt.com/",
}


@dataclass
class Config:
    provider: str = "local"  # local / hybrid / openai; cloud is never silently enabled
    model: str = "gpt-5.5"
    transcription_model: str = "gpt-transcribe"
    voice_enabled: bool = True
    voice_engine: str = "neural"
    voice_name: str = "bm_george"
    voice_speed: float = 1.0
    wake_enabled: bool = False
    gaming_mode_enabled: bool = True
    crash_restart_enabled: bool = True
    gaming_pause_wake: bool = True
    gaming_mute_speech: bool = True
    microphone_device: int | None = None
    wake_model_path: str = ""  # legacy compatibility; normally auto-discovered
    save_history: bool = True
    private_memory_enabled: bool = False  # explicit owner opt-in; new project notes only
    google_credentials_path: str = ""
    google_write_enabled: bool = False
    sites: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SITES))
    custom_folder: str = ""  # optional extra searchable folder; explicit user opt-in
    project_folders: dict[str, str] = field(default_factory=lambda: {
        "PayCore": str(Path.home() / "Desktop" / "PayCore")
    })  # Paths are local; no code or project files are uploaded automatically.


    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or data_dir() / "config.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            allowed = set(cls.__dataclass_fields__)
            return cls(**{k: v for k, v in data.items() if k in allowed})
        except (ValueError, TypeError, OSError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        path = path or data_dir() / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(path)


def api_key() -> str:
    env = os.getenv("OPENAI_API_KEY", "").strip()
    if env:
        return env
    try:
        import keyring
        return keyring.get_password("JARVIS-Desktop", "openai_api_key") or ""
    except Exception:
        return ""


def save_api_key(value: str) -> None:
    import keyring
    if value.strip():
        keyring.set_password("JARVIS-Desktop", "openai_api_key", value.strip())
    else:
        try:
            keyring.delete_password("JARVIS-Desktop", "openai_api_key")
        except Exception:
            pass
