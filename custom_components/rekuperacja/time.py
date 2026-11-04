from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory

from .entity import RekuperacjaEntity

TIMES = ["weekday_day_start", "weekday_night_start", "weekend_day_start", "weekend_night_start"]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(SettingTime(entry.runtime_data, entry.entry_id, k) for k in TIMES)


class SettingTime(RekuperacjaEntity, TimeEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry_id, key):
        super().__init__(coordinator, entry_id, key)
        self._key = key

    @property
    def native_value(self) -> time:
        return self.coordinator.settings[self._key]

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_setting(self._key, value)
