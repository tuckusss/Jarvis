"""Private tools are owner-approved and never silently use plain history."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock
from jarvis.agent import Agent
from jarvis.config import Config
from jarvis.memory import Memory
from jarvis.project_vault import ProjectVault
from jarvis.tools import ToolExecutor


class FakeProtector:
    def encrypt(self, content):
        return b"ciphertext:" + content.encode("utf-8")[::-1]
    def decrypt(self, content):
        if not content.startswith(b"ciphertext:"):
            raise ValueError("bad")
        return content[len(b"ciphertext:"):][::-1].decode("utf-8")


class PrivateToolTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        root = Path(self.temp.name)
        self.memory = Memory(root / "legacy.db")
        self.vault = ProjectVault(root / "encrypted.db", protector=FakeProtector())
        self.cfg = Config()
        self.cfg.private_memory_enabled = True
        self.approved = []
        self.tool = ToolExecutor(self.cfg, self.memory, MagicMock(),
                                 lambda name, detail: self.approved.append((name, detail)) or True,
                                 lambda: "", project_vault=self.vault)

    def tearDown(self):
        self.vault.close()
        self.memory.close()
        self.temp.cleanup()

    def test_optin_required_no_plaintext_fallback(self):
        self.cfg.private_memory_enabled = False
        result = self.tool.execute("remember_project",
                      {"project":"PayCore","note":"Never save this plaintext"})
        self.assertIn("disabled", result["error"])
        self.assertEqual(self.vault.search("PayCore"), [])

    def test_owner_approval_needed_before_save_search_delete(self):
        self.tool.approve = lambda *_: False
        for name, args in [
            ("remember_project", {"project":"PayCore","note":"New agreement details"}),
            ("search_project_memory", {"project":"PayCore","query":"agreement"}),
            ("forget_project_note", {"project":"PayCore","note_id":1}),
            ("backup_project_memory", {}),
        ]:
            result = self.tool.execute(name, args)
            self.assertIn("denied", result["error"])
        self.assertEqual(self.vault.search("PayCore"), [])

    def test_project_notes_scoped_and_deletable_with_permission(self):
        saved = self.tool.execute("remember_project", {
            "project":"PayCore","note":"The new card reader is ready for testing"
        })
        i = saved["encrypted_note_id"]
        matches = self.tool.execute("search_project_memory", {
            "project":"PayCore","query":"card reader"
        })
        self.assertEqual(matches["notes"][0]["id"], i)
        self.assertEqual(self.tool.execute("search_project_memory", {
            "project":"Freedom Homes","query":"card reader"
        })["notes"], [])
        self.assertTrue(self.tool.execute("forget_project_note", {
            "project":"PayCore","note_id":i
        })["deleted"])
        self.assertFalse(self.tool.execute("forget_project_note", {
            "project":"PayCore","note_id":i
        })["deleted"])

    def test_private_shortcut_is_not_sent_to_cloud_or_legacy_history(self):
        agent = Agent(self.cfg, self.memory, self.tool, client=MagicMock())
        out = agent.ask("Remember for PayCore: Payment revenue splits need final approval")
        self.assertIn("Encrypted", out)
        out = agent.ask("Search PayCore notes about revenue")
        self.assertIn("revenue splits", out)
        agent.client.responses.create.assert_not_called()
        self.assertEqual(self.memory.recent(), [])

    def test_backup_contains_encrypted_only(self):
        self.tool.execute("remember_project", {
            "project":"Personal","note":"Private vault backup example"
        })
        backup = self.tool.execute("backup_project_memory", {})
        self.assertTrue(backup["encrypted_backup"].endswith(".sqlite"))
        data = Path(backup["encrypted_backup"]).read_bytes()
        self.assertNotIn(b"Private vault backup example", data)
        Path(backup["encrypted_backup"]).unlink(missing_ok=True)
