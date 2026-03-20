#!/usr/bin/env python3
"""Watches the pipeline's pending/ directory for SRT files and runs rule-violation detection."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .business_logic import run_business_logic
from .openai_service import OpenAIConfigError
from .pending_watcher import WatchConfig, watch_forever
from .srt_validation import ValidationError, parse_and_validate_srt, validate_file_level


def process_pending_once(*, pending_dir: Path, processed_dir: Path, failed_dir: Path) -> int:
    """Process .srt files in pending_dir. Returns the number of files attempted."""
    attempted = 0

    for file_path in sorted(pending_dir.iterdir(), key=lambda p: p.name):
        if file_path.suffix.lower() != ".srt":
            continue

        attempted += 1
        file_name = file_path.name
        try:
            validate_file_level(file_path, pending_dir=pending_dir)
            captions = parse_and_validate_srt(file_path)

            result = run_business_logic(file_name=file_name, captions=captions)
            print(f"Business result from {file_name}: {result.summary}")

            shutil.move(str(file_path), str(processed_dir / file_name))
        except ValidationError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            shutil.move(str(file_path), str(failed_dir / file_name))
        except OpenAIConfigError as e:
            print(f"ERROR: OpenAI configuration: {e}", file=sys.stderr)
            print("Fix your OpenAI setup and re-run; leaving files in pending.", file=sys.stderr)
            return attempted
        except Exception as e:
            print(f"ERROR: unexpected failure processing '{file_name}': {e}", file=sys.stderr)
            shutil.move(str(file_path), str(failed_dir / file_name))

    return attempted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch pending/ for SRT transcripts and process them.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously poll for new .srt files",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--pending-dir",
        type=Path,
        default=Path("pending"),
        help="Directory to watch for .srt files (default: ./pending)",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("processed"),
        help="Directory for successfully processed files (default: ./processed)",
    )
    parser.add_argument(
        "--failed-dir",
        type=Path,
        default=Path("failed"),
        help="Directory for failed files (default: ./failed)",
    )

    args = parser.parse_args(argv)

    pending_dir: Path = args.pending_dir
    processed_dir: Path = args.processed_dir
    failed_dir: Path = args.failed_dir
    pending_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    def _once() -> int:
        return process_pending_once(pending_dir=pending_dir, processed_dir=processed_dir, failed_dir=failed_dir)

    if not args.watch:
        _once()
        return 0

    try:
        watch_forever(_once, config=WatchConfig(poll_seconds=float(args.poll_seconds)))
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
