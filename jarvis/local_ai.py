"""Private, bundled llama.cpp server for CPU-only offline inference.

The release installer ships llama-server.exe and an Apache-2.0 GGUF model.
The server listens only on 127.0.0.1, uses a random bearer token and runs
as a child of the desktop application. It never exposes a LAN endpoint.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_ALIAS = "jarvis-local"


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def runner_path() -> Path:
    return bundle_root() / "local_runtime" / "llama-server.exe"


def model_path() -> Path:
    return bundle_root() / "models" / MODEL_FILENAME


def has_local_bundle() -> bool:
    runner, model = runner_path(), model_path()
    return runner.is_file() and model.is_file() and model.stat().st_size > 500_000_000


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LocalRuntime:
    """Starts once on first local request; stops when JARVIS exits."""

    def __init__(self, popen=None, connection_timeout=120):
        self.proc = None
        self._popen = popen or subprocess.Popen
        self.timeout = connection_timeout
        self.gaming_mode_enabled = True
        self._lock = threading.RLock()
        self._token = ""
        self._port = 0
        self._client = None

    def available(self) -> bool:
        return has_local_bundle()

    def _healthy(self) -> bool:
        if not self._port or not self._token or not self.proc or self.proc.poll() is not None:
            return False
        req = Request(
            f"http://127.0.0.1:{self._port}/v1/models",
            headers={"Authorization": "Bearer " + self._token},
        )
        try:
            with urlopen(req, timeout=2) as res:
                return res.status == 200
        except (HTTPError, URLError, TimeoutError, OSError):
            return False

    def client(self):
        with self._lock:
            if self._client is not None and self._healthy():
                return self._client
            self.stop()
            if not has_local_bundle():
                raise RuntimeError(
                    "Local AI files are missing. Install the complete JARVIS Setup EXE "
                    "(the source-code ZIP does not contain the 1.1 GB AI model)."
                )
            self._port = _free_port()
            self._token = secrets.token_urlsafe(32)
            from .gaming import installed_game_running, select_inference_threads
            cpus = os.cpu_count() or 4
            gaming = self.gaming_mode_enabled and installed_game_running().active
            args = [
                str(runner_path()), "--model", str(model_path()),
                "--alias", MODEL_ALIAS, "--host", "127.0.0.1", "--port", str(self._port),
                "--ctx-size", "4096", "--threads", str(select_inference_threads(cpus, gaming=gaming)),
                "--n-gpu-layers", "0", "--no-webui", "--api-key", self._token,
            ]
            kwargs = {"cwd": str(runner_path().parent), "stdin": subprocess.DEVNULL,
                      "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                      "shell": False}
            if os.name == "nt":
                kwargs["creationflags"] = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                           | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
            self.proc = self._popen(args, **kwargs)
            until = time.monotonic() + self.timeout
            while time.monotonic() < until:
                if self.proc.poll() is not None:
                    self.stop()
                    raise RuntimeError("Local AI process exited during startup. Verify CPU compatibility.")
                if self._healthy():
                    from openai import OpenAI
                    self._client = OpenAI(
                        base_url=f"http://127.0.0.1:{self._port}/v1",
                        api_key=self._token, timeout=150.0, max_retries=0,
                    )
                    return self._client
                time.sleep(0.45)
            self.stop()
            raise RuntimeError("Local AI startup timed out. This PC may need more free memory.")

    def stop(self):
        with self._lock:
            if self._client is not None:
                try:
                    self._client.close()
                except Exception:
                    pass
            self._client = None
            if self.proc is not None:
                if self.proc.poll() is None:
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                self.proc = None
            self._token = ""
            self._port = 0
