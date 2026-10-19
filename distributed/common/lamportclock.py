from __future__ import annotations

import threading


class LamportClock:
    def __init__(self, processId: str, startAt: int = 0) -> None:
        self.processId = processId
        self.counter = startAt
        self.guard = threading.Lock()

    def tick(self) -> int:
        with self.guard:
            self.counter += 1
            return self.counter

    def observe(self, received: int) -> int:
        with self.guard:
            self.counter = max(self.counter, received) + 1
            return self.counter

    def peek(self) -> int:
        with self.guard:
            return self.counter
