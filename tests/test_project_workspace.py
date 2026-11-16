from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from types import SimpleNamespace

from jarvis.project_workspace import project_root, read_project_status


class ProjectWorkspaceTests(TestCase):
    def test_paycore_status_read_is_explicitly_scoped(self):
        with TemporaryDirectory() as dirname:
            p = Path(dirname)
            (p / "JARVIS_STATUS.md").write_text("PayCore controller hardware status")
            cfg = SimpleNamespace(project_folders={"PayCore": str(p)})
            self.assertEqual(project_root(cfg, "paycore"), p.resolve())
            result = read_project_status(cfg, "paycore")
            self.assertIn("controller hardware", result["content"])
            self.assertFalse(result["live"])

    def test_unknown_project_denied(self):
        with TemporaryDirectory() as dirname:
            cfg = SimpleNamespace(project_folders={"PayCore": dirname})
            with self.assertRaises(KeyError):
                project_root(cfg, "PrivateClient")

    def test_symlink_cannot_escape_project_root(self):
        with TemporaryDirectory() as dirname:
            root = Path(dirname)
            project = root / "workspace"
            project.mkdir()
            secret = root / "secret.txt"
            secret.write_text("private")
            try:
                (project / "JARVIS_STATUS.md").symlink_to(secret)
            except OSError:
                self.skipTest("Symlinks unavailable on this machine")
            cfg = SimpleNamespace(project_folders={"PayCore": str(project)})
            with self.assertRaises(FileNotFoundError):
                read_project_status(cfg, "PayCore")

    def test_missing_status_is_not_invented(self):
        with TemporaryDirectory() as dirname:
            cfg = SimpleNamespace(project_folders={"PayCore": dirname})
            with self.assertRaises(FileNotFoundError):
                read_project_status(cfg, "PayCore")


class ProjectToolApprovalTests(TestCase):
    def test_local_status_requires_explicit_approval(self):
        from jarvis.config import Config
        from jarvis.memory import Memory
        from jarvis.tools import ToolExecutor
        from unittest.mock import MagicMock

        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "JARVIS_STATUS.md").write_text("Test safe status", encoding="utf-8")
            cfg = Config()
            cfg.project_folders = {"PayCore": str(root)}
            memory = Memory(root / "local.db")
            try:
                denied = ToolExecutor(cfg, memory, MagicMock(), lambda *_: False,
                                      lambda: "not used")
                self.assertIn("denied", denied.execute(
                    "read_project_status", {"name": "PayCore"})["error"])
                accepted = ToolExecutor(cfg, memory, MagicMock(), lambda *_: True,
                                        lambda: "not used")
                result = accepted.execute("read_project_status", {"name": "PayCore"})
                self.assertEqual(result["content"], "Test safe status")
                self.assertFalse(result["live"])
            finally:
                memory.close()

    def test_only_opted_in_project_can_be_read(self):
        from jarvis.config import Config
        from jarvis.memory import Memory
        from jarvis.tools import ToolExecutor
        from unittest.mock import MagicMock

        with TemporaryDirectory() as folder:
            cfg = Config()
            cfg.project_folders = {}
            memory = Memory(Path(folder) / "test.db")
            try:
                tool = ToolExecutor(cfg, memory, MagicMock(), lambda *_: True, lambda: "")
                self.assertIn("Unknown project", tool.execute(
                    "read_project_status", {"name": "PayCore"})["error"])
            finally:
                memory.close()
