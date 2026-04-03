from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class WatchConfig:
    poll_seconds: float = 2.0


def watch_forever(process_once: Callable[[], int], *, config: WatchConfig) -> int:
    """Polling loop — process_once() returns the number of files handled."""
    while True:
        n = process_once()
        if n == 0:
            time.sleep(config.poll_seconds)
