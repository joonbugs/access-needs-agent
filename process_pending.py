#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


MAX_BYTES_DEFAULT = 5 * 1024 * 1024  # 5 MB

# used for creating custom error type with structured info
@dataclass(frozen=True)
class ValidationError(Exception):
    stage: str
    file_path: Path
    message: str
    cause: Optional[BaseException] = None

    def __str__(self) -> str:
        base = f"{self.stage} validation failed for '{self.file_path.name}': {self.message}"
        if self.cause is not None:
            return f"{base} (cause: {type(self.cause).__name__}: {self.cause})"
        return base

# changes whatever timestamp into ISO 8601 format
def _parse_iso8601(ts: str) -> datetime:
    # Accept common transcript timestamps like "2026-02-22T15:43:10Z".
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

# checks if the child path is within the parent path
def _is_within_dir(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False

# runs several checks with the file before proceeding 
def validate_file_level(file_path: Path, pending_dir: Path, max_bytes: int) -> None:
    if not file_path.exists():
        raise ValidationError(
            stage="file-level",
            file_path=file_path,
            message="File does not exist",
        )
    if not file_path.is_file():
        raise ValidationError(
            stage="file-level",
            file_path=file_path,
            message="Path is not a regular file",
        )
    if not _is_within_dir(file_path, pending_dir):
        raise ValidationError(
            stage="file-level",
            file_path=file_path,
            message=f"File is not inside pending folder '{pending_dir}'",
        )
    if file_path.suffix.lower() != ".json":
        raise ValidationError(
            stage="file-level",
            file_path=file_path,
            message="File is not a .json file",
        )

    try:
        size = file_path.stat().st_size
    except OSError as e:
        raise ValidationError(
            stage="file-level",
            file_path=file_path,
            message="Could not stat file size",
            cause=e,
        )
    if size > max_bytes:
        raise ValidationError(
            stage="file-level",
            file_path=file_path,
            message=f"File too large ({size} bytes) exceeds limit ({max_bytes} bytes / ~5MB)",
        )

    try:
        with file_path.open("rb") as f:
            f.read(1)
    except OSError as e:
        raise ValidationError(
            stage="file-level",
            file_path=file_path,
            message="File is not readable",
            cause=e,
        )

#opens the JSOn file and checks if there's the right structure and content
def validate_schema_level(file_path: Path) -> Dict[str, Any]:
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message=f"JSON syntax error at line {e.lineno}, column {e.colno}",
            cause=e,
        )
    except OSError as e:
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message="Could not open/read file as UTF-8 text",
            cause=e,
        )

    if not isinstance(data, dict):
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message="Top-level JSON must be an object/dict",
        )

    required: List[Tuple[str, type]] = [
        ("session_id", str),
        ("chunk_id", int),
        ("created_at", str),
        ("text", str),
        ("speaker", str),
    ]

    missing = [k for k, _t in required if k not in data]
    if missing:
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message=f"Missing required field(s): {', '.join(missing)}",
        )

    for k, t in required:
        v = data.get(k)
        if v is None:
            raise ValidationError(
                stage="schema-level",
                file_path=file_path,
                message=f"Field '{k}' must not be null",
            )
        if not isinstance(v, t):
            raise ValidationError(
                stage="schema-level",
                file_path=file_path,
                message=f"Field '{k}' must be {t.__name__}, got {type(v).__name__}",
            )

    if data["session_id"].strip() == "":
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message="Field 'session_id' must not be empty",
        )
    if data["chunk_id"] < 1:
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message="Field 'chunk_id' must be >= 1",
        )
    if data["speaker"].strip() == "":
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message="Field 'speaker' must not be empty",
        )
    if data["text"].strip() == "":
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message="Field 'text' must not be empty",
        )

    try:
        _parse_iso8601(data["created_at"])
    except Exception as e:
        raise ValidationError(
            stage="schema-level",
            file_path=file_path,
            message="Field 'created_at' must be ISO-8601 (e.g. 2026-02-22T15:43:10Z)",
            cause=e,
        )

    return data


