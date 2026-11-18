"""One-time, opt-in copy of legacy plaintext JARVIS records into DPAPI storage.

Never edits, renames or deletes legacy jarvis.db. Backups may also contain
plaintext. The caller must clearly disclose that at-rest legacy data remains.
Migration runs under a single transaction in the encrypted destination.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3
from .request_control import check_cancelled
from .secure_memory import SecureMemory

SOURCE_ID = "legacy-jarvis-db-v1"
CAP_PER_TABLE = 100_000


def preview_legacy(path: Path) -> dict:
    path = Path(path).resolve()
    if not path.is_file():
        return {"available": False, "messages": 0, "notes": 0, "reminders": 0}
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
        source.execute("PRAGMA query_only=ON")
        sizes = {}
        for table in ("messages", "notes", "reminders"):
            n = int(source.execute("SELECT count(*) FROM " + table).fetchone()[0])
            if n > CAP_PER_TABLE:
                raise ValueError("Legacy memory too large for unattended migration")
            sizes[table] = n
        return {"available": True, **sizes}


def migrate_legacy(legacy_path: Path, destination: SecureMemory, *,
                   approved: bool = False, cancel_event=None) -> dict:
    if not approved:
        raise PermissionError("Owner approval required for legacy memory migration")
    source_path = Path(legacy_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError("Legacy memory database not found")
    if source_path == destination.path.resolve():
        raise ValueError("Source and destination must be separate databases")
    counts = preview_legacy(source_path)
    with closing(sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)) as source:
        source.execute("PRAGMA query_only=ON")
        source.execute("BEGIN")  # Stable view during the encrypted copy.
        with destination.lock:
            destination.db.execute("""
                CREATE TABLE IF NOT EXISTS legacy_migrations (
                    source TEXT PRIMARY KEY, migrated_utc TEXT NOT NULL
                )
            """)
            if destination.db.execute(
                "SELECT 1 FROM legacy_migrations WHERE source=?", (SOURCE_ID,)
            ).fetchone():
                raise FileExistsError("Legacy data was already copied into this encrypted vault")
            check_cancelled(cancel_event)
            try:
                destination.db.execute("BEGIN IMMEDIATE")
                for role, created, plain in source.execute(
                    "SELECT role,created_at,content FROM messages ORDER BY id"
                ):
                    check_cancelled(cancel_event)
                    destination.db.execute(
                        "INSERT INTO messages(created_at,role,content) VALUES(?,?,?)",
                        (created, role, destination._protect(plain)),
                    )
                for created, plain in source.execute(
                    "SELECT created_at,note FROM notes ORDER BY id"
                ):
                    check_cancelled(cancel_event)
                    destination.db.execute(
                        "INSERT INTO notes(created_at,note) VALUES(?,?)",
                        (created, destination._protect(plain)),
                    )
                for due, plain, fired in source.execute(
                    "SELECT due_utc,message,fired FROM reminders ORDER BY id"
                ):
                    check_cancelled(cancel_event)
                    destination.db.execute(
                        "INSERT INTO reminders(due_utc,message,fired) VALUES(?,?,?)",
                        (due, destination._protect(plain), fired),
                    )
                check_cancelled(cancel_event)
                destination.db.execute(
                    "INSERT INTO legacy_migrations(source,migrated_utc) VALUES(?,?)",
                    (SOURCE_ID, datetime.now(timezone.utc).isoformat()),
                )
                destination.db.commit()
            except BaseException:
                destination.db.rollback()
                raise
    return {
        "copied": {"messages": counts["messages"], "notes": counts["notes"],
                   "reminders": counts["reminders"]},
        "legacy_plaintext_retained": True,
        "warning": "Original jarvis.db and external backups may still contain plaintext.",
    }
