"""Local owner confirmation for JARVIS actions.

This is a passphrase gate inside JARVIS, NOT speaker biometrics or Windows
authentication. A Windows session or administrator remains the OS security
boundary. Voice commands must re-verify because unknown speakers can talk
while the owner has left the keyboard.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time

from .config import data_dir

KDF_ITERATIONS = 390_000
MIN_LENGTH = 12
SESSION_SECONDS = 300


class OwnerGate:
    def __init__(self, path: Path | None = None, clock=None):
        self.path = path or data_dir() / "owner_gate.json"
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._unlocked_until = 0.0
        self._failures = 0
        self._blocked_until = 0.0

    @property
    def enrolled(self) -> bool:
        return self.path.is_file()

    def _record(self) -> dict:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if (data.get("version") != 1 or data.get("algorithm") != "pbkdf2-sha256" or
                not isinstance(data.get("salt"), str) or not isinstance(data.get("hash"), str)):
            raise ValueError("Owner access record is invalid; do not bypass this lock")
        return data

    def enrol(self, passphrase: str) -> None:
        """Enrollment requires consent in the authenticated local Windows session."""
        if len(passphrase) < MIN_LENGTH or passphrase.isspace():
            raise ValueError("Use a passphrase of at least 12 characters")
        with self._lock:
            if self.enrolled:
                raise PermissionError("Owner lock already exists; unlock before changing it")
            salt = secrets.token_bytes(16)
            digest = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"),
                                        salt, KDF_ITERATIONS)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "version": 1, "algorithm": "pbkdf2-sha256",
                "iterations": KDF_ITERATIONS,
                "salt": salt.hex(), "hash": digest.hex(),
            }
            # Owner access data is private to the Windows profile. Windows
            # admin / other same-user code can still tamper with user files.
            fd, name = tempfile.mkstemp(prefix=".owner-", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as out:
                    json.dump(record, out, sort_keys=True)
                try:
                    os.chmod(name, 0o600)
                except OSError:
                    pass
                os.replace(name, self.path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            self._unlocked_until = 0

    def unlock(self, passphrase: str, *, voice_command: bool = False) -> bool:
        """Every voice command asks again; typed commands use a short session."""
        with self._lock:
            if not self.enrolled:
                return True
            if self._clock() < self._blocked_until:
                return False
            try:
                record = self._record()
                iteration = int(record["iterations"])
                if iteration < KDF_ITERATIONS or iteration > 1_000_000:
                    return False
                expected = bytes.fromhex(record["hash"])
                derived = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"),
                                              bytes.fromhex(record["salt"]), iteration)
                valid = secrets.compare_digest(expected, derived)
            except (OSError, ValueError, KeyError, TypeError):
                return False
            if not valid:
                self._failures += 1
                if self._failures >= 5:
                    self._blocked_until = self._clock() + min(300, 2 ** min(self._failures, 8))
                return False
            self._failures = 0
            self._blocked_until = 0
            self._unlocked_until = 0 if voice_command else self._clock() + SESSION_SECONDS
            return True

    def authorised(self, *, voice_command: bool = False) -> bool:
        with self._lock:
            return (not self.enrolled or
                    (not voice_command and self._clock() < self._unlocked_until))

    def lock(self) -> None:
        with self._lock:
            self._unlocked_until = 0.0

    def disable(self) -> None:
        with self._lock:
            if self.enrolled and not self.authorised():
                raise PermissionError("Unlock as owner before disabling JARVIS access")
            if self.enrolled:
                self.path.unlink()
            self.lock()
