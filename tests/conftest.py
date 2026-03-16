"""Shared test fixtures."""

import pytest

from pipeline.asr.types import UtteranceResult, WordResult
from pipeline.transcript.per_speaker import PerSpeakerTranscript


@pytest.fixture
def sample_utterances():
    """Create sample utterances from two speakers with some overlap."""
    return [
        UtteranceResult(
            words=[
                WordResult(word="Hello", start=0.0, end=0.5, confidence=0.95, speaker_label="Speaker A"),
                WordResult(word="everyone", start=0.5, end=1.0, confidence=0.92, speaker_label="Speaker A"),
            ],
            transcript="Hello everyone",
            is_final=True,
            channel_index=0,
            speaker_label="Speaker A",
        ),
        UtteranceResult(
            words=[
                WordResult(word="Hi", start=0.8, end=1.1, confidence=0.90, speaker_label="Speaker B"),
                WordResult(word="there", start=1.1, end=1.5, confidence=0.88, speaker_label="Speaker B"),
            ],
            transcript="Hi there",
            is_final=True,
            channel_index=1,
            speaker_label="Speaker B",
        ),
        UtteranceResult(
            words=[
                WordResult(word="How", start=2.0, end=2.3, confidence=0.93, speaker_label="Speaker A"),
                WordResult(word="are", start=2.3, end=2.5, confidence=0.91, speaker_label="Speaker A"),
                WordResult(word="you", start=2.5, end=2.8, confidence=0.94, speaker_label="Speaker A"),
            ],
            transcript="How are you",
            is_final=True,
            channel_index=0,
            speaker_label="Speaker A",
        ),
    ]


@pytest.fixture
def populated_accumulators(sample_utterances):
    """Create accumulators with sample data."""
    acc_a = PerSpeakerTranscript(0, "Speaker A")
    acc_b = PerSpeakerTranscript(1, "Speaker B")

    for u in sample_utterances:
        if u.channel_index == 0:
            acc_a.add(u)
        else:
            acc_b.add(u)

    return [acc_a, acc_b]
