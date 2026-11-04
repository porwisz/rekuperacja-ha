"""Harmonogram dzień/noc z osobnymi godzinami na weekend."""

from __future__ import annotations

from datetime import datetime, time


def is_day(now: datetime, settings: dict) -> bool:
    weekend = now.weekday() >= 5
    prefix = "weekend" if weekend else "weekday"
    start: time = settings[f"{prefix}_day_start"]
    end: time = settings[f"{prefix}_night_start"]
    t = now.time()
    if start <= end:
        return start <= t < end
    return t >= start or t < end  # dzień przechodzi przez północ
