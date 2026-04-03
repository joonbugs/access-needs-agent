"""Live audio capture from a multi-channel audio interface via sounddevice."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

import numpy as np
import sounddevice as sd

from .base import AudioSource

logger = logging.getLogger(__name__)


class LiveAudioSource(AudioSource):
    """Captures multi-channel audio from a system audio device.

    Uses sounddevice (PortAudio) to open an InputStream. The PortAudio
    callback runs in a separate thread and pushes frames into an asyncio
    queue via call_soon_threadsafe.
    """

    def __init__(
        self,
        channels: int = 4,
        sample_rate: int = 16000,
        chunk_size: int = 4096,
        device_index: Optional[int] = None,
    ):
        self._channels = channels
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._device_index = device_index
        self._stream: Optional[sd.InputStream] = None
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=100)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._done = False

    async def __aenter__(self) -> LiveAudioSource:
        self._loop = asyncio.get_running_loop()
        self._done = False

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="float32",
            blocksize=self._chunk_size,
            device=self._device_index,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info(
            "Live audio capture started: %d channels, %d Hz, device=%s",
            self._channels,
            self._sample_rate,
            self._device_index or "default",
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._done = True
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Live audio capture stopped")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """PortAudio callback — runs in a separate thread."""
        if status:
            logger.warning("Audio callback status: %s", status)
        if self._loop is not None and not self._done:
            data = indata.copy()  # PortAudio buffer is reused
            self._loop.call_soon_threadsafe(self._enqueue, data)

    def _enqueue(self, data: np.ndarray) -> None:
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            logger.warning("Audio queue full — dropping frame")

    def __aiter__(self) -> AsyncIterator[np.ndarray]:
        return self

    async def __anext__(self) -> np.ndarray:
        if self._done:
            raise StopAsyncIteration
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=2.0)
        except asyncio.TimeoutError:
            if self._done:
                raise StopAsyncIteration
            # Return silence frame to keep pipeline alive
            return np.zeros((self._chunk_size, self._channels), dtype=np.float32)

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def num_channels(self) -> int:
        return self._channels
