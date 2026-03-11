#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Iterator, Tuple


def _iter_srt_blocks(lines: Iterable[str]) -> Iterator[list[str]]:
    block: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if line.strip() == "":
            if block:
                yield block
                block = []
            continue
        block.append(line)
    if block:
        yield block


def _parse_speaker_and_text(content_lines: list[str]) -> Tuple[str, str]:
    text = " ".join([ln.strip() for ln in content_lines if ln.strip() != ""]).strip()
    if text.startswith("[") and "]" in text:
        end = text.find("]")
        speaker = text[1:end].strip()
        rest = text[end + 1 :].strip()
        return speaker, rest
    return "unknown", text


def main() -> int:
    pending_dir = Path("input") / "pending"
    processed_dir = Path("input") / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    for file_path in sorted(pending_dir.iterdir(), key=lambda p: p.name):
        if file_path.suffix.lower() != ".srt":
            continue

        with file_path.open("r", encoding="utf-8") as f:
            lines = list(f)

        file_name = file_path.name

        for block in _iter_srt_blocks(lines):
            # Expected SRT block shape:
            # 1) sequence number
            # 2) timecodes
            # 3+) subtitle text (we embed speaker like "[agent] hello")
            if len(block) < 3:
                continue
            sequence = block[0].strip()
            speaker, text = _parse_speaker_and_text(block[2:])
            print(f"From {file_name} seq {sequence} agent {speaker} said {text}")

        shutil.move(str(file_path), str(processed_dir / file_name))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

