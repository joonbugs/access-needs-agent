"""Split interleaved multi-channel audio into per-channel mono PCM buffers."""

from __future__ import annotations

import numpy as np


class ChannelSplitter:
    """Splits a multi-channel numpy array into per-channel linear16 PCM byte buffers.

    Deepgram expects mono linear16 (signed 16-bit int, little-endian) PCM.
    Input arrays are float32 in [-1.0, 1.0] range.
    """

    def split(self, chunk: np.ndarray) -> list[bytes]:
        """Split an interleaved multi-channel chunk into per-channel PCM bytes.

        Args:
            chunk: numpy array of shape (frames, num_channels), dtype float32.

        Returns:
            List of bytes buffers, one per channel, each containing mono linear16 PCM.
        """
        if chunk.ndim == 1:
            # Mono input — single channel
            pcm = self._float_to_int16(chunk)
            return [pcm.tobytes()]

        num_channels = chunk.shape[1]
        buffers = []
        for i in range(num_channels):
            pcm = self._float_to_int16(chunk[:, i])
            buffers.append(pcm.tobytes())
        return buffers

    @staticmethod
    def _float_to_int16(samples: np.ndarray) -> np.ndarray:
        """Convert float32 [-1.0, 1.0] samples to int16."""
        clipped = np.clip(samples, -1.0, 1.0)
        return (clipped * 32767).astype(np.int16)
