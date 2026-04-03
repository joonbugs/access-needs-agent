"""Pipeline orchestrator — ties audio capture, ASR, transcript downmix, and SRT output together."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import uuid
from pathlib import Path

from .asr.deepgram_client import DeepgramASRClient
from .asr.types import UtteranceResult
from .audio.base import AudioSource
from .audio.file import FileAudioSource
from .audio.live import LiveAudioSource
from .audio.splitter import ChannelSplitter
from .config import PipelineConfig, load_config
from .output.srt_writer import SRTWriter
from .transcript.downmix import TranscriptDownmixer
from .transcript.per_speaker import PerSpeakerTranscript
from .transcript.vad_hook import NullVAD

logger = logging.getLogger(__name__)


def create_audio_source(config: PipelineConfig) -> AudioSource:
    """Create the appropriate audio source based on config."""
    if config.audio.mode == "file":
        if not config.audio.file_path:
            raise ValueError("audio.file_path must be set when mode is 'file'")
        return FileAudioSource(
            file_path=config.audio.file_path,
            chunk_size=config.audio.chunk_size,
            playback_speed=config.audio.file_playback_speed,
        )
    elif config.audio.mode == "live":
        return LiveAudioSource(
            channels=config.audio.channels,
            sample_rate=config.audio.sample_rate,
            chunk_size=config.audio.chunk_size,
            device_index=config.audio.device_index,
        )
    else:
        raise ValueError(f"Unknown audio mode: {config.audio.mode}")


async def audio_pump(
    source: AudioSource,
    splitter: ChannelSplitter,
    asr_clients: list[DeepgramASRClient],
    shutdown: asyncio.Event,
) -> None:
    """Read audio from source, split channels, send to ASR clients."""
    async with source:
        async for chunk in source:
            if shutdown.is_set():
                break
            mono_buffers = splitter.split(chunk)
            for i, buf in enumerate(mono_buffers):
                if i < len(asr_clients):
                    await asr_clients[i].send_audio(buf)


async def collect_transcripts(
    asr_client: DeepgramASRClient,
    accumulator: PerSpeakerTranscript,
    shutdown: asyncio.Event,
) -> None:
    """Collect transcript results from one ASR client into the accumulator."""
    async for utterance in asr_client.results():
        if shutdown.is_set():
            break
        accumulator.add(utterance)
        if utterance.is_final:
            logger.info(
                "[%s] (final) %s", accumulator.speaker_label, utterance.transcript
            )
        else:
            logger.info(
                "[%s] (interim) %s", accumulator.speaker_label, utterance.transcript
            )


async def periodic_flush(
    interval: float,
    accumulators: list[PerSpeakerTranscript],
    downmixer: TranscriptDownmixer,
    writer: SRTWriter,
    config: PipelineConfig,
    shutdown: asyncio.Event,
) -> None:
    """Periodically write SRT files from accumulated transcripts."""
    while not shutdown.is_set():
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=interval)
            break  # shutdown was set
        except asyncio.TimeoutError:
            pass  # interval elapsed, do a flush

        total = sum(len(acc) for acc in accumulators)
        logger.info("Flush: %d utterances accumulated", total)

        # Write per-speaker SRTs
        if config.output.write_per_speaker:
            for acc in accumulators:
                entries = acc.to_srt_entries()
                if entries:
                    path = writer.write_per_speaker(
                        acc.channel_index, acc.speaker_label, entries
                    )
                    logger.info("Wrote per-speaker SRT: %s (%d entries)", path, len(entries))

        # Write unified SRT
        if config.output.write_unified:
            unified = await downmixer.merge(accumulators)
            if unified:
                path = writer.write_unified(unified)
                logger.info("Wrote unified SRT: %s (%d entries)", path, len(unified))


async def run(config: PipelineConfig) -> None:
    """Main pipeline execution."""
    shutdown = asyncio.Event()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown.set)

    # Create components
    splitter = ChannelSplitter()

    num_channels = config.num_channels
    speakers = config.speakers[:num_channels]
    # Pad speaker names if fewer than channels
    while len(speakers) < num_channels:
        speakers.append(f"Speaker {len(speakers) + 1}")

    asr_clients = [
        DeepgramASRClient(i, speakers[i], config.asr) for i in range(num_channels)
    ]
    accumulators = [
        PerSpeakerTranscript(i, speakers[i]) for i in range(num_channels)
    ]
    downmixer = TranscriptDownmixer(config=config.downmix, vad=NullVAD())
    writer = SRTWriter(
        output_dir=config.output.output_dir,
        pending_dir=config.output.pending_dir,
        session_id=config.session_id,
    )
    source = create_audio_source(config)

    # Connect all ASR clients
    logger.info("Connecting to Deepgram (%d channels)...", num_channels)
    for client in asr_clients:
        await client.connect()
    logger.info("All ASR clients connected")

    # Run concurrent tasks
    tasks = []
    try:
        tasks.append(asyncio.create_task(
            audio_pump(source, splitter, asr_clients, shutdown),
            name="audio_pump",
        ))
        for i in range(num_channels):
            tasks.append(asyncio.create_task(
                collect_transcripts(asr_clients[i], accumulators[i], shutdown),
                name=f"collector_{i}",
            ))
        tasks.append(asyncio.create_task(
            periodic_flush(
                config.output.flush_interval,
                accumulators,
                downmixer,
                writer,
                config,
                shutdown,
            ),
            name="flusher",
        ))

        # Wait for audio pump to finish (file mode) or shutdown signal (live mode)
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # If audio pump finished (file ended), do a final flush then shut down
        shutdown.set()
        if pending:
            await asyncio.wait(pending, timeout=5.0)
            for t in pending:
                if not t.done():
                    t.cancel()

    finally:
        # Final flush
        logger.info("Final flush...")
        if config.output.write_per_speaker:
            for acc in accumulators:
                entries = acc.to_srt_entries()
                if entries:
                    writer.write_per_speaker(acc.channel_index, acc.speaker_label, entries)

        if config.output.write_unified:
            unified = await downmixer.merge(accumulators)
            if unified:
                writer.write_unified(unified)

        # Close ASR clients
        for client in asr_clients:
            await client.close()

    logger.info("Pipeline finished")


def cli() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Multi-channel ASR pipeline")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config YAML file"
    )
    parser.add_argument(
        "--input-file", default=None, help="Multi-channel WAV file (overrides config)"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Process file as fast as possible (no real-time delay)",
    )
    parser.add_argument(
        "--session-id", default=None, help="Session ID (auto-generated if omitted)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = load_config(args.config)

    if args.input_file:
        config.audio.mode = "file"
        config.audio.file_path = args.input_file
    if args.fast:
        config.audio.file_playback_speed = "fast"
    if args.session_id:
        config.session_id = args.session_id
    elif config.session_id == "meeting_001":
        config.session_id = f"session_{uuid.uuid4().hex[:8]}"

    asyncio.run(run(config))


if __name__ == "__main__":
    cli()
