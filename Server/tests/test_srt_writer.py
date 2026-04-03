"""Tests for the SRT writer."""

import tempfile
from datetime import timedelta
from pathlib import Path

import srt

from pipeline.output.srt_writer import SRTWriter


class TestSRTWriter:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.output_dir = Path(self.tmpdir) / "output"
        self.pending_dir = Path(self.tmpdir) / "pending"
        self.writer = SRTWriter(self.output_dir, self.pending_dir, "test_session")

    def test_write_per_speaker_creates_files(self):
        entries = [
            srt.Subtitle(
                index=1,
                start=timedelta(seconds=0),
                end=timedelta(seconds=1),
                content="Hello world",
            )
        ]
        path = self.writer.write_per_speaker(0, "Speaker A", entries)

        assert path.exists()
        assert "Speaker_A" in path.name
        # Also check pending dir
        pending_path = self.pending_dir / path.name
        assert pending_path.exists()

    def test_write_unified_creates_files(self):
        entries = [
            srt.Subtitle(
                index=1,
                start=timedelta(seconds=0),
                end=timedelta(seconds=1),
                content="[Speaker A] Hello",
            ),
            srt.Subtitle(
                index=2,
                start=timedelta(seconds=1),
                end=timedelta(seconds=2),
                content="[Speaker B] Hi there",
            ),
        ]
        path = self.writer.write_unified(entries)

        assert path.exists()
        assert "unified" in path.name

        content = path.read_text()
        assert "[Speaker A] Hello" in content
        assert "[Speaker B] Hi there" in content

    def test_srt_format_is_valid(self):
        entries = [
            srt.Subtitle(
                index=1,
                start=timedelta(seconds=1.5),
                end=timedelta(seconds=3.2),
                content="Test content",
            )
        ]
        path = self.writer.write_per_speaker(0, "Test", entries)
        content = path.read_text()

        # Parse it back to verify valid SRT
        parsed = list(srt.parse(content))
        assert len(parsed) == 1
        assert parsed[0].content == "Test content"
        assert parsed[0].start == timedelta(seconds=1.5)

    def test_atomic_write_no_partial_files(self):
        """No .tmp files should remain after writing."""
        entries = [
            srt.Subtitle(
                index=1,
                start=timedelta(seconds=0),
                end=timedelta(seconds=1),
                content="test",
            )
        ]
        self.writer.write_per_speaker(0, "Speaker", entries)

        tmp_files = list(self.output_dir.glob("*.tmp"))
        assert len(tmp_files) == 0
