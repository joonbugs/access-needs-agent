"""Tests for the channel splitter."""

import numpy as np

from pipeline.audio.splitter import ChannelSplitter


class TestChannelSplitter:
    def setup_method(self):
        self.splitter = ChannelSplitter()

    def test_splits_multichannel_into_separate_buffers(self):
        # 4 channels, 100 frames
        chunk = np.random.rand(100, 4).astype(np.float32) * 2 - 1
        buffers = self.splitter.split(chunk)

        assert len(buffers) == 4
        for buf in buffers:
            # Each buffer should be 100 frames * 2 bytes (int16)
            assert len(buf) == 200

    def test_mono_input(self):
        chunk = np.random.rand(100).astype(np.float32) * 2 - 1
        buffers = self.splitter.split(chunk)

        assert len(buffers) == 1
        assert len(buffers[0]) == 200

    def test_preserves_channel_isolation(self):
        # Channel 0 is all zeros, Channel 1 is all ones (clipped to 1.0)
        chunk = np.zeros((100, 2), dtype=np.float32)
        chunk[:, 1] = 1.0

        buffers = self.splitter.split(chunk)

        ch0 = np.frombuffer(buffers[0], dtype=np.int16)
        ch1 = np.frombuffer(buffers[1], dtype=np.int16)

        assert np.all(ch0 == 0)
        assert np.all(ch1 == 32767)

    def test_clips_out_of_range(self):
        chunk = np.array([[2.0], [-2.0]], dtype=np.float32)
        buffers = self.splitter.split(chunk)

        samples = np.frombuffer(buffers[0], dtype=np.int16)
        assert samples[0] == 32767
        assert samples[1] == -32767
