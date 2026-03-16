"""Deepgram ASR client — one WebSocket connection per audio channel."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from typing import AsyncIterator

from deepgram import (
    DeepgramClient,
    LiveOptions,
    LiveTranscriptionEvents,
)

from ..config import ASRConfig
from .base import ASRClient
from .types import UtteranceResult, WordResult

logger = logging.getLogger(__name__)


class DeepgramASRClient(ASRClient):
    """Manages a single Deepgram WebSocket connection for one audio channel.

    Streams mono linear16 PCM audio and emits UtteranceResult objects
    as transcripts arrive.

    Deepgram callbacks fire in a background thread, so we use a thread-safe
    deque + asyncio Event to bridge results to the async consumer.
    """

    def __init__(self, channel_index: int, speaker_label: str, config: ASRConfig):
        self._channel = channel_index
        self._speaker = speaker_label
        self._config = config
        self._client = DeepgramClient(config.api_key)
        self._connection = None
        # Thread-safe buffer: Deepgram callbacks write from a worker thread
        self._buffer: deque[UtteranceResult] = deque()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event = asyncio.Event()
        self._connected = False
        self._closing = False

    async def connect(self) -> None:
        """Open a WebSocket connection to Deepgram."""
        self._loop = asyncio.get_running_loop()

        options = LiveOptions(
            model=self._config.model,
            language=self._config.language,
            encoding="linear16",
            sample_rate=16000,
            channels=1,
            smart_format=self._config.smart_format,
            interim_results=self._config.interim_results,
            utterance_end_ms=str(self._config.utterance_end_ms),
            endpointing=str(self._config.endpointing_ms),
        )

        self._connection = self._client.listen.websocket.v("1")
        self._connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
        self._connection.on(LiveTranscriptionEvents.Error, self._on_error)
        self._connection.on(LiveTranscriptionEvents.Close, self._on_close)

        started = self._connection.start(options)
        if not started:
            raise ConnectionError(
                f"Failed to start Deepgram connection for channel {self._channel}"
            )
        self._connected = True
        logger.info("Deepgram connected for channel %d (%s)", self._channel, self._speaker)

    def _on_transcript(self, _self, result, **kwargs) -> None:
        """Handle incoming transcript from Deepgram (called from worker thread)."""
        try:
            channel = result.channel
            alt = channel.alternatives[0] if channel.alternatives else None
            if alt is None or not alt.transcript.strip():
                return

            words = [
                WordResult(
                    word=w.word,
                    start=w.start,
                    end=w.end,
                    confidence=w.confidence,
                    speaker_label=self._speaker,
                )
                for w in (alt.words or [])
            ]

            utterance = UtteranceResult(
                words=words,
                transcript=alt.transcript,
                is_final=result.is_final,
                channel_index=self._channel,
                speaker_label=self._speaker,
            )

            logger.debug(
                "Channel %d transcript (final=%s): %s",
                self._channel, result.is_final, alt.transcript,
            )

            # Thread-safe: append to deque and wake async consumer
            with self._lock:
                self._buffer.append(utterance)
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._event.set)

        except Exception:
            logger.exception("Error processing Deepgram transcript for channel %d", self._channel)

    def _on_error(self, _self, error, **kwargs) -> None:
        """Handle Deepgram errors."""
        logger.error("Deepgram error on channel %d: %s", self._channel, error)

    def _on_close(self, _self, close, **kwargs) -> None:
        """Handle Deepgram connection close."""
        self._connected = False
        if not self._closing:
            logger.warning("Deepgram connection closed unexpectedly for channel %d", self._channel)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._event.set)

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Send a chunk of mono linear16 PCM audio."""
        if self._connection is not None and self._connected:
            self._connection.send(pcm_bytes)

    async def results(self) -> AsyncIterator[UtteranceResult]:
        """Yield utterance results as they arrive."""
        while True:
            # Drain anything in the buffer
            while True:
                with self._lock:
                    if not self._buffer:
                        break
                    utterance = self._buffer.popleft()
                yield utterance

            if not self._connected and self._closing:
                break

            # Wait for new data or timeout
            self._event.clear()
            try:
                await asyncio.wait_for(self._event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

    async def close(self) -> None:
        """Close the Deepgram connection."""
        self._closing = True
        if self._connection is not None:
            self._connection.finish()
        self._connected = False
        self._event.set()
        logger.info("Deepgram closed for channel %d", self._channel)

    @property
    def healthy(self) -> bool:
        return self._connected
