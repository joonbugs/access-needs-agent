"""File-based audio source for reading multi-channel WAV files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator

import numpy as np
import soundfile as sf

from .base import AudioSource


class FileAudioSource(AudioSource):
    """Reads a multi-channel WAV file and yields chunks.

    Supports two playback speeds:
    - 'realtime': sleeps between chunks to simulate real-time capture
    - 'fast': yields chunks as fast as possible (for batch processing / testing)
    """

    def __init__(
        self,
        file_path: str | Path,
        chunk_size: int = 4096,
        playback_speed: str = "realtime",
    ):
        self._file_path = Path(file_path)
        self._chunk_size = chunk_size
        self._playback_speed = playback_speed
        self._sf: sf.SoundFile | None = None
        self._sample_rate: int = 0
        self._num_channels: int = 0
        self._done = False

    async def __aenter__(self) -> FileAudioSource:
        self._sf = sf.SoundFile(str(self._file_path), mode="r")
        self._sample_rate = self._sf.samplerate
        self._num_channels = self._sf.channels
        self._done = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._sf is not None:
            self._sf.close()
            self._sf = None

    def __aiter__(self) -> AsyncIterator[np.ndarray]:
        return self

    async def __anext__(self) -> np.ndarray:
        if self._done or self._sf is None:
            raise StopAsyncIteration

        # Read from file (blocking I/O, but WAV reads are fast)
        data = self._sf.read(self._chunk_size, dtype="float32")

        if len(data) == 0:
            self._done = True
            raise StopAsyncIteration

        # Ensure 2D shape even for mono
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        # Simulate real-time playback delay
        if self._playback_speed == "realtime":
            chunk_duration = len(data) / self._sample_rate
            await asyncio.sleep(chunk_duration)

        return data

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def num_channels(self) -> int:
        return self._num_channels
