"""Config flow: wybór encji wentylatora rekuperatora."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import CONF_FAN, DOMAIN


class RekuperacjaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Rekuperacja", data=user_input)
        default = "fan.rekuperator" if self.hass.states.get("fan.rekuperator") else vol.UNDEFINED
        schema = vol.Schema(
            {
                vol.Required(CONF_FAN, default=default): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="fan")
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
