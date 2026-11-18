"""Opt-in Windows DPAPI encryption for NEW JARVIS chat, notes and reminders.

This is intentionally a separate SQLite database from legacy jarvis.db.
Existing plaintext records are not silently migrated, overwritten or erased.
SQLite metadata (role/time/due date/fired state) remains visible. DPAPI does
not defend against malware already executing as the Windows user.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import base64
import sqlite3
from .config import data_dir
from .memory import Memory
from .windows_crypto import WindowsDpapi

PREFIX = "DPAPI1:"
MAX_SCAN = 10000


class SecureMemory(Memory):
    def __init__(self, path: Path | None = None, *, protector=None):
        # Fail closed on unsupported OS or absent Windows user key.
        self.protector = protector if protector is not None else WindowsDpapi()
        super().__init__(path or data_dir() / "jarvis_secure.db")

    def _protect(self, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("Only text can be stored in secure memory")
        blob = self.protector.encrypt(value)
        if not isinstance(blob, bytes) or not blob:
            raise RuntimeError("Secure memory encryption returned no ciphertext")
        return PREFIX + base64.b64encode(blob).decode("ascii")

    def _read(self, value: str) -> str:
        if not isinstance(value, str) or not value.startswith(PREFIX):
            raise ValueError("Invalid secure memory record; no plaintext fallback")
        return self.protector.decrypt(base64.b64decode(value[len(PREFIX):], validate=True))

    def message(self, role: str, content: str) -> None:
        if role not in ("user", "assistant"):
            raise ValueError("Invalid role")
        encrypted = self._protect(content[:30000])
        with self.lock:
            self.db.execute("INSERT INTO messages(created_at,role,content) VALUES(?,?,?)",
                            (datetime.now(timezone.utc).isoformat(), role, encrypted))
            self.db.commit()

    def recent(self, limit: int = 12) -> list[dict[str, str]]:
        with self.lock:
            rows = self.db.execute("SELECT role,content FROM messages ORDER BY id DESC LIMIT ?",
                                   (min(max(1, limit), 40),)).fetchall()
            return [{"role": role, "content": self._read(content)}
                    for role, content in reversed(rows)]

    def remember(self, note: str) -> None:
        if not 3 <= len(note.strip()) <= 1500:
            raise ValueError("Note must be 3 to 1500 characters")
        encrypted = self._protect(note.strip())
        with self.lock:
            self.db.execute("INSERT INTO notes(created_at,note) VALUES(?,?)",
                            (datetime.now(timezone.utc).isoformat(), encrypted))
            self.db.commit()

    def recall(self, query: str = "", limit: int = 12) -> list[str]:
        if len(query) > 120:
            raise ValueError("Search query is too long")
        with self.lock:
            rows = self.db.execute("SELECT note FROM notes ORDER BY id DESC LIMIT ?",
                                   (MAX_SCAN,)).fetchall()
            result = []
            for (secret,) in rows:
                plain = self._read(secret)
                if query.casefold() in plain.casefold():
                    result.append(plain)
                if len(result) >= min(max(1, limit), 25):
                    break
            return result

    def search_messages(self, query: str, limit: int = 8) -> list[dict]:
        query = query.strip()
        if not 2 <= len(query) <= 120:
            raise ValueError("Memory search needs 2-120 characters")
        with self.lock:
            rows = self.db.execute(
                "SELECT role,created_at,content FROM messages ORDER BY id DESC LIMIT ?",
                (MAX_SCAN,)
            ).fetchall()
            result = []
            for role, when, secret in rows:
                plain = self._read(secret)
                if query.casefold() in plain.casefold():
                    result.append({"role": role, "at": when, "excerpt": plain[:800]})
                if len(result) >= min(max(1, limit), 20):
                    break
            return result

    def add_reminder(self, due_at: str, message: str) -> int:
        due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        if due.tzinfo is None or due.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("Reminder must be in the future and timezone-aware")
        if not 3 <= len(message.strip()) <= 500:
            raise ValueError("Reminder needs a short message")
        encrypted = self._protect(message.strip())
        with self.lock:
            cursor = self.db.execute(
                "INSERT INTO reminders(due_utc,message) VALUES(?,?)",
                (due.astimezone(timezone.utc).isoformat(), encrypted),
            )
            self.db.commit()
            return int(cursor.lastrowid)

    def reminders(self, limit=20) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id,due_utc,message FROM reminders WHERE fired=0 ORDER BY due_utc LIMIT ?",
                (min(max(1, limit), 50),),
            ).fetchall()
            return [{"id": i, "due_utc": d, "message": self._read(m)}
                    for i, d, m in rows]

    def due_reminders(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id,due_utc,message FROM reminders "
                "WHERE fired=0 AND due_utc<=? ORDER BY due_utc LIMIT 20",
                (datetime.now(timezone.utc).isoformat(),),
            ).fetchall()
            # If Windows DPAPI becomes unavailable, do not consume reminders.
            payload = [{"id": i, "due_utc": d, "message": self._read(m)}
                       for i, d, m in rows]
            if rows:
                self.db.executemany("UPDATE reminders SET fired=1 WHERE id=? AND fired=0",
                                    [(i,) for i, _, _ in rows])
                self.db.commit()
            return payload
