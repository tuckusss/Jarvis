"""Backup tests: encrypted snapshots must capture WAL writes and never overwrite."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import os
import sqlite3

from jarvis.memory import Memory
from jarvis.secure_memory import SecureMemory
from jarvis.secure_backup import create_secure_backup, verify_secure_backup


class TestProtector:
    def encrypt(self, content: str) -> bytes:
        return b"test-only:" + content.encode("utf-8")[::-1]
    def decrypt(self, content: bytes) -> str:
        if not content.startswith(b"test-only:"):
            raise ValueError("Cannot decrypt")
        return content[len(b"test-only:"):][::-1].decode("utf-8")


class EncryptedBackupTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.memory = SecureMemory(self.root / "active.sqlite",
                                   protector=TestProtector())
        self.backup = self.root / "recovery.sqlite"

    def tearDown(self):
        self.memory.close()
        self.tmp.cleanup()

    def test_live_wal_snapshot_and_read_only_verification(self):
        self.memory.message("user", "Confidential controller prototype milestone")
        self.memory.remember("Freedom Homes private inspection ledger")
        result = create_secure_backup(self.memory, self.backup)
        self.assertEqual(result["records"]["messages"], 1)
        self.assertEqual(result["records"]["notes"], 1)
        self.assertFalse(result["portable"])
        self.assertEqual(len(result["sha256"]), 64)
        self.assertNotIn(b"Confidential controller", self.backup.read_bytes())
        verified = verify_secure_backup(self.backup, protector=TestProtector())
        self.assertEqual(result["sha256"], verified["sha256"])
        self.assertEqual(result["records"], verified["records"])
        with closing(sqlite3.connect(str(self.backup))) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM messages").fetchone()[0], 1)

    def test_backups_never_overwrite(self):
        self.memory.message("assistant", "Keep existing recovery copy")
        create_secure_backup(self.memory, self.backup)
        previous = self.backup.read_bytes()
        self.memory.message("user", "Newer event in live database")
        with self.assertRaises(FileExistsError):
            create_secure_backup(self.memory, self.backup)
        self.assertEqual(self.backup.read_bytes(), previous)

    def test_plaintext_or_corrupt_record_fails_closed(self):
        self.memory.message("user", "Encrypted message")
        self.memory.db.execute("UPDATE messages SET content='not encrypted'")
        self.memory.db.commit()
        with self.assertRaises(ValueError):
            create_secure_backup(self.memory, self.backup)
        self.assertFalse(self.backup.exists())

    def test_verify_invalid_backup_does_not_mutate_it(self):
        self.backup.write_bytes(b"invalid or damaged sqlite")
        old = self.backup.read_bytes()
        with self.assertRaises(sqlite3.DatabaseError):
            verify_secure_backup(self.backup, protector=TestProtector())
        self.assertEqual(self.backup.read_bytes(), old)

    def test_wrong_profile_or_key_rejected(self):
        self.memory.message("user", "Secret")
        create_secure_backup(self.memory, self.backup)
        class WrongProtector:
            def decrypt(self, secret):
                raise OSError("This Windows account cannot decrypt that note")
        with self.assertRaises(OSError):
            verify_secure_backup(self.backup, protector=WrongProtector())

    def test_refuse_plaintext_mode_and_in_place_backup(self):
        with self.assertRaises(ValueError):
            create_secure_backup(self.memory, self.memory.path)
        legacy = Memory(self.root / "plain.sqlite")
        try:
            with self.assertRaises(TypeError):
                create_secure_backup(legacy, self.backup)
        finally:
            legacy.close()

    def test_real_windows_profile_recovery(self):
        if os.name != "nt":
            self.skipTest("CurrentUser DPAPI requires Windows")
        real = SecureMemory(self.root / "real.sqlite")
        try:
            real.message("user", "Windows profile private backup check")
            output = self.root / "real-recovery.sqlite"
            backup = create_secure_backup(real, output)
            self.assertEqual(
                verify_secure_backup(output)["sha256"], backup["sha256"]
            )
        finally:
            real.close()
