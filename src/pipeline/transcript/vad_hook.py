"""Pluggable VAD (Voice Activity Detection) interface for ghost suppression.

The fast path (local audio analysis) will implement VADSignal when it's built.
Until then, NullVAD is used as a no-op default.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class VADSignal(Protocol):
    """Protocol for the fast-path VAD to implement."""

    async def dominant_speaker_at(self, timestamp: float) -> Optional[int]:
        """Return channel index of dominant speaker at given timestamp, or None."""
        ...


class NullVAD:
    """Default no-op implementation when fast path isn't available."""

    async def dominant_speaker_at(self, timestamp: float) -> Optional[int]:
        return None
