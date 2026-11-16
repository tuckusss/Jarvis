import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from jarvis.config import Config
from jarvis.memory import Memory
from jarvis.tools import ToolExecutor, _path_allowed, TOOLS
from jarvis.agent import Agent


class CoreTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mem = Memory(self.root / "db.sqlite")
        self.cfg = Config()
        self.google = MagicMock()
        self.requested = []

    def tearDown(self):
        self.mem.close()
        self.tmp.cleanup()

    def executor(self, allowed=True):
        def approve(name, detail):
            self.requested.append((name, detail))
            return allowed
        return ToolExecutor(self.cfg, self.mem, self.google, approve, lambda: "Screen summary")

    def test_reminders_claim_only_once(self):
        from datetime import datetime, timedelta, timezone
        in_one_second = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        rid = self.mem.add_reminder(in_one_second, "Check my meeting notes")
        self.assertGreater(rid, 0)
        self.assertEqual(len(self.mem.reminders()), 1)
        from unittest.mock import patch
        from datetime import datetime as RealDatetime
        class Later(RealDatetime):
            @classmethod
            def now(cls, tz=None):
                return RealDatetime.now(tz) + timedelta(seconds=3)
        with patch("jarvis.memory.datetime", Later):
            self.assertEqual(len(self.mem.due_reminders()), 1)
            self.assertEqual(self.mem.due_reminders(), [])

    def test_memory_history_and_notes(self):
        self.mem.remember("Property development project timeline")
        self.mem.message("user", "hello")
        self.mem.message("assistant", "hello back")
        self.assertEqual([x["role"] for x in self.mem.recent()], ["user", "assistant"])
        self.assertEqual(self.mem.recall("project"), ["Property development project timeline"])
        self.mem.clear_history()
        self.assertEqual(self.mem.recent(), [])
        self.assertEqual(len(self.mem.recall()), 1)

    def test_unsafe_actions_denied(self):
        tool = self.executor(allowed=False)
        self.assertIn("denied", tool.execute("send_email", {"to": "a@b.com", "subject": "hi", "body": "ok"})["error"])
        self.assertIn("denied", tool.execute("inspect_screen", {})["error"])
        self.google.send_mail.assert_not_called()
        self.assertEqual(len(self.requested), 2)

    def test_unknown_commands_and_apps_rejected(self):
        tool = self.executor()
        self.assertEqual(tool.execute("run_shell", {"command": "rm -rf"}), {"error": "Unknown tool"})
        self.assertIn("allowlist", tool.execute("open_app", {"app": "powershell"})["error"])

    def test_path_traversal(self):
        allowed = self.root / "allowed"
        allowed.mkdir()
        secret = self.root / "secret.txt"
        secret.write_text("do not read")
        self.assertFalse(_path_allowed(secret, [allowed]))
        self.assertFalse(_path_allowed(allowed / ".." / "secret.txt", [allowed]))

    def test_file_search_no_symlink_escape(self):
        local = self.root / "local"
        local.mkdir()
        actual = self.root / "topsecret"
        actual.mkdir()
        (actual / "letter.txt").write_text("private")
        (local / "safe-letter.txt").write_text("safe")
        try:
            (local / "escape").symlink_to(actual, target_is_directory=True)
        except OSError:
            pass
        self.cfg.custom_folder = str(local)
        with patch("jarvis.tools.roots_for", return_value=[local]):
            res = self.executor().execute("search_files", {"name": "letter"})
        self.assertEqual(len(res["files"]), 1)
        self.assertTrue(res["files"][0].endswith("safe-letter.txt"))

    def test_no_secret_file_read(self):
        p = self.root / "credentials.json"
        p.write_text("secret")
        with patch("jarvis.tools.roots_for", return_value=[self.root]):
            result = self.executor().execute("read_file", {"path": str(p)})
        self.assertIn("excluded", result["error"])

    def test_write_requires_config_opt_in(self):
        tool = self.executor()
        self.google.send_mail.side_effect = PermissionError("write disabled")
        self.assertIn("write disabled", tool.execute("send_email", {"to": "test@example.org", "subject": "a", "body": "hi"})["error"])

    def test_tool_schema_names_unique(self):
        names = [t["name"] for t in TOOLS]
        self.assertEqual(len(names), len(set(names)))

    def test_agent_runs_tool_then_final_response(self):
        first = SimpleNamespace(output=[SimpleNamespace(type="function_call",name="system_status", arguments="{}", call_id="id1")], output_text="")
        second = SimpleNamespace(output=[], output_text="Your system is operating normally.")
        fake = MagicMock()
        fake.responses.create.side_effect = [first, second]
        agent = Agent(self.cfg, self.mem, self.executor(), client=fake)
        answer = agent.ask("How is my system?")
        self.assertIn("normally", answer)
        self.assertEqual(fake.responses.create.call_count, 2)
        sent = fake.responses.create.call_args.kwargs["input"]
        self.assertTrue(any(isinstance(x, dict) and x.get("type") == "function_call_output" for x in sent))


class SearchMemoryTests(TestCase):
    def test_history_search_is_bounded_and_literal(self):
        with TemporaryDirectory() as folder:
            db = Memory(Path(folder) / "messages.db")
            try:
                db.message("user", "Check the warehouse location before sending")
                db.message("assistant", "Warehouse location is listed")
                self.assertEqual(len(db.search_messages("warehouse")), 2)
                self.assertEqual(db.search_messages("%"), [])
                with self.assertRaises(ValueError):
                    db.search_messages("")
            finally:
                db.close()
