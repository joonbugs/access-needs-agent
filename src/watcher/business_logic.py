from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .openai_service import generate_text
from .srt_validation import Caption


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
        "Task: Write 3 bullet points summarizing the conversation.\n"
        "Transcript:\n"
        f"{transcript}\n"
    )


def run_business_logic(file_name: str, captions: Sequence[Caption]) -> BusinessResult:
    """Business layer entry point."""
    prompt = _build_prompt(file_name=file_name, captions=captions)
    summary = generate_text(prompt, model="gpt-4o-mini")
    return BusinessResult(summary=summary)
