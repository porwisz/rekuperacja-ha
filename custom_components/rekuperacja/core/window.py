"""Okno czasowe próbek: zmiana wartości (ostatnia − pierwsza) w ostatnich N sekundach."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta


class ChangeWindow:
    def __init__(self, max_age: timedelta) -> None:
        self.max_age = max_age
        self._samples: deque[tuple[datetime, float]] = deque()

    def add(self, t: datetime, value: float) -> None:
        self._samples.append((t, value))
        self._prune(t)

    def _prune(self, now: datetime) -> None:
        while self._samples and now - self._samples[0][0] > self.max_age:
            self._samples.popleft()

    def change(self, now: datetime) -> float:
        self._prune(now)
        if len(self._samples) < 2:
            return 0.0
        return self._samples[-1][1] - self._samples[0][1]
