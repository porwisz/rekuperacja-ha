"""Wybór zwycięskiego żądania: ręczne nadpisanie > najwyższy poziom."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Command:
    """To, co wysyłamy do wentylatora: albo procent, albo preset."""

    percentage: int | None = None
    preset: str | None = None

    def describe(self) -> str:
        return self.preset if self.preset else f"{self.percentage}%"


@dataclass
class Request:
    source: str
    level: int
    command: Command
    until: datetime | None = None
    created: datetime | None = field(default=None, compare=False)

    def active(self, now: datetime) -> bool:
        return self.until is None or self.until > now


def resolve(requests: list[Request], now: datetime, manual: Request | None = None) -> Request | None:
    """Aktywne ręczne nadpisanie wygrywa zawsze; potem maksimum poziomu.

    Przy remisie wygrywa żądanie czasowe (boost) przed bazowym.
    """
    if manual is not None and manual.active(now):
        return manual
    active = [r for r in requests if r.active(now)]
    if not active:
        return None
    return max(active, key=lambda r: (r.level, r.until is not None))
