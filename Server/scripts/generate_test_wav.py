"""Generate multi-channel test WAV files for pipeline testing.

Creates a 4-channel WAV where each channel has a tone at a different frequency,
active at different time intervals to simulate turn-taking.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000
DURATION = 10.0  # seconds
NUM_CHANNELS = 4
OUTPUT_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def generate_tone(freq: float, start: float, end: float, total_duration: float) -> np.ndarray:
    """Generate a sine tone active during [start, end] within total_duration."""
    num_samples = int(total_duration * SAMPLE_RATE)
    t = np.linspace(0, total_duration, num_samples, endpoint=False)
    signal = np.sin(2 * np.pi * freq * t)
    # Apply time window — only active during [start, end]
    mask = (t >= start) & (t < end)
    signal *= mask.astype(np.float32)
    # Fade in/out to avoid clicks (10ms ramps)
    ramp = int(0.01 * SAMPLE_RATE)
    for i in range(num_samples):
        if mask[i]:
            # Find distance from edge
            left = i - int(start * SAMPLE_RATE)
            right = int(end * SAMPLE_RATE) - i - 1
            if left < ramp:
                signal[i] *= left / ramp
            if right < ramp:
                signal[i] *= right / ramp
    return signal.astype(np.float32) * 0.5  # reduce amplitude


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Each channel gets a different frequency and different active intervals
    # Simulates 4 speakers taking turns with some overlap
    channel_specs = [
        # (frequency, [(start, end), ...])
        (300, [(0.0, 2.5), (6.0, 8.0)]),   # Speaker A: talks early, then later
        (500, [(2.0, 4.5)]),                 # Speaker B: talks in the middle (overlaps briefly with A)
        (700, [(4.0, 6.5)]),                 # Speaker C: talks next (overlaps briefly with B)
        (900, [(8.0, 10.0)]),                # Speaker D: talks at the end
    ]

    channels = []
    for freq, intervals in channel_specs:
        channel = np.zeros(int(DURATION * SAMPLE_RATE), dtype=np.float32)
        for start, end in intervals:
            channel += generate_tone(freq, start, end, DURATION)
        channels.append(channel)

    # Stack into multi-channel array (samples, channels)
    multichannel = np.column_stack(channels)

    output_path = OUTPUT_DIR / "4ch_test.wav"
    sf.write(str(output_path), multichannel, SAMPLE_RATE)
    print(f"Generated: {output_path}")
    print(f"  Duration: {DURATION}s, Channels: {NUM_CHANNELS}, Sample rate: {SAMPLE_RATE} Hz")
    print(f"  Channel 0 (300 Hz): 0.0-2.5s, 6.0-8.0s")
    print(f"  Channel 1 (500 Hz): 2.0-4.5s")
    print(f"  Channel 2 (700 Hz): 4.0-6.5s")
    print(f"  Channel 3 (900 Hz): 8.0-10.0s")


if __name__ == "__main__":
    main()