def business_process(file_path: Path, data: Dict[str, Any]) -> None:
    # Required output format from user prompt.
    speaker = str(data["speaker"])
    text = str(data["text"]).replace("\n", " ").strip()
    print(f"From {file_path.name} agent {speaker} said {text}")


#responsible for moving a file from one location to another 
def safe_move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_path = dst_dir / src.name
    # Avoid overwrite by suffixing if needed.
    if dst_path.exists():
        stem, suffix = src.stem, src.suffix
        for i in range(1, 10_000):
            candidate = dst_dir / f"{stem}__dup{i:04d}{suffix}"
            if not candidate.exists():
                dst_path = candidate
                break
    return Path(shutil.move(str(src), str(dst_path)))

#gets a lit of all the files in folder and returns in alphabetical order 
#TODO: will need to change this later
def list_pending_json(pending_dir: Path) -> List[Path]:
    if not pending_dir.exists():
        return []
    return sorted([p for p in pending_dir.iterdir() if p.is_file()])



#validates all file and creates a queue of valid items
@dataclass(frozen=True)
class ParsedItem:
    file_path: Path
    session_id: str
    chunk_id: int
    created_at: datetime
    data: Dict[str, Any]


def build_queue(
    files: Iterable[Path],
    pending_dir: Path,
    max_bytes: int,
    failed_dir: Path,
) -> List[ParsedItem]:
    items: List[ParsedItem] = []

    for fp in files:
        try:
            validate_file_level(fp, pending_dir=pending_dir, max_bytes=max_bytes)
            data = validate_schema_level(fp)
            created_at = _parse_iso8601(data["created_at"])
            items.append(
                ParsedItem(
                    file_path=fp,
                    session_id=str(data["session_id"]),
                    chunk_id=int(data["chunk_id"]),
                    created_at=created_at,
                    data=data,
                )
            )
        except ValidationError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            try:
                safe_move(fp, failed_dir)
            except Exception as move_err:
                print(
                    f"ERROR: failed to move '{fp.name}' to failed folder: {move_err}",
                    file=sys.stderr,
                )
        except Exception as e:
            ve = ValidationError(
                stage="schema-level",
                file_path=fp,
                message="Unexpected error while validating/parsing JSON",
                cause=e,
            )
            print(f"ERROR: {ve}", file=sys.stderr)
            #TODO: We need to figure something out for this too (if the file can't even be moved to failed)
            try:
                safe_move(fp, failed_dir)
            except Exception as move_err:
                print(
                    f"ERROR: failed to move '{fp.name}' to failed folder: {move_err}",
                    file=sys.stderr,
                )

    # Sort primarily by session and chunk order; use created_at for stability.
    #TODO: will need to come back to this maybe
    items.sort(key=lambda it: (it.session_id, it.chunk_id, it.created_at, it.file_path.name))
    return items


def process_queue_strict_order(
    items: List[ParsedItem],
    processed_dir: Path,
    failed_dir: Path,
) -> int:
    """
    Strictly processes per-session in increasing chunk_id with no gaps.
    If a gap is detected (e.g., chunk 3 exists but chunk 2 missing), later chunks
    for that session are left in pending until the missing chunk arrives.
    """
    processed_count = 0
    expected_next: Dict[str, int] = {}

    for it in items:
        exp = expected_next.get(it.session_id, 1)
        if it.chunk_id != exp:
            print(
                f"INFO: skipping '{it.file_path.name}' for session '{it.session_id}' "
                f"because expected chunk_id {exp} but found {it.chunk_id}. "
                "Leaving file in pending.",
                file=sys.stderr,
            )
            continue

        try:
            business_process(it.file_path, it.data)
            safe_move(it.file_path, processed_dir)
            processed_count += 1
            expected_next[it.session_id] = exp + 1
        except Exception as e:
            ve = ValidationError(
                stage="business-level",
                file_path=it.file_path,
                message="Unexpected error during business processing",
                cause=e,
            )
            print(f"ERROR: {ve}", file=sys.stderr)
            try:
                safe_move(it.file_path, failed_dir)
            except Exception as move_err:
                print(
                    f"ERROR: failed to move '{it.file_path.name}' to failed folder: {move_err}",
                    file=sys.stderr,
                )
    return processed_count


