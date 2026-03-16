"""Data types for ASR results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WordResult:
    """A single recognized word with timing and confidence."""

    word: str
    start: float  # seconds from session start
    end: float
    confidence: float
    speaker_label: str = ""


@dataclass
class UtteranceResult:
    """A complete or partial utterance from one channel."""

    words: list[WordResult] = field(default_factory=list)
    transcript: str = ""
    is_final: bool = False
    channel_index: int = 0
    speaker_label: str = ""

    @property
    def start(self) -> float:
        return self.words[0].start if self.words else 0.0

    @property
    def end(self) -> float:
        return self.words[-1].end if self.words else 0.0

    @property
    def avg_confidence(self) -> float:
        if not self.words:
            return 0.0
        return sum(w.confidence for w in self.words) / len(self.words)
