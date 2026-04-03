"""Pipeline configuration loaded from YAML + environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class AudioConfig(BaseModel):
    mode: str = "file"
    device_index: Optional[int] = None
    sample_rate: int = 16000
    channels: int = 4
    chunk_size: int = 4096
    file_path: Optional[str] = None
    file_playback_speed: str = "realtime"


class ASRConfig(BaseModel):
    provider: str = "deepgram"
    api_key: str = Field(default_factory=lambda: os.environ.get("DEEPGRAM_API_KEY", ""))
    model: str = "nova-3"
    language: str = "en-US"
    interim_results: bool = True
    smart_format: bool = True
    utterance_end_ms: int = 1500
    endpointing_ms: int = 300
    reconnect_attempts: int = 3
    reconnect_backoff_base: float = 1.0


class DownmixConfig(BaseModel):
    ghost_confidence_threshold: float = 0.7
    overlap_strategy: str = "separate"


class OutputConfig(BaseModel):
    output_dir: str = "./output"
    pending_dir: str = "./pending"
    flush_interval: float = 15.0
    write_per_speaker: bool = True
    write_unified: bool = True


class PipelineConfig(BaseModel):
    session_id: str = "meeting_001"
    audio: AudioConfig = AudioConfig()
    speakers: list[str] = Field(default_factory=lambda: ["Speaker A", "Speaker B", "Speaker C", "Speaker D"])
    asr: ASRConfig = ASRConfig()
    downmix: DownmixConfig = DownmixConfig()
    output: OutputConfig = OutputConfig()

    @property
    def num_channels(self) -> int:
        return self.audio.channels


def load_config(path: str | Path = "config.yaml") -> PipelineConfig:
    """Load config from YAML file, falling back to defaults."""
    path = Path(path)
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return PipelineConfig(**data)
    return PipelineConfig()
