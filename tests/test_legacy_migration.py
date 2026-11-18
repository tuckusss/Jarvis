from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase

from jarvis.legacy_migration import migrate_legacy, preview_legacy
from jarvis.memory import Memory
from jarvis.request_control import RequestCancelled
from jarvis.secure_memory import SecureMemory


class FakeCipher:
    def encrypt(self, value: str) -> bytes:
        return b"encrypted:" + value[::-1].encode("utf8")
    def decrypt(self, value: bytes) -> str:
        if not value.startswith(b"encrypted:"):
            raise ValueError("Corrupted encrypted content")
        return value[len(b"encrypted:"):].decode("utf8")[::-1]


class LegacyMigrationTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        root = Path(self.folder.name)
        self.legacy = Memory(root / "jarvis.db")
        self.secure = SecureMemory(root / "jarvis_secure.db", protector=FakeCipher())

    def tearDown(self):
        self.legacy.close()
        self.secure.close()
        self.folder.cleanup()

    def test_owner_approval_required(self):
        self.legacy.message("user", "Private old question")
        with self.assertRaises(PermissionError):
            migrate_legacy(self.legacy.path, self.secure)
        self.assertEqual(self.secure.recent(), [])

    def test_migrate_preserves_records_but_leaves_legacy_plaintext(self):
        self.legacy.message("user", "Project controller revision notes")
        self.legacy.message("assistant", "Controller remains offline")
        self.legacy.remember("Freedom Homes weekly maintenance")
        before = preview_legacy(self.legacy.path)
        result = migrate_legacy(self.legacy.path, self.secure, approved=True)
        self.assertEqual(before["messages"], 2)
        self.assertEqual(result["copied"]["messages"], 2)
        self.assertTrue(result["legacy_plaintext_retained"])
        self.assertEqual(self.secure.recent()[0]["content"], "Project controller revision notes")
        self.assertEqual(self.secure.recall("maintenance"), ["Freedom Homes weekly maintenance"])
        self.assertNotIn(b"Project controller revision", self.secure.path.read_bytes())
        self.assertEqual(self.legacy.recent()[0]["content"], "Project controller revision notes")

    def test_cannot_copy_legacy_twice(self):
        self.legacy.message("user", "One-time source")
        migrate_legacy(self.legacy.path, self.secure, approved=True)
        with self.assertRaises(FileExistsError):
            migrate_legacy(self.legacy.path, self.secure, approved=True)

    def test_cancelled_migration_rolls_back(self):
        self.legacy.message("user", "One secret record")
        cancelled = Event()
        cancelled.set()
        with self.assertRaises(RequestCancelled):
            migrate_legacy(self.legacy.path, self.secure, approved=True,
                           cancel_event=cancelled)
        self.assertEqual(self.secure.recent(), [])
        self.assertEqual(
            self.secure.db.execute("SELECT count(*) FROM messages").fetchone()[0], 0
        )

    def test_invalid_source_fails_without_writing(self):
        with self.assertRaises(FileNotFoundError):
            migrate_legacy(Path(self.folder.name) / "missing.db",
                           self.secure, approved=True)
        self.assertEqual(self.secure.recent(), [])
