"""Safe, user-scoped backup and verification of DPAPI encrypted JARVIS history.

SQLite's online backup API includes WAL-backed records in one consistent
snapshot. Backups are created with exclusive destination creation and are
validated before being accepted. This module DOES NOT overwrite any live
database or promise portable decryption: Windows CurrentUser DPAPI is tied to
the original Windows profile, normally on the same computer.
"""
from __future__ import annotations

import base64
from contextlib import closing
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import tempfile

from .secure_memory import PREFIX, SecureMemory
from .windows_crypto import WindowsDpapi

_MAX_RECORDS_PER_TABLE = 100_000
_TABLE_FIELDS = {"messages": "content", "notes": "note", "reminders": "message"}


def _read_only_db(path: Path):
    """Open the selected backup read-only; never change its SQLite schema."""
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def verify_secure_backup(path: Path, *, protector=None) -> dict:
    """Verify SQLite integrity and decryptability, but never return its content.

    It verifies CURRENT PROFILE recovery, not trust/origin. An attacker running
    as the current Windows user may access DPAPI-protected data too.
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError("Encrypted history backup not found")
    if path.stat().st_size > 2_147_483_648:
        raise ValueError("Encrypted history backup is above the 2 GiB safety limit")
    cipher = protector if protector is not None else WindowsDpapi()
    counts = {}
    with closing(_read_only_db(path)) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Backup SQLite integrity check failed")
        for table, column in _TABLE_FIELDS.items():
            found = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if not found:
                raise ValueError("Missing encrypted history table: " + table)
            count = int(db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0])
            if count > _MAX_RECORDS_PER_TABLE:
                raise ValueError("Backup exceeds verified record limit")
            counts[table] = count
            for (encrypted,) in db.execute("SELECT " + column + " FROM " + table):
                if not isinstance(encrypted, str) or not encrypted.startswith(PREFIX):
                    raise ValueError("Backup contains an unencrypted history record")
                raw = base64.b64decode(encrypted[len(PREFIX):], validate=True)
                if not raw or not isinstance(cipher.decrypt(raw), str):
                    raise ValueError("Backup cannot be decrypted by the current Windows profile")
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "file": str(path),
        "sha256": digest.hexdigest(),
        "records": counts,
        "verified_for_current_windows_profile": True,
        "portable": False,
    }


def create_secure_backup(memory: SecureMemory, destination: Path) -> dict:
    """Snapshot the active vault without modifying it; refuse overwrites.

    The final filename is reserved using O_EXCL. An interrupted copy may leave
    an incomplete destination; re-run verification before treating it as a
    backup. The original live memory is never touched.
    """
    if not isinstance(memory, SecureMemory):
        raise TypeError("Backups require encrypted history to be active")
    destination = Path(destination).expanduser().resolve()
    if destination.suffix.lower() != ".sqlite":
        raise ValueError("Use a .sqlite filename for an encrypted history backup")
    if destination == memory.path.resolve():
        raise ValueError("Cannot back up over the live secure history database")
    if destination.exists():
        raise FileExistsError("Backup already exists; choose a new filename")
    if not destination.parent.is_dir():
        raise FileNotFoundError("Backup folder does not exist")
    tmp_path = None
    created_final = False
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".jarvis-encrypted-backup-", suffix=".sqlite",
            dir=str(destination.parent), delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
        with closing(sqlite3.connect(str(tmp_path))) as target:
            with memory.lock:
                memory.db.backup(target)
        # Validate ciphertext BEFORE writing a user-visible backup filename.
        verify_secure_backup(tmp_path, protector=memory.protector)
        fd = os.open(str(destination), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        created_final = True
        with os.fdopen(fd, "wb") as out, tmp_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        return verify_secure_backup(destination, protector=memory.protector)
    except BaseException:
        if created_final:
            destination.unlink(missing_ok=True)
        raise
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
