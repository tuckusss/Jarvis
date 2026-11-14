import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile

from jarvis.wake_model import (
    MODEL_NAME, _safe_model_member, extract_verified_model, is_valid_model, resolve_model,
)


class WakeModelTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.zip_path = self.root / "model.zip"
        self.target = self.root / "installed" / MODEL_NAME

    def tearDown(self):
        self.temp.cleanup()

    def _archive(self, *, attack=False):
        with ZipFile(self.zip_path, "w") as archive:
            archive.writestr(f"{MODEL_NAME}/am/final.mdl", b"sample model marker")
            archive.writestr(f"{MODEL_NAME}/conf/model.conf", "test")
            archive.writestr(f"{MODEL_NAME}/graph/HCLG.fst", "test")
            if attack:
                archive.writestr(f"{MODEL_NAME}/../outside.txt", "bad")
        return hashlib.sha256(self.zip_path.read_bytes()).hexdigest()

    def test_verified_model_installs_without_manual_folder_selection(self):
        expected = self._archive()
        actual = extract_verified_model(self.zip_path, self.target, expected)
        self.assertEqual(actual, self.target)
        self.assertTrue(is_valid_model(actual))
        with patch("jarvis.wake_model.packaged_model", return_value=self.root / "not-bundled"), \
             patch("jarvis.wake_model.installed_model", return_value=actual):
            self.assertEqual(resolve_model(), actual)

    def test_bad_sha_rejected_without_installation(self):
        self._archive()
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            extract_verified_model(self.zip_path, self.target, "0" * 64)
        self.assertFalse(self.target.exists())

    def test_archive_traversal_rejected_without_writing_outside(self):
        expected = self._archive(attack=True)
        with self.assertRaisesRegex(ValueError, "Unsafe file path"):
            extract_verified_model(self.zip_path, self.target, expected)
        self.assertFalse((self.root / "outside.txt").exists())
        self.assertFalse(self.target.exists())

    def test_windows_drive_and_absolute_path_rejected(self):
        for value in ["../escape", "/root", "C:/escape", f"{MODEL_NAME}/C:tmp"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _safe_model_member(value)
