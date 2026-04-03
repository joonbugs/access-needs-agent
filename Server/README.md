# Access Needs Agent — Multi-Channel ASR Pipeline

Real-time multi-channel audio transcription pipeline for an accessibility agent that monitors conversations for access-need violations.

Takes N microphone streams from a USB audio interface, sends each to Deepgram for transcription, and produces N+1 SRT transcript files (one per speaker + one unified speaker-labeled transcript). Designed to feed into a downstream LLM classifier for violation detection.

## Architecture

```
Mic 1 ─┐                          ┌─ Deepgram WS 1 ─┐
Mic 2 ─┤  Audio    Channel        ├─ Deepgram WS 2 ─┤  Transcript   ┌─ Speaker A.srt
Mic 3 ─┼─ Interface ─► Splitter ──┼─ Deepgram WS 3 ─┼─ Downmix ────┼─ Speaker B.srt
Mic 4 ─┘  (USB)                   └─ Deepgram WS 4 ─┘              ├─ ...
                                                                     └─ unified.srt
                                                        ↓
                                                   pending/ folder
                                                   (downstream watcher)
```

## Setup

**Requirements:** Python 3.11+, PortAudio

```bash
# macOS
brew install portaudio

# Create venv and install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
# Edit .env with your keys:
# - DEEPGRAM_API_KEY=...
# - OPENAI_API_KEY=...
```

Where should `.env` live?

- If you run commands from `Server/`, put it in `Server/.env`
- If you run from the repo root, put it in `<repo>/.env`

The backend code will try **both locations**.

## Usage

### File mode (pre-recorded multi-channel WAV)

```bash
# Real-time playback speed
python -m pipeline.main --input-file recording.wav

# As fast as possible (batch processing)
python -m pipeline.main --input-file recording.wav --fast
```

### Live mode (audio interface)

Edit `config.yaml` to set `audio.mode: "live"` and optionally set `audio.device_index`, then:

```bash
python -m pipeline.main
```

### CLI options

| Flag | Description |
|---|---|
| `--config PATH` | Config file (default: `config.yaml`) |
| `--input-file PATH` | Multi-channel WAV file (overrides config) |
| `--fast` | Skip real-time delay for file input |
| `--session-id ID` | Session identifier (auto-generated if omitted) |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Output

For a 4-speaker session, the pipeline writes to `output/` and `pending/`:

```
output/
├── session_abc123_Speaker_A.srt
├── session_abc123_Speaker_B.srt
├── session_abc123_Speaker_C.srt
├── session_abc123_Speaker_D.srt
└── session_abc123_unified.srt
```

The unified SRT has speaker labels:

```srt
1
00:00:00,000 --> 00:00:02,500
[Speaker A] Hello everyone, welcome.

2
00:00:02,100 --> 00:00:03,800
[Speaker B] Hi, thanks for having me.
```

Files are written atomically (tmp + rename) so downstream watchers never read partial files.

## Configuration

See `config.yaml` for all options. Key settings:

```yaml
audio:
  mode: "live"          # "live" or "file"
  channels: 4           # number of mic channels
  sample_rate: 16000

speakers:               # labels for each channel
  - "Speaker A"
  - "Speaker B"
  - "Speaker C"
  - "Speaker D"

asr:
  model: "nova-3"       # Deepgram model

downmix:
  ghost_confidence_threshold: 0.7  # suppress crosstalk below this

output:
  flush_interval: 15.0  # seconds between SRT writes
  pending_dir: "./pending"
```

## Project Structure

```
src/pipeline/
├── main.py              # Orchestrator + CLI
├── config.py            # Pydantic config model
├── audio/
│   ├── base.py          # AudioSource ABC
│   ├── live.py          # Live capture via sounddevice
│   ├── file.py          # Multi-channel WAV replay
│   └── splitter.py      # Channel split → per-channel PCM
├── asr/
│   ├── base.py          # ASRClient ABC
│   ├── deepgram_client.py  # Deepgram WebSocket client
│   └── types.py         # WordResult, UtteranceResult
├── transcript/
│   ├── per_speaker.py   # Per-channel accumulator
│   ├── downmix.py       # Merge N streams → unified timeline
│   └── vad_hook.py      # Pluggable VAD interface
└── output/
    └── srt_writer.py    # Atomic SRT file writer
```

## Testing

```bash
# Generate test fixtures
python scripts/generate_test_wav.py

# Run tests
pytest tests/ -v
```

## Integration with Downstream Processing

This pipeline is the "slow path" upstream component. It drops SRT files into a `pending/` directory that a downstream watcher picks up for LLM-based rule-violation detection (e.g., condescending language, ignoring stated access needs).

The `vad_hook.py` module exposes a `VADSignal` protocol for the "fast path" (local audio analysis) to plug into for improved ghost suppression. Until the fast path is built, a confidence-based heuristic handles crosstalk filtering.
