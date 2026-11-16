"""Adaptive, energy-based speech endpoint detection for offline microphone capture.

This is NOT neural speaker identification or anti-spoofing. It estimates local
ambient noise and waits for sustained speech before ending on a quiet period.
"""
from __future__ import annotations

from collections import deque
import math


class SpeechEndpoint:
    def __init__(self, *, frame_seconds=0.1, trailing_silence=0.65,
                 min_speech_seconds=0.15, minimum_rms=180.0):
        self.frame_seconds = float(frame_seconds)
        # Avoid banker's rounding: 0.15/0.1 must be two voice frames,
        # never one. Ceil keeps timing conservative and deterministic.
        self.quiet_frames = max(1, math.ceil(trailing_silence / self.frame_seconds - 1e-9))
        self.voice_frames = max(2, math.ceil(min_speech_seconds / self.frame_seconds - 1e-9))
        self.minimum_rms = float(minimum_rms)
        self.calibration = deque(maxlen=24)
        self.started = False
        self._voice_streak = 0
        self._quiet_streak = 0

    @property
    def threshold(self) -> float:
        if not self.calibration:
            return max(180.0, self.minimum_rms)
        baseline = sorted(self.calibration)[max(0, len(self.calibration) // 4)]
        return max(self.minimum_rms, baseline * 2.5)

    def observe(self, rms: float) -> tuple[bool, bool]:
        """Return (speech_started, speech_finished) for one audio frame."""
        value = max(0.0, float(rms))
        # First 0.5 s estimates ambient microphone gain. The recorder retains
        # this window as pre-roll so the start of speech is not discarded.
        if len(self.calibration) < 5:
            self.calibration.append(value)
            return False, False
        threshold = self.threshold
        if not self.started:
            if value >= threshold:
                self._voice_streak += 1
            else:
                self._voice_streak = 0
                self.calibration.append(value)
            if self._voice_streak >= self.voice_frames:
                self.started = True
                return True, False
            return False, False
        if value < threshold:
            self._quiet_streak += 1
        else:
            self._quiet_streak = 0
        return False, self._quiet_streak >= self.quiet_frames
