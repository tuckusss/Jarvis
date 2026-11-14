"""Verified, safely extracted Vosk wake model with zero manual folder selection.

The signed Windows installer includes the model. The source/developer build can
install it on demand into the user's private application data directory.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZipFile

MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MIRROR_URL = f"https://huggingface.co/rhasspy/vosk-models/resolve/main/en/{MODEL_NAME}.zip"
# Independent published checksum of this specific model ZIP (not any arbitrary ZIP).
MODEL_SHA256 = "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"
MAX_ARCHIVE_SIZE = 85 * 1024 * 1024
MAX_EXTRACTED_SIZE = 250 * 1024 * 1024
MAX_FILES = 2000


def is_valid_model(path: Path) -> bool:
    """A minimal layout check. Vosk performs the real model load at runtime."""
    return path.is_dir() and all((path / folder).is_dir() for folder in ("am", "conf", "graph")) and (
        path / "am" / "final.mdl"
    ).is_file()


def packaged_model() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "models" / MODEL_NAME


def installed_model() -> Path:
    from .config import data_dir
    return data_dir() / "models" / MODEL_NAME


def resolve_model(user_path: str = "") -> Path | None:
    candidates = [Path(user_path).expanduser()] if user_path else []
    candidates.extend((packaged_model(), installed_model()))
    return next((p for p in candidates if is_valid_model(p)), None)


def _safe_model_member(name: str) -> Path:
    """Ensure each member lives under the one expected top-level model folder."""
    p = PurePosixPath(name.replace("\\", "/"))
    parts = p.parts
    if (p.is_absolute() or not parts or parts[0] != MODEL_NAME or
            any(item in ("..", "") for item in parts) or ":" in name):
        raise ValueError("Unsafe file path in Vosk archive")
    return Path(*parts[1:]) if len(parts) > 1 else Path(".")


def extract_verified_model(archive: Path, destination: Path, expected_sha256: str = MODEL_SHA256) -> Path:
    """Verify immutable model digest, reject traversal/symlinks/bombs, install atomically."""
    digest = hashlib.sha256()
    with archive.open("rb") as src:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected_sha256.lower():
        raise ValueError("Vosk download failed SHA-256 verification")
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="jarvis-vosk-", dir=destination.parent))
    try:
        with ZipFile(archive) as z:
            infos = z.infolist()
            if len(infos) > MAX_FILES or sum(x.file_size for x in infos) > MAX_EXTRACTED_SIZE:
                raise ValueError("Vosk archive is unexpectedly large")
            for info in infos:
                child = _safe_model_member(info.filename)
                if child == Path("."):
                    continue
                mode = (info.external_attr >> 16)
                if stat.S_ISLNK(mode):
                    raise ValueError("Symlinks not permitted in model ZIP")
                out = scratch / child
                if info.is_dir():
                    out.mkdir(parents=True, exist_ok=True)
                else:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as src, out.open("wb") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
        if not is_valid_model(scratch):
            raise ValueError("Downloaded archive is not a usable Vosk model")
        if destination.exists():
            if is_valid_model(destination):
                return destination
            raise ValueError("An incomplete model exists at the install location; remove it before retrying")
        scratch.rename(destination)
        return destination
    finally:
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)


def install_model(destination: Path | None = None) -> Path:
    """Download once, validate authenticity, install to internal app data or build assets."""
    destination = destination or installed_model()
    if is_valid_model(destination):
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="jarvis-vosk-download-", suffix=".zip", dir=destination.parent)
    os.close(fd)
    archive = Path(name)
    try:
        failures = []
        for url in (MODEL_URL, MIRROR_URL):
            try:
                req = Request(url, headers={"User-Agent": "JARVIS-Desktop-Model-Installer/0.3"})
                with urlopen(req, timeout=60) as src, archive.open("wb") as dst:
                    total = 0
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_ARCHIVE_SIZE:
                            raise ValueError("Vosk download exceeds expected size")
                        dst.write(chunk)
                return extract_verified_model(archive, destination)
            except (OSError, ValueError, EOFError) as exc:
                failures.append(type(exc).__name__)
        raise RuntimeError("Could not download a verified Vosk model from either approved source: " + ", ".join(failures))
    finally:
        archive.unlink(missing_ok=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Install pinned Vosk small English model")
    parser.add_argument("--destination", type=Path, default=None)
    args = parser.parse_args()
    print("Verified Vosk model:", install_model(args.destination))
