from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.util import dt as dt_util

from .entity import RekuperacjaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([ActiveSource(c, entry.entry_id, "active_source"),
                        TargetCommand(c, entry.entry_id, "target")])


class ActiveSource(RekuperacjaEntity, SensorEntity):
    _attr_icon = "mdi:account-switch"

    @property
    def native_value(self) -> str:
        w = self.coordinator.winner
        if not self.coordinator.settings["automation"]:
            return "wylaczona"
        return w.source if w else "brak"

    @property
    def extra_state_attributes(self) -> dict:
        c = self.coordinator
        now = dt_util.utcnow()
        reqs = c.requests(now) + ([c.manual] if c.manual else [])
        return {
            "zadania": [
                {"zrodlo": r.source, "poziom": r.level, "komenda": r.command.describe(),
                 "do": dt_util.as_local(r.until).isoformat() if r.until else None}
                for r in reqs
            ],
            "do": dt_util.as_local(c.winner.until).isoformat() if c.winner and c.winner.until else None,
        }


class TargetCommand(RekuperacjaEntity, SensorEntity):
    _attr_icon = "mdi:fan"

    @property
    def native_value(self) -> str | None:
        w = self.coordinator.winner
        return w.command.describe() if w else None
