"""Sentence-paced streamed speech. Pure Python and deterministic."""
from __future__ import annotations

import re


class SentenceBuffer:
    """Accumulate model tokens until a human-sized phrase can be spoken."""
    def __init__(self, *, min_chars: int = 28, max_chars: int = 180):
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.pending = ""

    def feed(self, delta: str) -> list[str]:
        self.pending += delta or ""
        ready: list[str] = []
        while True:
            match = re.search(r"[.!?](?:[\"'\u201d])?\s+", self.pending)
            if match and match.end() >= self.min_chars:
                cut = match.end()
            elif len(self.pending) >= self.max_chars:
                cut = self.pending.rfind(" ", 0, self.max_chars)
                if cut < self.min_chars:
                    cut = self.max_chars
            else:
                break
            phrase = self.pending[:cut].strip()
            self.pending = self.pending[cut:].lstrip()
            if phrase:
                ready.append(phrase)
        return ready

    def flush(self) -> list[str]:
        rest = self.pending.strip()
        self.pending = ""
        return [rest] if rest else []
