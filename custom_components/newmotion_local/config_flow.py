"""Config flow for the NewMotion Local integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.httpx_client import get_async_client
import voluptuous as vol

from .api import (
    CannotConnect,
    ChargerState,
    NewMotionClient,
    NewMotionError,
    NotNewMotion,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

HOST_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class NewMotionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a NewMotion charger by IP address."""

    VERSION = 1

    async def _async_probe(self, host: str) -> ChargerState:
        return await NewMotionClient(get_async_client(self.hass), host).get_status()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the charger's address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                state = await self._async_probe(host)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NotNewMotion:
                errors["base"] = "not_newmotion"
            except NewMotionError:
                _LOGGER.exception("Unexpected error probing %s", host)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(state.charge_point_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=f"NewMotion {state.charge_point_id}",
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(HOST_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of an existing charger."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                state = await self._async_probe(host)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NotNewMotion:
                errors["base"] = "not_newmotion"
            except NewMotionError:
                _LOGGER.exception("Unexpected error during reconfigure")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(state.charge_point_id)
                self._abort_if_unique_id_mismatch(reason="unique_id_mismatch")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                HOST_SCHEMA, user_input or {CONF_HOST: entry.data[CONF_HOST]}
            ),
            errors=errors,
        )
