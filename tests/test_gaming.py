from unittest import TestCase
from jarvis.gaming import detect_game, select_inference_threads


class GamingTests(TestCase):
    def test_detects_crusader_kings(self):
        s = detect_game(["explorer.exe", "CK3.EXE"])
        self.assertTrue(s.active)
        self.assertEqual(s.title, "Crusader Kings III")

    def test_detects_mount_and_blade_warband(self):
        s = detect_game(["mb_warband.exe"])
        self.assertTrue(s.active)
        self.assertIn("Warband", s.title)

    def test_never_matches_similarly_named_process(self):
        self.assertFalse(detect_game(["ck3-loader-virus.exe", "game.exe"]).active)

    def test_gaming_caps_local_ai_threads(self):
        self.assertEqual(select_inference_threads(16, gaming=False), 6)
        self.assertEqual(select_inference_threads(16, gaming=True), 2)
        self.assertEqual(select_inference_threads(2, gaming=True), 2)
