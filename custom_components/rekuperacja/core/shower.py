"""Wykrywanie prysznica: przepływ wody i spadek temperatury CWU w oknie."""

from __future__ import annotations

from datetime import datetime, timedelta

from .window import ChangeWindow


class ShowerDetector:
    def __init__(self, window_min: float = 3, min_liters: float = 15, min_drop_c: float = 2) -> None:
        age = timedelta(minutes=window_min)
        self.water = ChangeWindow(age)
        self.cwu = ChangeWindow(age)
        self.min_liters = min_liters
        self.min_drop_c = min_drop_c

    def add_water_liters(self, t: datetime, liters_total: float) -> None:
        self.water.add(t, liters_total)

    def add_cwu(self, t: datetime, celsius: float) -> None:
        self.cwu.add(t, celsius)

    def detected(self, now: datetime) -> bool:
        return self.water.change(now) >= self.min_liters and self.cwu.change(now) <= -self.min_drop_c
