from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .entity import RekuperacjaEntity

SWITCHES = {"automation": None, "schedule_enabled": EntityCategory.CONFIG}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        SettingSwitch(entry.runtime_data, entry.entry_id, k, cat) for k, cat in SWITCHES.items()
    )


class SettingSwitch(RekuperacjaEntity, SwitchEntity):
    def __init__(self, coordinator, entry_id, key, category):
        super().__init__(coordinator, entry_id, key)
        self._key = key
        self._attr_entity_category = category

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.settings[self._key])

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_setting(self._key, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_setting(self._key, False)
