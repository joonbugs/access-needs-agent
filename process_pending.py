#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict


def main() -> str:
    pending_dir = Path("input") / "pending"
    processed_dir = Path("input") / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    for file_path in sorted(pending_dir.iterdir(), key=lambda p: p.name):
        if file_path.suffix.lower() != ".json":
            print(f"skipping {file_path.name}: not a JSON file")
            continue

        with file_path.open("r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)

        file_name = file_path.name
        print(f"From {file_name} agent {data['speaker']} said {data['text']}")
        shutil.move(str(file_path), str(processed_dir / file_name))

    return "Done"


if __name__ == "__main__":
    raise SystemExit(main())

