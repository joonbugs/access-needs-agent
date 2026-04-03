from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class WatchConfig:
    poll_seconds: float = 2.0


def watch_forever(process_once: Callable[[], int], *, config: WatchConfig) -> int:
    """
    Polling loop.

    - `process_once()` should process whatever is currently pending and return the
      number of files it processed (or attempted, depending on your semantics).
    - When there is nothing to do, we sleep for `poll_seconds`.
    """
    while True:
        n = process_once()
        if n == 0:
            time.sleep(config.poll_seconds)

