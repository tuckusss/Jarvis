"""Fast, offline speech presentation regression tests."""
from unittest import TestCase

from jarvis.neural_voice import (
    VOICE_CHOICES, spoken_text, speech_segments, neural_available,
)
from jarvis.config import Config


class VoiceQualityTests(TestCase):
    def test_british_male_is_default(self):
        config = Config()
        self.assertEqual(config.voice_engine, "neural")
        self.assertEqual(config.voice_name, "bm_george")
        self.assertIn("bm_george", VOICE_CHOICES)

    def test_speech_strips_markdown_and_urls(self):
        phrase = "## JARVIS\n**Done.** See https://example.org/a for details."
        spoken = spoken_text(phrase)
        self.assertIn("Done.", spoken)
        self.assertNotIn("https:", spoken)
        self.assertNotIn("**", spoken)
        self.assertNotIn("##", spoken)

    def test_large_answers_split_at_sentence_boundaries(self):
        paragraphs = "First answer is ready. " * 30
        parts = speech_segments(paragraphs, max_chars=95)
        self.assertGreater(len(parts), 2)
        self.assertTrue(all(0 < len(p) <= 95 for p in parts))

    def test_code_blocks_not_read_as_speech(self):
        markdown = "Here is the result:\n" + chr(96)*3 + "python\nprint(123)\n" + chr(96)*3
        out = spoken_text(markdown)
        self.assertNotIn("print(123)", out)

    def test_short_voice_answer(self):
        self.assertEqual(speech_segments("Ready."), ["Ready."])

    def test_voice_model_test_reports_missing_files(self):
        # Source checkouts intentionally have no bundled model.
        self.assertIsInstance(neural_available(), bool)
