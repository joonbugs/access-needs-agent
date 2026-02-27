#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def main() -> int:
    pending_dir = Path("input") / "pending"

    for file_path in sorted(pending_dir.iterdir(), key=lambda p: p.name):
        with file_path.open("r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)

        print(f"From {file_path.name} agent {data['speaker']} said {data['text']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

