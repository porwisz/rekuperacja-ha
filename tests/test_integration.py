from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.rekuperacja.const import DOMAIN

FAN = "fan.rekuperator"
DAY = dt_util.as_utc(dt_util.parse_datetime("2026-11-04T12:00:00+01:00"))


async def _setup(hass: HomeAssistant, freezer):
    await hass.config.async_set_time_zone("Europe/Warsaw")
    freezer.move_to(DAY)
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall):
        calls.append(call)
        attrs = {"percentage": call.data.get("percentage"), "preset_mode": call.data.get("preset_mode")}
        hass.states.async_set(FAN, "on", attrs)

    hass.services.async_register("fan", "set_percentage", record)
    hass.services.async_register("fan", "set_preset_mode", record)
    hass.states.async_set(FAN, "on", {"percentage": 60, "preset_mode": None})
    entry = MockConfigEntry(domain=DOMAIN, data={"fan_entity": FAN})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return calls, entry


async def test_schedule_and_boost(hass, freezer):
    calls, _ = await _setup(hass, freezer)
    assert calls[-1].data["percentage"] == 40  # dzień
    await hass.services.async_call(DOMAIN, "request", {"source": "prysznic", "percentage": 100, "minutes": 10}, blocking=True)
    assert calls[-1].data["percentage"] == 100
    freezer.tick(timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls[-1].data["percentage"] == 40


async def test_night_uses_sleep_preset(hass, freezer):
    calls, _ = await _setup(hass, freezer)
    freezer.move_to(DAY.replace(hour=22))  # 23:00 lokalnie
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls[-1].data["preset_mode"] == "Sen"


async def test_manual_override(hass, freezer):
    calls, _ = await _setup(hass, freezer)
    freezer.tick(timedelta(seconds=30))
    hass.states.async_set(FAN, "on", {"percentage": 80, "preset_mode": None})  # z panelu
    await hass.async_block_till_done()
    assert hass.states.get("sensor.rekuperacja_active_request").state == "reczne"
    n = len(calls)
    await hass.services.async_call(DOMAIN, "request", {"source": "x", "percentage": 100, "minutes": 5}, blocking=True)
    assert len(calls) == n  # ręczne wygrywa
    await hass.services.async_call("button", "press", {"entity_id": "button.rekuperacja_resume_automation"}, blocking=True)
    assert calls[-1].data["percentage"] == 100


async def test_automation_off(hass, freezer):
    calls, _ = await _setup(hass, freezer)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.rekuperacja_automation"}, blocking=True)
    n = len(calls)
    await hass.services.async_call(DOMAIN, "request", {"source": "x", "percentage": 100}, blocking=True)
    assert len(calls) == n
