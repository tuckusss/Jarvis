from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from jarvis.owner_auth import OwnerGate


class OwnerGateTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.moment = 100.0
        self.path = Path(self.temp.name) / "gate.json"
        self.gate = OwnerGate(self.path, clock=lambda: self.moment)

    def tearDown(self):
        self.temp.cleanup()

    def test_passphrase_minimum_and_no_plaintext(self):
        with self.assertRaises(ValueError):
            self.gate.enrol("123")
        self.gate.enrol("A distinctive secure passphrase")
        self.assertTrue(self.gate.enrolled)
        self.assertNotIn("distinctive secure", self.path.read_text().lower())

    def test_unverified_commands_blocked(self):
        self.gate.enrol("A distinctive secure passphrase")
        self.assertFalse(self.gate.authorised())
        self.assertFalse(self.gate.unlock("wrong"))
        self.assertFalse(self.gate.authorised())
        self.assertTrue(self.gate.unlock("A distinctive secure passphrase"))
        self.assertTrue(self.gate.authorised())

    def test_voice_requires_reverification_even_when_typed_unlocked(self):
        self.gate.enrol("A distinctive secure passphrase")
        self.gate.unlock("A distinctive secure passphrase")
        self.assertFalse(self.gate.authorised(voice_command=True))
        self.assertTrue(self.gate.unlock("A distinctive secure passphrase", voice_command=True))
        self.assertFalse(self.gate.authorised())

    def test_session_expires_and_manual_lock(self):
        self.gate.enrol("A distinctive secure passphrase")
        self.gate.unlock("A distinctive secure passphrase")
        self.moment += 301
        self.assertFalse(self.gate.authorised())
        self.gate.unlock("A distinctive secure passphrase")
        self.gate.lock()
        self.assertFalse(self.gate.authorised())

    def test_lockout_after_bad_attempts(self):
        self.gate.enrol("A distinctive secure passphrase")
        for _ in range(6):
            self.assertFalse(self.gate.unlock("wrong"))
        self.assertFalse(self.gate.unlock("A distinctive secure passphrase"))
        self.moment += 305
        self.assertTrue(self.gate.unlock("A distinctive secure passphrase"))

    def test_cannot_reenrol_without_owner(self):
        self.gate.enrol("A distinctive secure passphrase")
        with self.assertRaises(PermissionError):
            self.gate.enrol("Another distinctive passphrase")
        with self.assertRaises(PermissionError):
            self.gate.disable()
        self.gate.unlock("A distinctive secure passphrase")
        self.gate.disable()
        self.assertFalse(self.gate.enrolled)
