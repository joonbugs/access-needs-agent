#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from business_logic import run_business_logic
from openai_service import OpenAIConfigError
from srt_validation import ValidationError, parse_and_validate_srt, validate_file_level


def main() -> int:
    pending_dir = Path("input") / "pending"
    processed_dir = Path("input") / "processed"
    failed_dir = Path("input") / "failed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    for file_path in sorted(pending_dir.iterdir(), key=lambda p: p.name):
        if file_path.suffix.lower() != ".srt":
            continue

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
            # Config problems (missing key/deps) shouldn't mark transcripts as "failed".
            print(f"ERROR: OpenAI configuration: {e}", file=sys.stderr)
            print("Fix your OpenAI setup and re-run; leaving files in pending.", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"ERROR: unexpected failure processing '{file_name}': {e}", file=sys.stderr)
            shutil.move(str(file_path), str(failed_dir / file_name))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

