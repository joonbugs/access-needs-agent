"""Tests for the transcript downmixer."""

import pytest

from pipeline.asr.types import UtteranceResult, WordResult
from pipeline.config import DownmixConfig
from pipeline.transcript.downmix import TranscriptDownmixer
from pipeline.transcript.per_speaker import PerSpeakerTranscript
from pipeline.transcript.vad_hook import NullVAD


@pytest.fixture
def downmixer():
    return TranscriptDownmixer(config=DownmixConfig(), vad=NullVAD())


class TestTranscriptDownmixer:
    @pytest.mark.asyncio
    async def test_merge_sorts_by_start_time(self, downmixer, populated_accumulators):
        entries = await downmixer.merge(populated_accumulators)

        # Should be sorted by time
        times = [e.start.total_seconds() for e in entries]
        assert times == sorted(times)

    @pytest.mark.asyncio
    async def test_merge_includes_speaker_labels(self, downmixer, populated_accumulators):
        entries = await downmixer.merge(populated_accumulators)

        labels = [e.content for e in entries]
        assert any("[Speaker A]" in label for label in labels)
        assert any("[Speaker B]" in label for label in labels)

    @pytest.mark.asyncio
    async def test_merge_empty_accumulators(self, downmixer):
        acc = [PerSpeakerTranscript(0, "A"), PerSpeakerTranscript(1, "B")]
        entries = await downmixer.merge(acc)
        assert entries == []

    @pytest.mark.asyncio
    async def test_ghost_suppression_by_confidence(self):
        """Low-confidence overlapping utterance from another channel should be suppressed."""
        config = DownmixConfig(ghost_confidence_threshold=0.7)
        downmixer = TranscriptDownmixer(config=config, vad=NullVAD())

        acc_a = PerSpeakerTranscript(0, "Speaker A")
        acc_b = PerSpeakerTranscript(1, "Speaker B")

        # Speaker A says something with high confidence
        acc_a.add(UtteranceResult(
            words=[WordResult("Hello", 0.0, 1.0, 0.95, "Speaker A")],
            transcript="Hello",
            is_final=True,
            channel_index=0,
            speaker_label="Speaker A",
        ))

        # Speaker B's mic picks up bleed — same time, low confidence
        acc_b.add(UtteranceResult(
            words=[WordResult("Hello", 0.1, 0.9, 0.4, "Speaker B")],
            transcript="Hello",
            is_final=True,
            channel_index=1,
            speaker_label="Speaker B",
        ))

        entries = await downmixer.merge([acc_a, acc_b])

        # Ghost should be suppressed — only Speaker A's utterance remains
        assert len(entries) == 1
        assert "[Speaker A]" in entries[0].content

    @pytest.mark.asyncio
    async def test_overlapping_speech_both_kept_when_confident(self):
        """Both speakers kept when both have high confidence (real simultaneous speech)."""
        config = DownmixConfig(ghost_confidence_threshold=0.7)
        downmixer = TranscriptDownmixer(config=config, vad=NullVAD())

        acc_a = PerSpeakerTranscript(0, "Speaker A")
        acc_b = PerSpeakerTranscript(1, "Speaker B")

        acc_a.add(UtteranceResult(
            words=[WordResult("I think", 1.0, 2.0, 0.92, "Speaker A")],
            transcript="I think",
            is_final=True,
            channel_index=0,
            speaker_label="Speaker A",
        ))

        acc_b.add(UtteranceResult(
            words=[WordResult("Exactly", 1.5, 2.5, 0.89, "Speaker B")],
            transcript="Exactly",
            is_final=True,
            channel_index=1,
            speaker_label="Speaker B",
        ))

        entries = await downmixer.merge([acc_a, acc_b])
        assert len(entries) == 2
