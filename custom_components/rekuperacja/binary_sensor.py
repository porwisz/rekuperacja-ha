from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import RekuperacjaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Shower(entry.runtime_data, entry.entry_id, "shower")])


class Shower(RekuperacjaEntity, BinarySensorEntity):
    _attr_icon = "mdi:shower"

    @property
    def available(self) -> bool:
        return self.coordinator.shower.configured

    @property
    def is_on(self) -> bool:
        return self.coordinator.shower.detected

    @property
    def extra_state_attributes(self) -> dict:
        from homeassistant.util import dt as dt_util

        d = self.coordinator.shower.detector
        now = dt_util.utcnow()
        return {"woda_l_okno": round(d.water.change(now), 1), "cwu_zmiana_okno": round(d.cwu.change(now), 1)}
