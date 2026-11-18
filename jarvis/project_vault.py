"""Opt-in encrypted notes for named JARVIS projects.

New notes are protected with Windows CurrentUser DPAPI *before* SQLite writes.
Existing legacy chats, reminders, notes, and audit logs are not migrated or
encrypted by this feature. Search decrypts in-memory only after owner approval.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import re
import sqlite3
import threading
from .config import data_dir
from .windows_crypto import WindowsDpapi

MAX_NOTE = 3000
MAX_RESULTS = 20
MAX_SCAN = 500


def project_name(config, name: str) -> str:
    allowed = {"personal": "Personal", "paycore": "PayCore", "freedom homes": "Freedom Homes"}
    folders = getattr(config, "project_folders", {})
    if isinstance(folders, dict):
        for key in folders:
            if isinstance(key, str) and 1 <= len(key) <= 80:
                allowed[key.strip().casefold()] = key.strip()
    choice = str(name).strip().casefold()
    if choice not in allowed:
        raise ValueError("Unknown project; configure its name in JARVIS Settings")
    return allowed[choice]


class ProjectVault:
    def __init__(self, path: Path | None = None, *, protector=None):
        # Construction must fail on non-Windows if no test-only protector was
        # explicitly provided. There is never a plaintext fallback in production.
        self.protector = protector if protector is not None else WindowsDpapi()
        self.path = path or data_dir() / "project_vault.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS project_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                secret BLOB NOT NULL
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS project_notes_scope ON project_notes(project,id)")
        self.db.commit()

    def remember(self, project: str, note: str) -> int:
        project = project.strip()
        note = note.strip()
        if not (1 <= len(project) <= 80) or not re.fullmatch(r"[\w .-]+", project, re.UNICODE):
            raise ValueError("Invalid project label")
        if not (3 <= len(note) <= MAX_NOTE):
            raise ValueError("Project note must be 3 to 3000 characters")
        ciphertext = self.protector.encrypt(note)
        if not isinstance(ciphertext, bytes) or not ciphertext:
            raise RuntimeError("Project encryption failed; note was not saved")
        with self.lock:
            cursor = self.db.execute(
                "INSERT INTO project_notes(project,created_utc,secret) VALUES(?,?,?)",
                (project, datetime.now(timezone.utc).isoformat(), sqlite3.Binary(ciphertext)),
            )
            self.db.commit()
            return int(cursor.lastrowid)

    def search(self, project: str, query: str = "", *, limit: int = 8) -> list[dict]:
        if not (1 <= len(project) <= 80):
            raise ValueError("Project is required")
        if len(query) > 120:
            raise ValueError("Search phrase exceeds 120 characters")
        with self.lock:
            rows = self.db.execute(
                "SELECT id,created_utc,secret FROM project_notes "
                "WHERE project=? ORDER BY id DESC LIMIT ?",
                (project, MAX_SCAN),
            ).fetchall()
            result = []
            for note_id, created, secret in rows:
                # Never catch decryption failure and show a blank/partial result.
                # A profile-key change or corrupted ciphertext must fail closed.
                plain = self.protector.decrypt(bytes(secret))
                if query.casefold() in plain.casefold():
                    result.append({"id": note_id, "created_utc": created,
                                   "project": project, "note": plain[:MAX_NOTE]})
                if len(result) >= max(1, min(limit, MAX_RESULTS)):
                    break
            return result

    def forget(self, project: str, note_id: int) -> bool:
        if type(note_id) is not int or note_id < 1:
            raise ValueError("Note ID must be a positive integer")
        with self.lock:
            cursor = self.db.execute(
                "DELETE FROM project_notes WHERE project=? AND id=?",
                (project, note_id),
            )
            self.db.commit()
            return cursor.rowcount == 1

    def encrypted_backup(self, destination: Path) -> Path:
        """SQLite snapshot containing DPAPI ciphertext, not decrypted notes."""
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError("Refusing to overwrite an existing vault backup")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            with closing(sqlite3.connect(str(destination))) as target:
                self.db.backup(target)
        return destination

    def close(self):
        with self.lock:
            self.db.close()
