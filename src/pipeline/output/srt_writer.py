"""Write per-speaker and unified SRT files with atomic file operations."""

from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from pathlib import Path

import srt


def make_subtitle(index: int, start: float, end: float, text: str) -> srt.Subtitle:
    """Create an srt.Subtitle from seconds-based timestamps."""
    return srt.Subtitle(
        index=index,
        start=timedelta(seconds=start),
        end=timedelta(seconds=end),
        content=text,
    )


class SRTWriter:
    """Writes SRT transcript files with atomic file operations.

    Atomic writes prevent Vicky's downstream watcher from picking up
    partially-written files: we write to a temp file first, then rename.
    """

    def __init__(self, output_dir: str | Path, pending_dir: str | Path, session_id: str):
        self._output_dir = Path(output_dir)
        self._pending_dir = Path(pending_dir)
        self._session_id = session_id
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._pending_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write content to a file atomically using tmp + rename."""
        dir_ = path.parent
        fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=dir_)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def write_per_speaker(
        self, channel_index: int, speaker_label: str, entries: list[srt.Subtitle]
    ) -> Path:
        """Write a per-speaker SRT file to the output dir and pending dir."""
        safe_label = speaker_label.replace(" ", "_")
        filename = f"{self._session_id}_{safe_label}.srt"
        content = srt.compose(entries)

        # Write to output dir (archive)
        out_path = self._output_dir / filename
        self._atomic_write(out_path, content)

        # Write to pending dir (for downstream processing)
        pending_path = self._pending_dir / filename
        self._atomic_write(pending_path, content)

        return out_path

    def write_unified(self, entries: list[srt.Subtitle]) -> Path:
        """Write the unified (all speakers) SRT file."""
        filename = f"{self._session_id}_unified.srt"
        content = srt.compose(entries)

        out_path = self._output_dir / filename
        self._atomic_write(out_path, content)

        pending_path = self._pending_dir / filename
        self._atomic_write(pending_path, content)

        return out_path
