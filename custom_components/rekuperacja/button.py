from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .entity import RekuperacjaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([Btn(c, entry.entry_id, "boost", "async_boost", "mdi:fan-plus"),
                        Btn(c, entry.entry_id, "resume", "async_resume_automation", "mdi:restore")])


class Btn(RekuperacjaEntity, ButtonEntity):
    def __init__(self, coordinator, entry_id, key, method, icon):
        super().__init__(coordinator, entry_id, key)
        self._method = method
        self._attr_icon = icon

    async def async_press(self) -> None:
        await getattr(self.coordinator, self._method)()
