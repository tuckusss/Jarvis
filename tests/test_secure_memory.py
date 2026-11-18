"""Secure memory stores *new* messages, notes and reminders as ciphertext."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os

from jarvis.secure_memory import SecureMemory


class TestCipher:
    def encrypt(self, text: str) -> bytes:
        return b"fake-test:" + text[::-1].encode("utf8")
    def decrypt(self, value: bytes) -> str:
        if not value.startswith(b"fake-test:"):
            raise ValueError("Invalid ciphertext")
        return value[10:].decode("utf8")[::-1]


class SecureMemoryTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.path = Path(self.folder.name) / "secure.db"
        self.mem = SecureMemory(self.path, protector=TestCipher())

    def tearDown(self):
        self.mem.close()
        self.folder.cleanup()

    def test_message_roundtrip_without_storing_plaintext(self):
        self.mem.message("user", "PayCore private controller detail")
        self.mem.message("assistant", "Acknowledged privately")
        self.assertEqual(self.mem.recent()[-1]["content"], "Acknowledged privately")
        self.assertIn("controller detail", self.mem.search_messages("controller")[0]["excerpt"])
        data = self.path.read_bytes()
        self.assertNotIn(b"private controller detail", data)
        self.assertNotIn(b"Acknowledged privately", data)

    def test_notes_scope_and_no_wildcard_interpretation(self):
        self.mem.remember("Freedom Homes monthly inspection reminder")
        self.mem.remember("Use 80% split calculation")
        self.assertEqual(self.mem.recall("inspection"), ["Freedom Homes monthly inspection reminder"])
        self.assertEqual(self.mem.recall("80%"), ["Use 80% split calculation"])
        self.assertEqual(self.mem.recall("%x"), [])
        self.assertNotIn(b"monthly inspection", self.path.read_bytes())

    def test_reminders_decrypt_and_due_claim_once(self):
        when = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
        self.mem.add_reminder(when, "Submit PayCore certificate")
        self.assertEqual(len(self.mem.reminders()), 1)
        self.assertEqual(self.mem.reminders()[0]["message"], "Submit PayCore certificate")
        self.assertNotIn(b"Submit PayCore", self.path.read_bytes())
        from datetime import datetime as RealDatetime
        class Later(RealDatetime):
            @classmethod
            def now(cls, tz=None):
                return RealDatetime.now(tz) + timedelta(minutes=1)
        with patch("jarvis.secure_memory.datetime", Later):
            self.assertEqual(len(self.mem.due_reminders()), 1)
            self.assertEqual(self.mem.due_reminders(), [])

    def test_corrupt_ciphertext_never_displays_plaintext(self):
        self.mem.message("user", "private")
        self.mem.db.execute("UPDATE messages SET content=?", ("unencrypted",))
        self.mem.db.commit()
        with self.assertRaises(ValueError):
            self.mem.recent()

    def test_encryption_failure_does_not_write(self):
        class Broken:
            def encrypt(self, text):
                raise RuntimeError("Unable to encrypt")
        self.mem.protector = Broken()
        with self.assertRaises(RuntimeError):
            self.mem.message("user", "Sensitive details")
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM messages").fetchone()[0], 0)

    def test_real_windows_dpapi(self):
        if os.name != "nt":
            self.skipTest("Windows only")
        other = SecureMemory(Path(self.folder.name) / "windows.db")
        try:
            other.message("user", "DPAPI test from actual user profile")
            self.assertEqual(other.recent()[0]["content"], "DPAPI test from actual user profile")
            self.assertNotIn(b"actual user profile", other.path.read_bytes())
        finally:
            other.close()

    def test_fail_closed_outside_windows(self):
        if os.name == "nt":
            self.skipTest("Outside Windows only")
        with self.assertRaises(OSError):
            SecureMemory(Path(self.folder.name) / "unsupported.db")
