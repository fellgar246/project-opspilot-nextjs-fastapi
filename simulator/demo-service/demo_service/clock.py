from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class LogicalClock:
    """Logical clock used for causal coherence across signals.

    Wall-clock is used by default. In evaluation mode, callers can advance
    ``offset_seconds`` so metrics, logs, deployments and commits share one timeline.
    """

    _base_wall: float = field(default_factory=time.time)
    _offset_seconds: float = 0.0
    _lock: Lock = field(default_factory=Lock)

    def now(self) -> float:
        with self._lock:
            return time.time() + self._offset_seconds

    def now_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.now()))

    def advance(self, seconds: float) -> float:
        with self._lock:
            self._offset_seconds += seconds
            return time.time() + self._offset_seconds

    def set_offset(self, offset_seconds: float) -> float:
        with self._lock:
            self._offset_seconds = offset_seconds
            return time.time() + self._offset_seconds

    def reset(self) -> None:
        with self._lock:
            self._base_wall = time.time()
            self._offset_seconds = 0.0

    @property
    def offset_seconds(self) -> float:
        with self._lock:
            return self._offset_seconds


clock = LogicalClock()
