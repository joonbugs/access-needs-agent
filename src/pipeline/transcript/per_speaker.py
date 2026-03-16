"""Per-speaker transcript accumulator."""

from __future__ import annotations

from datetime import timedelta

import srt

from ..asr.types import UtteranceResult


class PerSpeakerTranscript:
    """Accumulates final utterances for a single speaker/channel.

    Stores only final (non-interim) utterances in time order.
    Provides methods to retrieve entries and convert to SRT subtitles.
    """

    def __init__(self, channel_index: int, speaker_label: str):
        self.channel_index = channel_index
        self.speaker_label = speaker_label
        self._utterances: list[UtteranceResult] = []

    def add(self, utterance: UtteranceResult) -> None:
        """Add an utterance. Only final utterances are stored."""
        if utterance.is_final and utterance.transcript.strip():
            self._utterances.append(utterance)

    def get_all(self) -> list[UtteranceResult]:
        """Return all accumulated utterances."""
        return list(self._utterances)

    def get_since(self, timestamp: float) -> list[UtteranceResult]:
        """Return utterances starting at or after the given timestamp."""
        return [u for u in self._utterances if u.start >= timestamp]

    def to_srt_entries(self) -> list[srt.Subtitle]:
        """Convert accumulated utterances to SRT subtitle entries."""
        entries = []
        for i, u in enumerate(self._utterances, start=1):
            entries.append(
                srt.Subtitle(
                    index=i,
                    start=timedelta(seconds=u.start),
                    end=timedelta(seconds=u.end),
                    content=u.transcript,
                )
            )
        return entries

    def clear(self) -> None:
        """Clear all accumulated utterances."""
        self._utterances.clear()

    def __len__(self) -> int:
        return len(self._utterances)
