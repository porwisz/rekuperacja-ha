from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime

from .entity import RekuperacjaEntity

# klucz: (min, max, krok, jednostka)
NUMBERS = {
    "day_percentage": (5, 100, 5, PERCENTAGE),  # firmware: 20 biegów co 5%
    "manual_minutes": (5, 480, 5, UnitOfTime.MINUTES),
    "boost_minutes": (5, 180, 5, UnitOfTime.MINUTES),
    "shower_after_minutes": (0, 120, 5, UnitOfTime.MINUTES),
    "airing_minutes": (5, 120, 5, UnitOfTime.MINUTES),
    "airing_percentage": (5, 100, 5, PERCENTAGE),
}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(SettingNumber(entry.runtime_data, entry.entry_id, k, *v) for k, v in NUMBERS.items())


class SettingNumber(RekuperacjaEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry_id, key, lo, hi, step, unit):
        super().__init__(coordinator, entry_id, key)
        self._key = key
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float:
        return self.coordinator.settings[self._key]

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_setting(self._key, int(value))
