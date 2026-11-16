"""User-configured, strictly read-only local business/project workspaces."""
from __future__ import annotations

from pathlib import Path

STATUS_FILE = "JARVIS_STATUS.md"
MAX_STATUS_BYTES = 32_000


def project_root(config, name: str) -> Path:
    projects = getattr(config, "project_folders", {})
    if not isinstance(projects, dict):
        raise ValueError("Project folders must be configured in Settings")
    key = next((k for k in projects if isinstance(k, str)
                and k.casefold() == name.strip().casefold()), None)
    if key is None:
        raise KeyError("Unknown project; configure its folder in Settings")
    folder = Path(projects[key]).expanduser()
    if not folder.is_absolute() or not folder.is_dir():
        raise FileNotFoundError("Project folder is missing; choose an existing folder in Settings")
    return folder.resolve()


def read_project_status(config, name: str) -> dict:
    root = project_root(config, name)
    target = root / STATUS_FILE
    if not target.is_file() or target.is_symlink() or target.resolve().parent != root:
        raise FileNotFoundError(
            "No JARVIS_STATUS.md found in the configured project folder"
        )
    if target.stat().st_size > MAX_STATUS_BYTES:
        raise ValueError("Project summary exceeds 32 KB limit")
    return {
        "project": name,
        "source": STATUS_FILE,
        "content": target.read_text(encoding="utf-8", errors="replace")[:MAX_STATUS_BYTES],
        "live": False,
    }
