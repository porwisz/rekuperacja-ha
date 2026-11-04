"""Koordynator: zbiera żądania, wybiera zwycięzcę, steruje wentylatorem."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    COMMAND_GRACE_S,
    DEFAULT_SETTINGS,
    PRESET_BOOST,
    PRESET_SLEEP,
    RESEND_INTERVAL_S,
    SIGNAL_UPDATE,
    SLEEP_LEVEL,
    SOURCE_BOOST_BUTTON,
    SOURCE_MANUAL,
    SOURCE_SCHEDULE,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .core.arbiter import Command, Request, resolve
from .core.schedule import is_day

_LOGGER = logging.getLogger(__name__)


def level_of(command: Command) -> int:
    if command.preset == PRESET_BOOST:
        return 100
    if command.preset == PRESET_SLEEP:
        return SLEEP_LEVEL
    if command.preset:  # Auto / Kominek — traktujemy jak średnią wydajność
        return 50
    return command.percentage or 0


def _req_to_json(r: Request) -> dict:
    return {
        "source": r.source,
        "level": r.level,
        "percentage": r.command.percentage,
        "preset": r.command.preset,
        "until": r.until.isoformat() if r.until else None,
    }


def _req_from_json(d: dict) -> Request:
    until = dt_util.parse_datetime(d["until"]) if d.get("until") else None
    return Request(d["source"], d["level"], Command(d.get("percentage"), d.get("preset")), until)


class RekuperacjaCoordinator:
    def __init__(self, hass: HomeAssistant, fan_entity: str) -> None:
        self.hass = hass
        self.fan_entity = fan_entity
        self.settings: dict = dict(DEFAULT_SETTINGS)
        self.timed: dict[str, Request] = {}  # żądania czasowe/zewnętrzne wg źródła
        self.manual: Request | None = None
        self.winner: Request | None = None
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._last_command: Command | None = None
        self._last_sent: datetime | None = None
        self._unsubs: list = []

    # ---------- cykl życia ----------
    async def async_start(self) -> None:
        data = await self._store.async_load() or {}
        for key, value in data.get("settings", {}).items():
            if key not in DEFAULT_SETTINGS:
                continue
            if isinstance(DEFAULT_SETTINGS[key], time):
                value = time.fromisoformat(value)
            self.settings[key] = value
        now = dt_util.utcnow()
        for d in data.get("timed", []):
            r = _req_from_json(d)
            if r.active(now):
                self.timed[r.source] = r
        if data.get("manual"):
            m = _req_from_json(data["manual"])
            self.manual = m if m.active(now) else None

        self._unsubs.append(
            async_track_state_change_event(self.hass, [self.fan_entity], self._on_fan_change)
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._on_tick, timedelta(seconds=30))
        )
        await self.async_evaluate()

    async def async_stop(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        await self._async_save()

    async def _async_save(self) -> None:
        settings = {k: (v.isoformat() if isinstance(v, time) else v) for k, v in self.settings.items()}
        await self._store.async_save(
            {
                "settings": settings,
                "timed": [_req_to_json(r) for r in self.timed.values()],
                "manual": _req_to_json(self.manual) if self.manual else None,
            }
        )

    # ---------- API dla encji i serwisów ----------
    async def async_set_setting(self, key: str, value) -> None:
        self.settings[key] = value
        await self._async_save()
        await self.async_evaluate()

    async def async_request(self, source: str, command: Command, minutes: float | None) -> None:
        now = dt_util.utcnow()
        until = now + timedelta(minutes=minutes) if minutes else None
        self.timed[source] = Request(source, level_of(command), command, until, now)
        await self._async_save()
        await self.async_evaluate()

    async def async_cancel(self, source: str) -> None:
        if self.timed.pop(source, None):
            await self._async_save()
            await self.async_evaluate()

    async def async_boost(self) -> None:
        await self.async_request(
            SOURCE_BOOST_BUTTON, Command(percentage=100), self.settings["boost_minutes"]
        )

    async def async_resume_automation(self) -> None:
        """Kasuje ręczne nadpisanie i boost z przycisku."""
        self.manual = None
        self.timed.pop(SOURCE_BOOST_BUTTON, None)
        self._last_command = None
        await self._async_save()
        await self.async_evaluate()

    # ---------- logika ----------
    def requests(self, now: datetime) -> list[Request]:
        out: list[Request] = []
        if self.settings["schedule_enabled"]:
            local = dt_util.as_local(now)
            if is_day(local, self.settings):
                pct = int(self.settings["day_percentage"])
                out.append(Request(SOURCE_SCHEDULE, pct, Command(percentage=pct)))
            else:
                out.append(Request(SOURCE_SCHEDULE, SLEEP_LEVEL, Command(preset=PRESET_SLEEP)))
        out.extend(r for r in self.timed.values() if r.active(now))
        return out

    async def async_evaluate(self) -> None:
        now = dt_util.utcnow()
        expired = [s for s, r in self.timed.items() if not r.active(now)]
        for s in expired:
            del self.timed[s]
        if self.manual and not self.manual.active(now):
            self.manual = None
            self._last_command = None

        self.winner = resolve(self.requests(now), now, self.manual)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

        if not self.settings["automation"] or self.winner is None:
            return
        if self.winner is self.manual:
            return  # ręczne: użytkownik już ustawił wentylator
        await self._async_apply(self.winner.command, now)

    def _fan_matches(self, command: Command) -> bool:
        state = self.hass.states.get(self.fan_entity)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return True  # nie ma czym sterować
        preset = state.attributes.get("preset_mode")
        if command.preset:
            return state.state == STATE_ON and preset == command.preset
        return (
            state.state == STATE_ON
            and not preset
            and state.attributes.get("percentage") == command.percentage
        )

    async def _async_apply(self, command: Command, now: datetime) -> None:
        if self._fan_matches(command):
            self._last_command = command
            return
        if (
            command == self._last_command
            and self._last_sent
            and (now - self._last_sent).total_seconds() < RESEND_INTERVAL_S
        ):
            return
        self._last_command = command
        self._last_sent = now
        _LOGGER.debug("Rekuperator -> %s (%s)", command.describe(), self.winner and self.winner.source)
        if command.preset:
            await self.hass.services.async_call(
                "fan", "set_preset_mode",
                {ATTR_ENTITY_ID: self.fan_entity, "preset_mode": command.preset}, blocking=True,
            )
        else:
            await self.hass.services.async_call(
                "fan", "set_percentage",
                {ATTR_ENTITY_ID: self.fan_entity, "percentage": command.percentage}, blocking=True,
            )

    # ---------- zdarzenia ----------
    @callback
    def _on_tick(self, _now) -> None:
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _on_fan_change(self, event: Event[EventStateChangedData]) -> None:
        old, new = event.data["old_state"], event.data["new_state"]
        if old is None or new is None or not self.settings["automation"]:
            return
        if new.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) or old.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        key = lambda s: (s.state, s.attributes.get("percentage"), s.attributes.get("preset_mode"))
        if key(old) == key(new):
            return
        now = dt_util.utcnow()
        if self._last_sent and (now - self._last_sent).total_seconds() < COMMAND_GRACE_S:
            return  # echo naszej komendy
        if self._last_command and self._fan_matches(self._last_command):
            return
        # Zmiana z panelu / aplikacji / ręcznie w HA -> nadpisanie na X min
        if new.state != STATE_ON:
            command = Command(percentage=0)
        elif new.attributes.get("preset_mode"):
            command = Command(preset=new.attributes["preset_mode"])
        else:
            command = Command(percentage=new.attributes.get("percentage"))
        minutes = self.settings["manual_minutes"]
        self.manual = Request(SOURCE_MANUAL, level_of(command), command, now + timedelta(minutes=minutes), now)
        _LOGGER.info("Ręczna zmiana rekuperatora (%s) — automatyka wstrzymana na %s min", command.describe(), minutes)
        self.hass.async_create_task(self._async_save())
        self.winner = self.manual
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)
