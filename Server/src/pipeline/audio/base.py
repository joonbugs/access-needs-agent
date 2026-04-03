"""Abstract base for audio sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

import numpy as np


class AudioSource(ABC):
    """Async context manager that yields multi-channel audio chunks.

    Each yielded array has shape (frames, num_channels), dtype float32,
    with samples in [-1.0, 1.0].
    """

    @abstractmethod
    async def __aenter__(self) -> AudioSource:
        ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[np.ndarray]:
        ...

    @abstractmethod
    async def __anext__(self) -> np.ndarray:
        ...

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        ...

    @property
    @abstractmethod
    def num_channels(self) -> int:
        ...
