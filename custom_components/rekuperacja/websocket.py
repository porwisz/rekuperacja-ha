"""WebSocket API dla karty Lovelace (rekuperacja-card)."""

from __future__ import annotations

from datetime import time

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SETTINGS, DOMAIN, SIGNAL_UPDATE, SOURCE_MANUAL, SOURCE_SCHEDULE
from .core.arbiter import Command
from .core.schedule import is_day, next_switch

# ustawienia, które karta może zmieniać (bool / int)
TIMES = {"weekday_day_start", "weekday_night_start", "weekend_day_start", "weekend_night_start"}
EDITABLE = {"automation", "schedule_enabled", "day_auto", "shower_enabled", "day_percentage",
            "boost_minutes", "manual_minutes", "shower_after_minutes"}


def _coordinator(hass: HomeAssistant):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


def _iso(t):
    return dt_util.as_local(t).isoformat() if t else None


def snapshot(c) -> dict:
    now = dt_util.utcnow()
    local = dt_util.as_local(now)
    fan = c.hass.states.get(c.fan_entity)
    reqs = c.requests(now)
    if c.manual and c.manual.active(now):
        reqs.append(c.manual)
    w = c.winner
    d = c.shower.detector
    return {
        "fan": {
            "entity_id": c.fan_entity,
            "state": fan.state if fan else None,
            "percentage": fan.attributes.get("percentage") if fan else None,
            "preset": (fan.attributes.get("preset_mode") or None) if fan else None,
        },
        "settings": {k: v for k, v in c.settings.items() if k in EDITABLE},
        "times": {k: c.settings[k].strftime("%H:%M") for k in TIMES},
        "winner": {"source": w.source, "command": w.command.describe(), "until": _iso(w.until)} if w else None,
        "requests": sorted(
            (
                {
                    "source": r.source,
                    "level": r.level,
                    "command": r.command.describe(),
                    "until": _iso(r.until),
                    "winner": r is w,
                    "cancellable": r.source not in (SOURCE_SCHEDULE,),
                }
                for r in reqs
            ),
            key=lambda x: -x["level"],
        ),
        "shower": {
            "configured": c.shower.configured,
            "detected": c.shower.detected,
            "water_l": round(d.water.change(now), 1),
            "water_min_l": d.min_liters,
            "cwu_change": round(d.cwu.change(now), 1),
            "cwu_min_drop": d.min_drop_c,
        },
        "schedule": {
            "is_day": is_day(local, c.settings),
            "next_switch": next_switch(local, c.settings).isoformat(),
        },
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@websocket_api.async_response
async def ws_subscribe(hass, connection, msg):
    c = _coordinator(hass)
    if c is None:
        connection.send_error(msg["id"], "not_loaded", "Integracja Rekuperacja nie jest załadowana")
        return

    @callback
    def push(*_):
        connection.send_message(websocket_api.event_message(msg["id"], snapshot(c)))

    unsubs = [
        async_dispatcher_connect(hass, SIGNAL_UPDATE, push),
        async_track_state_change_event(hass, [c.fan_entity], push),
    ]

    @callback
    def unsub():
        for u in unsubs:
            u()

    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"])
    push()


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/set_setting", vol.Required("key"): vol.In(EDITABLE | TIMES), vol.Required("value"): vol.Any(bool, int, float, str)}
)
@websocket_api.async_response
async def ws_set_setting(hass, connection, msg):
    c = _coordinator(hass)
    value = msg["value"]
    if msg["key"] in TIMES:
        try:
            value = time.fromisoformat(str(value))
        except ValueError:
            connection.send_error(msg["id"], "invalid_format", "Godzina w formacie HH:MM")
            return
    elif not isinstance(DEFAULT_SETTINGS[msg["key"]], bool):
        value = int(value)
    await c.async_set_setting(msg["key"], value)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/action",
        vol.Required("action"): vol.In(["boost", "resume", "request", "cancel"]),
        vol.Optional("source"): str,
        vol.Optional("percentage"): vol.All(int, vol.Range(0, 100)),
        vol.Optional("preset"): str,
        vol.Optional("minutes"): vol.Any(int, float),
    }
)
@websocket_api.async_response
async def ws_action(hass, connection, msg):
    c = _coordinator(hass)
    a = msg["action"]
    if a == "boost":
        await c.async_boost()
    elif a == "resume":
        await c.async_resume_automation()
    elif a == "request":
        await c.async_request(msg.get("source", "panel"), Command(msg.get("percentage"), msg.get("preset")), msg.get("minutes"))
    elif a == "cancel":
        if msg.get("source") == SOURCE_MANUAL:
            await c.async_resume_automation()
        else:
            await c.async_cancel(msg.get("source", ""))
    connection.send_result(msg["id"])


@callback
def async_register(hass: HomeAssistant) -> None:
    for cmd in (ws_subscribe, ws_set_setting, ws_action):
        websocket_api.async_register_command(hass, cmd)
