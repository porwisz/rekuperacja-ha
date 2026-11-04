"""Serwowanie karty Lovelace razem z integracją."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

URL = f"/{DOMAIN}_static"
JS = "rekuperacja-card.js"
_DATA_KEY = f"{DOMAIN}_frontend"


async def async_register(hass: HomeAssistant) -> None:
    if hass.data.get(_DATA_KEY):
        return
    path = Path(__file__).parent / "frontend"
    version = (await async_get_integration(hass, DOMAIN)).version
    await hass.http.async_register_static_paths([StaticPathConfig(URL, str(path), False)])
    frontend.add_extra_js_url(hass, f"{URL}/{JS}?v={version}")
    hass.data[_DATA_KEY] = True