def process_once(
    pending_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    max_bytes: int,
    strict_order: bool,
) -> int:
    files = list_pending_json(pending_dir)
    if not files:
        return 0

    items = build_queue(
        files=files,
        pending_dir=pending_dir,
        max_bytes=max_bytes,
        failed_dir=failed_dir,
    )
    if not items:
        return 0

    if strict_order:
        return process_queue_strict_order(
            items=items,
            processed_dir=processed_dir,
            failed_dir=failed_dir,
        )

    processed_count = 0
    for it in items:
        try:
            business_process(it.file_path, it.data)
            safe_move(it.file_path, processed_dir)
            processed_count += 1
        except Exception as e:
            ve = ValidationError(
                stage="business-level",
                file_path=it.file_path,
                message="Unexpected error during business processing",
                cause=e,
            )
            print(f"ERROR: {ve}", file=sys.stderr)
            try:
                safe_move(it.file_path, failed_dir)
            except Exception as move_err:
                print(
                    f"ERROR: failed to move '{it.file_path.name}' to failed folder: {move_err}",
                    file=sys.stderr,
                )
    return processed_count


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate, parse, and process transcript-chunk JSON files from input/pending/."
    )
    parser.add_argument("--pending-dir", default="input/pending", help="Pending input directory")
    parser.add_argument("--processed-dir", default="input/processed", help="Processed output directory")
    parser.add_argument("--failed-dir", default="input/failed", help="Failed output directory")
    parser.add_argument(
        "--max-mb",
        type=int,
        default=5,
        help="Max file size in MB (files larger than this are rejected)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process current pending files once, then exit",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously poll and process pending files",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="Polling interval when --watch is enabled",
    )
    parser.add_argument(
        "--strict-order",
        action="store_true",
        default=True,
        help="Process per session strictly in chunk_id order with no gaps (default: true)",
    )
    parser.add_argument(
        "--no-strict-order",
        action="store_true",
        help="Disable strict per-session ordering (processes all available chunks in sorted order)",
    )

    args = parser.parse_args(argv)

    pending_dir = Path(args.pending_dir)
    processed_dir = Path(args.processed_dir)
    failed_dir = Path(args.failed_dir)

    max_bytes = int(args.max_mb) * 1024 * 1024

    strict_order = bool(args.strict_order) and not bool(args.no_strict_order)

    if args.watch and args.once:
        print("ERROR: choose only one of --once or --watch", file=sys.stderr)
        return 2
    if not args.watch and not args.once:
        # Default behavior: once.
        args.once = True

    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)
    pending_dir.mkdir(parents=True, exist_ok=True)

    if args.once:
        n = process_once(
            pending_dir=pending_dir,
            processed_dir=processed_dir,
            failed_dir=failed_dir,
            max_bytes=max_bytes,
            strict_order=strict_order,
        )
        print(f"Done. Processed {n} file(s).")
        return 0

    # Watch mode
    print(
        "Watching for new pending transcript chunks...\n"
        f"- pending:   {pending_dir}\n"
        f"- processed: {processed_dir}\n"
        f"- failed:    {failed_dir}\n"
        f"- strict chunk order per session: {strict_order}\n"
        f"- max bytes: {max_bytes}\n"
        f"- poll seconds: {args.poll_seconds}\n"
    )
    while True:
        try:
            n = process_once(
                pending_dir=pending_dir,
                processed_dir=processed_dir,
                failed_dir=failed_dir,
                max_bytes=max_bytes,
                strict_order=strict_order,
            )
            if n == 0:
                time.sleep(args.poll_seconds)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())

