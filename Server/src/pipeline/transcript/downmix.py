"""Transcript downmixer — merges per-speaker transcripts into a unified timeline."""

from __future__ import annotations

from datetime import timedelta

import srt

from ..asr.types import UtteranceResult
from ..config import DownmixConfig
from .per_speaker import PerSpeakerTranscript
from .vad_hook import NullVAD, VADSignal


class TranscriptDownmixer:
    """Merges N per-speaker transcript streams into one unified timeline.

    Handles:
    - Sorting utterances from all speakers by start time
    - Adding speaker labels to the unified transcript
    - Ghost suppression (crosstalk filtering) via confidence threshold and optional VAD
    """

    def __init__(self, config: DownmixConfig, vad: VADSignal | None = None):
        self._config = config
        self._vad = vad or NullVAD()

    async def merge(
        self, accumulators: list[PerSpeakerTranscript]
    ) -> list[srt.Subtitle]:
        """Merge all per-speaker utterances into a unified SRT entry list.

        Returns speaker-labeled, time-sorted SRT subtitles.
        """
        # Collect all utterances with their speaker labels
        all_utterances: list[UtteranceResult] = []
        for acc in accumulators:
            all_utterances.extend(acc.get_all())

        # Ghost suppression: remove likely crosstalk
        filtered = await self._suppress_ghosts(all_utterances)

        # Sort by start time
        filtered.sort(key=lambda u: u.start)

        # Build SRT entries with speaker labels
        entries = []
        for i, u in enumerate(filtered, start=1):
            label = u.speaker_label or f"Channel {u.channel_index}"
            content = f"[{label}] {u.transcript}"
            entries.append(
                srt.Subtitle(
                    index=i,
                    start=timedelta(seconds=u.start),
                    end=timedelta(seconds=u.end),
                    content=content,
                )
            )
        return entries

    async def _suppress_ghosts(
        self, utterances: list[UtteranceResult]
    ) -> list[UtteranceResult]:
        """Filter out ghost utterances caused by mic crosstalk/bleed.

        Strategy:
        1. If VAD signal available: use dominant speaker to filter
        2. Else: when two channels overlap in time, suppress the one with
           lower average word confidence (below threshold)
        """
        if not utterances:
            return utterances

        kept: list[UtteranceResult] = []
        threshold = self._config.ghost_confidence_threshold

        for u in utterances:
            # Check VAD signal first
            dominant = await self._vad.dominant_speaker_at(u.start)
            if dominant is not None and dominant != u.channel_index:
                # VAD says a different channel is dominant — check confidence
                if u.avg_confidence < threshold:
                    continue  # suppress this ghost

            # Confidence-based heuristic: check for overlapping utterances
            # from other channels with higher confidence
            is_ghost = False
            for other in utterances:
                if other.channel_index == u.channel_index:
                    continue
                if self._overlaps(u, other) and u.avg_confidence < threshold and other.avg_confidence > u.avg_confidence:
                    is_ghost = True
                    break

            if not is_ghost:
                kept.append(u)

        return kept

    @staticmethod
    def _overlaps(a: UtteranceResult, b: UtteranceResult) -> bool:
        """Check if two utterances overlap in time."""
        return a.start < b.end and b.start < a.end
