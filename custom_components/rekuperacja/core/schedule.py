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


def next_switch(now: datetime, settings: dict) -> datetime:
    """Najbliższa zmiana dzień/noc po `now` (now — lokalny, świadomy strefy)."""
    from datetime import timedelta

    best = None
    for d in range(0, 3):
        day = (now + timedelta(days=d)).date()
        prefix = "weekend" if day.weekday() >= 5 else "weekday"
        for key in ("day_start", "night_start"):
            t: time = settings[f"{prefix}_{key}"]
            cand = datetime.combine(day, t, tzinfo=now.tzinfo)
            if cand > now and (best is None or cand < best):
                best = cand
    return best


def airing_window(now: datetime, settings: dict) -> tuple[str, datetime] | None:
    """Aktywne przewietrzanie: ("rano" | "wieczor", koniec okna) albo None.

    Rano: `airing_minutes` od początku dnia; wieczór: `airing_minutes` przed początkiem nocy.
    Godziny brane z harmonogramu snu (osobno pn–pt i weekend).
    """
    from datetime import timedelta

    length = timedelta(minutes=int(settings["airing_minutes"]))
    if length <= timedelta(0):
        return None
    for d in (-1, 0, 1):  # okna mogą przechodzić przez północ
        day = (now + timedelta(days=d)).date()
        prefix = "weekend" if day.weekday() >= 5 else "weekday"
        if settings["airing_morning"]:
            start = datetime.combine(day, settings[f"{prefix}_day_start"], tzinfo=now.tzinfo)
            if start <= now < start + length:
                return "rano", start + length
        if settings["airing_evening"]:
            end = datetime.combine(day, settings[f"{prefix}_night_start"], tzinfo=now.tzinfo)
            if end - length <= now < end:
                return "wieczor", end
    return None
