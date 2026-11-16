"""Owner capabilities cannot be bypassed by an agent's direct tool call."""
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from unittest import TestCase
from unittest.mock import MagicMock

from jarvis.config import Config
from jarvis.memory import Memory
from jarvis.owner_auth import OwnerGate
from jarvis.tools import ToolExecutor


PHRASE = "A deliberately long and distinctive passphrase"


class ExecutorBoundaryTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        folder = Path(self.tmp.name)
        self.memory = Memory(folder / "memory.sqlite")
        self.gate = OwnerGate(folder / "owner.json")
        self.gate.enrol(PHRASE)
        self.exec = ToolExecutor(Config(), self.memory, MagicMock(),
                                 lambda *_: True, lambda: "screen",
                                 owner_gate=self.gate)

    def tearDown(self):
        self.memory.close()
        self.tmp.cleanup()

    def test_direct_tool_without_token_is_denied(self):
        result = self.exec.execute("remember_note", {"note": "Sensitive note"})
        self.assertIn("locked", result["error"])
        self.assertEqual(self.memory.recall(), [])

    def test_verified_typed_command_has_short_scoped_authorisation(self):
        self.assertTrue(self.gate.unlock(PHRASE))
        token = self.gate.issue_command_token()
        self.assertIsNotNone(token)
        with self.exec.authorised_request(token):
            result = self.exec.execute("remember_note", {"note": "Project approved"})
            self.assertTrue(result["saved"])
        self.assertIn("locked", self.exec.execute("recall_notes", {"query": "Project"})["error"])
        self.gate.revoke_command_token(token)
        with self.exec.authorised_request(token):
            self.assertIn("locked", self.exec.execute("list_reminders", {})["error"])

    def test_voice_token_is_one_time_and_does_not_unlock_typed_session(self):
        self.assertTrue(self.gate.unlock(PHRASE, voice_command=True))
        one_time = self.gate.issue_command_token(voice_command=True)
        self.assertTrue(self.gate.check_command_token(one_time))
        self.assertIsNone(self.gate.issue_command_token(voice_command=True))
        self.assertFalse(self.gate.authorised())
        self.gate.lock()
        self.assertFalse(self.gate.check_command_token(one_time))

    def test_capability_not_inherited_by_second_thread(self):
        self.assertTrue(self.gate.unlock(PHRASE))
        token = self.gate.issue_command_token()
        external = []
        with self.exec.authorised_request(token):
            worker = threading.Thread(
                target=lambda: external.append(self.exec.execute("recall_notes", {"query": ""}))
            )
            worker.start()
            worker.join(2)
            self.assertIn("locked", external[0]["error"])

    def test_token_expires_during_stalled_request(self):
        current = [10.0]
        gate = OwnerGate(Path(self.tmp.name) / "other.json", clock=lambda: current[0])
        gate.enrol(PHRASE)
        self.assertTrue(gate.unlock(PHRASE))
        token = gate.issue_command_token()
        self.assertTrue(gate.check_command_token(token))
        current[0] += 181
        self.assertFalse(gate.check_command_token(token))

    def test_without_enrolment_existing_tool_behavior_unchanged(self):
        ungated = ToolExecutor(Config(), self.memory, MagicMock(),
                              lambda *_: True, lambda: "screen",
                              owner_gate=OwnerGate(Path(self.tmp.name) / "new_owner.json"))
        self.assertTrue(ungated.execute("remember_note", {"note": "Normal note"})["saved"])

    def test_revoked_while_approval_dialog_open_cannot_execute(self):
        self.assertTrue(self.gate.unlock(PHRASE))
        token = self.gate.issue_command_token()
        def revoke_while_approving(name, detail):
            self.gate.lock()
            return True
        self.exec.approve = revoke_while_approving
        with self.exec.authorised_request(token):
            result = self.exec.execute("remember_note", {"note": "Must not be saved"})
        self.assertIn("locked", result["error"])
        self.assertEqual(self.memory.recall(), [])
