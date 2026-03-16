"""Quick mic test — records 3 seconds and reports audio levels."""

import numpy as np
import sounddevice as sd

DURATION = 3  # seconds
SAMPLE_RATE = 16000

print(f"Default input device: {sd.query_devices(kind='input')}")
print(f"\nRecording {DURATION}s of audio at {SAMPLE_RATE} Hz...")

audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
sd.wait()

peak = np.max(np.abs(audio))
rms = np.sqrt(np.mean(audio ** 2))

print(f"\nPeak amplitude: {peak:.6f}")
print(f"RMS level:      {rms:.6f}")

if peak < 0.001:
    print("\n⚠️  Audio is essentially SILENT.")
    print("   → Check: System Settings → Privacy & Security → Microphone")
    print("   → Make sure your Terminal app has microphone access enabled.")
else:
    print(f"\n✓ Mic is working! Peak={peak:.4f}, RMS={rms:.4f}")
