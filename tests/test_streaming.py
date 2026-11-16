from unittest import TestCase
from jarvis.streaming import SentenceBuffer


class StreamingTests(TestCase):
    def test_speaks_first_sentence_without_full_answer(self):
        buf = SentenceBuffer(min_chars=10)
        self.assertEqual(buf.feed("Hello, I am JARVIS. This is"), ["Hello, I am JARVIS."])
        self.assertEqual(buf.flush(), ["This is"])

    def test_long_answer_does_not_wait_forever(self):
        buf = SentenceBuffer(max_chars=80, min_chars=12)
        segments = buf.feed("word " * 40)
        self.assertGreaterEqual(len(segments), 2)
        self.assertTrue(all(len(s) <= 80 for s in segments))

    def test_empty_tokens_are_ignored(self):
        buf = SentenceBuffer()
        self.assertEqual(buf.feed(""), [])
        self.assertEqual(buf.flush(), [])

    def test_flush_preserves_short_reply(self):
        buf = SentenceBuffer()
        self.assertEqual(buf.feed("Ready."), [])
        self.assertEqual(buf.flush(), ["Ready."])

    def test_multiple_sentences(self):
        buf = SentenceBuffer(min_chars=10)
        self.assertEqual(buf.feed("First complete! Second complete? "), ["First complete!", "Second complete?"])
