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
    if freezer is not None:
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


async def test_shower_boost(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Warsaw")
    freezer.move_to(DAY)
    calls = []

    async def record(call):
        calls.append(call)
        hass.states.async_set(FAN, "on", {"percentage": call.data.get("percentage"), "preset_mode": None})

    hass.services.async_register("fan", "set_percentage", record)
    hass.services.async_register("fan", "set_preset_mode", record)
    hass.states.async_set(FAN, "on", {"percentage": 40, "preset_mode": None})
    W, H = "sensor.woda", "sensor.cwu"
    hass.states.async_set(W, "100.000", {"unit_of_measurement": "m³"})
    hass.states.async_set(H, "49.5")
    entry = MockConfigEntry(domain=DOMAIN, data={"fan_entity": FAN},
                            options={"water_entity": W, "cwu_entity": H, "shower_min_liters": 15, "shower_min_drop": 2})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for i in range(1, 7):
        freezer.tick(timedelta(seconds=30))
        hass.states.async_set(W, f"{100 + i * 0.004:.3f}", {"unit_of_measurement": "m³"})
        hass.states.async_set(H, str(49.5 - i * 0.5))
        await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.rekuperacja_shower").state == "on"
    assert calls[-1].data["percentage"] == 100
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.rekuperacja_shower").state == "off"
    assert calls[-1].data["percentage"] == 100  # nadal wietrzy (20 min po)
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls[-1].data["percentage"] == 40


async def test_options_flow(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"fan_entity": FAN}, options={})
    entry.add_to_hass(hass)
    hass.states.async_set(FAN, "on", {"percentage": 40, "preset_mode": None})
    assert await hass.config_entries.async_setup(entry.entry_id)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"water_entity": "sensor.a", "cwu_entity": "sensor.b", "shower_min_liters": 10, "shower_min_drop": 1}
    )
    assert r["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.runtime_data.shower.water == "sensor.a"


async def test_websocket(hass, hass_ws_client):
    calls, _ = await _setup(hass, None)  # bez freezera: token WS musi być ważny
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "rekuperacja/subscribe"})
    assert (await ws.receive_json())["success"]
    snap = (await ws.receive_json())["event"]
    assert snap["winner"]["source"] == "harmonogram"
    assert "next_switch" in snap["schedule"]
    await ws.send_json({"id": 2, "type": "rekuperacja/action", "action": "request",
                        "source": "panel_wietrz", "percentage": 80, "minutes": 60})
    msg = await ws.receive_json()
    while msg.get("id") != 2:
        msg = await ws.receive_json()
    assert msg["success"]
    assert calls[-1].data["percentage"] == 80
    await ws.send_json({"id": 3, "type": "rekuperacja/set_setting", "key": "automation", "value": False})
    msg = await ws.receive_json()
    while msg.get("id") != 3:
        msg = await ws.receive_json()
    assert msg["success"]
    assert hass.states.get("switch.rekuperacja_automation").state == "off"
