"""Config flow: wentylator; options flow: czujniki modułów."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CWU,
    CONF_FAN,
    CONF_MIN_DROP,
    CONF_MIN_LITERS,
    CONF_WATER,
    DEFAULT_CWU,
    DEFAULT_WATER,
    DOMAIN,
)


def _sensor() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _num(lo, hi, step, unit) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=lo, max=hi, step=step, unit_of_measurement=unit,
                                      mode=selector.NumberSelectorMode.BOX)
    )


def options_schema(hass, current: dict) -> vol.Schema:
    def dflt(key, fallback):
        if key in current:
            return current[key]
        return fallback if hass.states.get(fallback) else vol.UNDEFINED

    return vol.Schema(
        {
            vol.Optional(CONF_WATER, description={"suggested_value": dflt(CONF_WATER, DEFAULT_WATER)}): _sensor(),
            vol.Optional(CONF_CWU, description={"suggested_value": dflt(CONF_CWU, DEFAULT_CWU)}): _sensor(),
            vol.Required(CONF_MIN_LITERS, default=current.get(CONF_MIN_LITERS, 15)): _num(1, 100, 1, "L"),
            vol.Required(CONF_MIN_DROP, default=current.get(CONF_MIN_DROP, 2)): _num(0.5, 20, 0.5, "°C"),
        }
    )


class RekuperacjaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._data = user_input
            return await self.async_step_modules()
        default = "fan.rekuperator" if self.hass.states.get("fan.rekuperator") else vol.UNDEFINED
        schema = vol.Schema(
            {
                vol.Required(CONF_FAN, default=default): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="fan")
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_modules(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Rekuperacja", data=self._data, options=user_input)
        return self.async_show_form(step_id="modules", data_schema=options_schema(self.hass, {}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RekuperacjaOptionsFlow()


class RekuperacjaOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init", data_schema=options_schema(self.hass, dict(self.config_entry.options))
        )
