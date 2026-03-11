from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional


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


@dataclass(frozen=True)
class Caption:
    seq: int
    start_ms: int
    end_ms: int
    speaker: str
    text: str


_TIMECODE_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2},\d{3})(?:\s+.*)?$"
)


def validate_file_level(file_path: Path, pending_dir: Path) -> None:
    try:
        if not file_path.exists():
            raise ValidationError("file-level", file_path, "File does not exist")
        if not file_path.is_file():
            raise ValidationError("file-level", file_path, "Path is not a regular file")
        if file_path.suffix.lower() != ".srt":
            raise ValidationError("file-level", file_path, "File is not a .srt file")

        # Safety check: ensure the file is inside the pending folder.
        file_path.resolve().relative_to(pending_dir.resolve())

        with file_path.open("r", encoding="utf-8") as f:
            f.read(1)
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError("file-level", file_path, "File is not readable", cause=e)


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


def _parse_timestamp_to_ms(ts: str) -> int:
    # Format: HH:MM:SS,mmm
    hh, mm, rest = ts.split(":")
    ss, mmm = rest.split(",")
    return (int(hh) * 3600 + int(mm) * 60 + int(ss)) * 1000 + int(mmm)


def _parse_speaker_and_text(text_lines: list[str]) -> tuple[str, str]:
    # SRT text may be multiple lines; collapse to a single printable string.
    text = " ".join([ln.strip() for ln in text_lines if ln.strip() != ""]).strip()
    if text.startswith("[") and "]" in text:
        end = text.find("]")
        speaker = text[1:end].strip()
        rest = text[end + 1 :].strip()
        return speaker, rest
    return "", text


def parse_and_validate_srt(file_path: Path) -> list[Caption]:
    try:
        raw = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ValidationError("schema-level", file_path, "Could not read file as UTF-8 text", cause=e)

    blocks = list(_iter_srt_blocks(raw.splitlines()))
    if not blocks:
        raise ValidationError("schema-level", file_path, "SRT contains no caption blocks")

    captions: list[Caption] = []
    expected_seq = 1

    for block in blocks:
        if len(block) < 3:
            raise ValidationError(
                "schema-level",
                file_path,
                "Each SRT block must have: sequence line, timecode line, and at least one text line",
            )

        # 1) sequence
        seq_str = block[0].strip()
        try:
            seq = int(seq_str)
        except Exception as e:
            raise ValidationError("schema-level", file_path, f"Sequence must be an integer, got '{seq_str}'", cause=e)
        if seq != expected_seq:
            raise ValidationError(
                "schema-level",
                file_path,
                f"Sequence numbers must be strictly sequential starting at 1 (expected {expected_seq}, got {seq})",
            )

        # 2) timecodes
        tc_line = block[1].strip()
        m = _TIMECODE_RE.match(tc_line)
        if not m:
            raise ValidationError(
                "schema-level",
                file_path,
                f"Invalid timecode line for seq {seq}: '{tc_line}' (expected 'HH:MM:SS,mmm --> HH:MM:SS,mmm')",
            )
        start_ms = _parse_timestamp_to_ms(m.group("start"))
        end_ms = _parse_timestamp_to_ms(m.group("end"))
        if end_ms <= start_ms:
            raise ValidationError(
                "schema-level",
                file_path,
                f"Invalid time range for seq {seq}: end must be after start",
            )

        # 3+) caption text (must include speaker tag and non-empty content)
        speaker, text = _parse_speaker_and_text(block[2:])
        if speaker.strip() == "":
            raise ValidationError(
                "schema-level",
                file_path,
                f"Missing speaker tag for seq {seq} (expected like '[agent] ...' or '[customer] ...')",
            )
        if text.strip() == "":
            raise ValidationError("schema-level", file_path, f"Empty caption text for seq {seq}")

        captions.append(Caption(seq=seq, start_ms=start_ms, end_ms=end_ms, speaker=speaker, text=text))
        expected_seq += 1

    print("Successfully validated")
    return captions

