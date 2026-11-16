from unittest import TestCase
from jarvis.endpointing import SpeechEndpoint


class SpeechEndpointTests(TestCase):
    def test_quiet_speech_starts_and_ends(self):
        detector = SpeechEndpoint()
        for _ in range(7):
            self.assertFalse(detector.observe(35)[0])
        self.assertFalse(detector.observe(270)[0])
        self.assertTrue(detector.observe(320)[0])
        for _ in range(detector.quiet_frames - 1):
            self.assertFalse(detector.observe(10)[1])
        self.assertTrue(detector.observe(10)[1])

    def test_noise_threshold_adapts_to_constant_background(self):
        detector = SpeechEndpoint()
        for _ in range(10):
            detector.observe(440)
        self.assertGreaterEqual(detector.threshold, 1100)
        self.assertFalse(detector.started)
        self.assertFalse(detector.observe(800)[0])
        self.assertTrue(detector.observe(1600)[0] is False)
        self.assertTrue(detector.observe(1800)[0])

    def test_speech_only_after_multiple_frames(self):
        detector = SpeechEndpoint()
        for _ in range(5):
            detector.observe(10)
        detector.observe(400)
        detector.observe(5)
        self.assertFalse(detector.started)
