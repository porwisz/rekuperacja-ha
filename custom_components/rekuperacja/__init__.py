"""Integracja Rekuperacja — automatyka wietrzenia nad encją fan z ESPHome."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .const import CONF_FAN, DOMAIN
from .coordinator import RekuperacjaCoordinator
from .core.arbiter import Command

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.TIME, Platform.SENSOR, Platform.BUTTON]

type RekuperacjaConfigEntry = ConfigEntry[RekuperacjaCoordinator]

REQUEST_SCHEMA = vol.Schema(
    {
        vol.Required("source"): cv.string,
        vol.Optional("percentage"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
        vol.Optional("preset"): cv.string,
        vol.Optional("minutes"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)
CANCEL_SCHEMA = vol.Schema({vol.Required("source"): cv.string})


def _coordinator(hass: HomeAssistant) -> RekuperacjaCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Integracja Rekuperacja nie jest załadowana")
    return entries[0].runtime_data


async def async_setup_entry(hass: HomeAssistant, entry: RekuperacjaConfigEntry) -> bool:
    coordinator = RekuperacjaCoordinator(hass, entry.data[CONF_FAN], dict(entry.options))
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start()

    from . import frontend, websocket

    websocket.async_register(hass)
    if hass.http is not None:
        await frontend.async_register(hass)

    async def handle_request(call: ServiceCall) -> None:
        pct, preset = call.data.get("percentage"), call.data.get("preset")
        if (pct is None) == (preset is None):
            raise ServiceValidationError("Podaj dokładnie jedno: percentage albo preset")
        await _coordinator(hass).async_request(
            call.data["source"], Command(pct, preset), call.data.get("minutes")
        )

    async def handle_cancel(call: ServiceCall) -> None:
        await _coordinator(hass).async_cancel(call.data["source"])

    hass.services.async_register(DOMAIN, "request", handle_request, REQUEST_SCHEMA)
    hass.services.async_register(DOMAIN, "cancel", handle_cancel, CANCEL_SCHEMA)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: RekuperacjaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RekuperacjaConfigEntry) -> bool:
    await entry.runtime_data.async_stop()
    hass.services.async_remove(DOMAIN, "request")
    hass.services.async_remove(DOMAIN, "cancel")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
