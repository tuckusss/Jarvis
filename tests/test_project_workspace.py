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
