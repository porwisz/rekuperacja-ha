"""Moduł prysznica: 100% w trakcie i N minut po."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from ..const import CONF_CWU, CONF_MIN_DROP, CONF_MIN_LITERS, CONF_WATER, SOURCE_SHOWER
from ..core.arbiter import Command
from ..core.shower import ShowerDetector

_LOGGER = logging.getLogger(__name__)
_LITERS_PER_UNIT = {"m³": 1000.0, "m3": 1000.0, "L": 1.0, "l": 1.0, "gal": 3.785411784}


def _value(state: State | None) -> float | None:
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


class ShowerModule:
    def __init__(self, hass: HomeAssistant, coordinator, options: dict) -> None:
        self.hass = hass
        self.c = coordinator
        self.water = options.get(CONF_WATER)
        self.cwu = options.get(CONF_CWU)
        self.detector = ShowerDetector(
            min_liters=options.get(CONF_MIN_LITERS, 15), min_drop_c=options.get(CONF_MIN_DROP, 2)
        )
        self.detected = False

    @property
    def configured(self) -> bool:
        return bool(self.water and self.cwu)

    def start(self) -> list:
        if not self.configured:
            return []
        now = dt_util.utcnow()
        for eid in (self.water, self.cwu):
            self._sample(eid, self.hass.states.get(eid), now)
        return [async_track_state_change_event(self.hass, [self.water, self.cwu], self._on_change)]

    def _sample(self, entity_id: str, state: State | None, now: datetime) -> None:
        v = _value(state)
        if v is None:
            return
        if entity_id == self.water:
            unit = state.attributes.get("unit_of_measurement", "m³")
            self.detector.add_water_liters(now, v * _LITERS_PER_UNIT.get(unit, 1000.0))
        else:
            self.detector.add_cwu(now, v)

    @callback
    def _on_change(self, event: Event[EventStateChangedData]) -> None:
        self._sample(event.data["entity_id"], event.data["new_state"], dt_util.utcnow())
        self.hass.async_create_task(self.async_check())

    async def async_check(self) -> None:
        """Wołane przy każdej próbce i co tick koordynatora."""
        if not self.configured:
            return
        now = dt_util.utcnow()
        detected = self.detector.detected(now)
        if detected != self.detected:
            self.detected = detected
            _LOGGER.info("Prysznic %s", "wykryty" if detected else "zakończony")
        from homeassistant.helpers.dispatcher import async_dispatcher_send

        from ..const import SIGNAL_UPDATE

        async_dispatcher_send(self.hass, SIGNAL_UPDATE)
        if detected and self.c.settings["shower_enabled"]:
            # odświeżane, póki trwa — wygasa N minut po ostatnim wykryciu
            await self.c.async_request(
                SOURCE_SHOWER, Command(percentage=100), self.c.settings["shower_after_minutes"]
            )
