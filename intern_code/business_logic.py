from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from openai_service import generate_text
from srt_validation import Caption


@dataclass(frozen=True)
class BusinessResult:
    summary: str


def _build_prompt(file_name: str, captions: Sequence[Caption]) -> str:
    lines: list[str] = []
    for cap in captions:
        lines.append(f"{cap.speaker}: {cap.text}")
    transcript = "\n".join(lines)
    return (
        "You are analyzing a transcript.\n"
        f"File: {file_name}\n"
        "Task: if the speaker says a color say COLOR, other wise None\n"
        "Transcript:\n"
        f"{transcript}\n"
    )


def run_business_logic(file_name: str, captions: Sequence[Caption]) -> BusinessResult:
    """
    Business layer entry point.

    - Input: validated transcript captions
    - Output: whatever your app needs next (for now: a summary)
    """
    prompt = _build_prompt(file_name=file_name, captions=captions)
    summary = generate_text(prompt, model="gpt-4o-mini")
    return BusinessResult(summary=summary)

