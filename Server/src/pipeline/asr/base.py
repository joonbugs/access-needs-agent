"""Abstract base for ASR clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from .types import UtteranceResult


class ASRClient(ABC):
    """Abstract ASR client interface.

    One instance per audio channel. Manages a connection to the ASR service,
    accepts audio chunks, and yields transcript results.
    """

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def send_audio(self, pcm_bytes: bytes) -> None:
        ...

    @abstractmethod
    async def results(self) -> AsyncIterator[UtteranceResult]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
