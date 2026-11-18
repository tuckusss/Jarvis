"""Private memory never writes note plaintext to SQLite."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from jarvis.config import Config
from jarvis.project_vault import ProjectVault, project_name


class FakeCipher:
    """Insecure deterministic test double; never used in the application."""
    def encrypt(self, value: str) -> bytes:
        return b"test-cipher:" + value[::-1].encode("utf-8")
    def decrypt(self, value: bytes) -> str:
        if not value.startswith(b"test-cipher:"):
            raise ValueError("invalid ciphertext")
        return value[len(b"test-cipher:"):].decode("utf-8")[::-1]


class ProjectVaultTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vault.sqlite"
        self.vault = ProjectVault(self.path, protector=FakeCipher())

    def tearDown(self):
        self.vault.close()
        self.tmp.cleanup()

    def test_encrypt_then_search_scoped_to_project(self):
        note_id = self.vault.remember("PayCore", "Nayax operator settlement milestone")
        self.vault.remember("Freedom Homes", "Monthly inspection status")
        with closing(sqlite3.connect(str(self.path))) as db:
            data = db.execute("SELECT secret FROM project_notes WHERE id=?", (note_id,)).fetchone()[0]
        self.assertNotIn(b"Nayax", data)
        self.assertIn(b"test-cipher:", data)
        self.assertEqual(len(self.vault.search("PayCore", "settlement")), 1)
        self.assertEqual(self.vault.search("Freedom Homes", "settlement"), [])

    def test_delete_only_the_requested_project_note(self):
        a = self.vault.remember("PayCore", "Device revenue schedule")
        b = self.vault.remember("Freedom Homes", "Move out inspection due")
        self.assertFalse(self.vault.forget("Freedom Homes", a))
        self.assertTrue(self.vault.forget("PayCore", a))
        self.assertFalse(self.vault.forget("PayCore", a))
        self.assertEqual(self.vault.search("PayCore"), [])
        self.assertEqual(self.vault.search("Freedom Homes")[0]["id"], b)

    def test_cannot_save_plaintext_if_encrypt_fails(self):
        class Fails:
            def encrypt(self, _: str):
                raise RuntimeError("DPAPI unavailable")
        self.vault.protector = Fails()
        with self.assertRaises(RuntimeError):
            self.vault.remember("PayCore", "should never save")
        self.assertEqual(self.vault.db.execute("SELECT count(*) FROM project_notes").fetchone()[0], 0)

    def test_decryption_failure_never_returns_fake_result(self):
        self.vault.remember("PayCore", "Sensitive project detail")
        class Fails:
            def decrypt(self, value: bytes):
                raise RuntimeError("DPAPI profile unavailable")
        self.vault.protector = Fails()
        with self.assertRaises(RuntimeError):
            self.vault.search("PayCore")

    def test_encrypted_backup_contains_no_plaintext(self):
        self.vault.remember("Personal", "private backup secrets sample")
        path = Path(self.tmp.name) / "copy.sqlite"
        self.vault.encrypted_backup(path)
        self.assertTrue(path.exists())
        self.assertNotIn(b"private backup secrets", path.read_bytes())
        with self.assertRaises(FileExistsError):
            self.vault.encrypted_backup(path)

    def test_project_scope_validation(self):
        cfg = Config()
        self.assertEqual(project_name(cfg, "paycore"), "PayCore")
        self.assertEqual(project_name(cfg, "Freedom Homes"), "Freedom Homes")
        with self.assertRaises(ValueError):
            project_name(cfg, "unlisted client")
        with self.assertRaises(ValueError):
            self.vault.remember("../hidden", "must fail")
        with self.assertRaises(ValueError):
            self.vault.remember("PayCore", "a")

    def test_actual_dpapi_roundtrip_on_windows(self):
        if os.name != "nt":
            self.skipTest("CurrentUser DPAPI is Windows-only")
        from jarvis.windows_crypto import WindowsDpapi
        protector = WindowsDpapi()
        raw = "Confidential test \u2022 " + "a" * 32
        ciphertext = protector.encrypt(raw)
        self.assertNotIn(raw.encode("utf-8"), ciphertext)
        self.assertEqual(protector.decrypt(ciphertext), raw)
        with self.assertRaises((OSError, UnicodeError)):
            protector.decrypt(bytes([ciphertext[0] ^ 1]) + ciphertext[1:])

    def test_no_nonwindows_plaintext_fallback(self):
        if os.name == "nt":
            self.skipTest("Only relevant outside Windows")
        with self.assertRaises(OSError):
            ProjectVault(Path(self.tmp.name) / "should-not-exist.sqlite")
