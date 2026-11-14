from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from .config import data_dir


class Memory:
    """Local persistence; memory additions are explicitly requested, not auto-extracted."""

    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "jarvis.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                note TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                due_utc TEXT NOT NULL,
                message TEXT NOT NULL,
                fired INTEGER NOT NULL DEFAULT 0
            );
        """)
        self.db.commit()

    def message(self, role: str, content: str) -> None:
        if role not in ("user", "assistant"):
            raise ValueError("Invalid role")
        with self.lock:
            self.db.execute("INSERT INTO messages(created_at,role,content) VALUES(?,?,?)",
                            (datetime.now(timezone.utc).isoformat(), role, content[:30000]))
            self.db.commit()

    def recent(self, limit: int = 12) -> list[dict[str, str]]:
        with self.lock:
            rows = self.db.execute("SELECT role,content FROM messages ORDER BY id DESC LIMIT ?",
                                   (min(max(limit, 1), 40),)).fetchall()
            return [{"role": r, "content": c} for r, c in reversed(rows)]

    def remember(self, note: str) -> None:
        if not (3 <= len(note.strip()) <= 1500):
            raise ValueError("Note must be 3 to 1500 characters")
        with self.lock:
            self.db.execute("INSERT INTO notes(created_at,note) VALUES(?,?)",
                            (datetime.now(timezone.utc).isoformat(), note.strip()))
            self.db.commit()

    def recall(self, query: str = "", limit: int = 12) -> list[str]:
        with self.lock:
            if query.strip():
                # Treat search terms as data, never SQL.
                rows = self.db.execute(
                    "SELECT note FROM notes WHERE note LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT ?",
                    ("%" + query.strip()[:120].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%", min(limit, 25)),
                ).fetchall()
            else:
                rows = self.db.execute("SELECT note FROM notes ORDER BY id DESC LIMIT ?", (min(limit,25),)).fetchall()
            return [row[0] for row in rows]

    def add_reminder(self, due_at: str, message: str) -> int:
        due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        if due.tzinfo is None:
            raise ValueError("Reminders need an ISO timestamp with timezone offset")
        if not (3 <= len(message.strip()) <= 500):
            raise ValueError("Reminder needs a short message")
        utc = due.astimezone(timezone.utc)
        if utc <= datetime.now(timezone.utc):
            raise ValueError("Reminder must be scheduled in the future")
        with self.lock:
            cursor = self.db.execute("INSERT INTO reminders(due_utc,message) VALUES(?,?)", (utc.isoformat(), message.strip()))
            self.db.commit()
            return cursor.lastrowid

    def reminders(self, limit=20) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT id,due_utc,message FROM reminders WHERE fired=0 ORDER BY due_utc LIMIT ?", (min(limit, 50),)).fetchall()
            return [{"id": i, "due_utc": d, "message": m} for i, d, m in rows]

    def due_reminders(self) -> list[dict]:
        """Atomically claim due reminders so each is surfaced only once per process or restart."""
        with self.lock:
            rows = self.db.execute("SELECT id,due_utc,message FROM reminders WHERE fired=0 AND due_utc<=? ORDER BY due_utc LIMIT 20",
                                   (datetime.now(timezone.utc).isoformat(),)).fetchall()
            if rows:
                self.db.executemany("UPDATE reminders SET fired=1 WHERE id=? AND fired=0", [(r[0],) for r in rows])
                self.db.commit()
            return [{"id": i, "due_utc": d, "message": m} for i, d, m in rows]

    def clear_history(self) -> None:
        with self.lock:
            self.db.execute("DELETE FROM messages")
            self.db.commit()

    def clear_notes(self) -> None:
        with self.lock:
            self.db.execute("DELETE FROM notes")
            self.db.commit()

    def close(self) -> None:
        with self.lock:
            self.db.close()
