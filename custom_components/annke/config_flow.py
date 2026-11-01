"""Config flow for Annke cameras."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_OFF_DELAY, DEFAULT_OFF_DELAY, DOMAIN
from .isapi import DeviceInfo, IsapiAuthError, IsapiClient, IsapiError

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=80): vol.All(int, vol.Range(min=1, max=65535)),
        vol.Optional(CONF_SSL, default=False): bool,
    }
)


class AnnkeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Annke."""

    VERSION = 1

    async def _probe(self, data: Mapping[str, Any]) -> DeviceInfo:
        client = IsapiClient(
            get_async_client(self.hass, verify_ssl=False),
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            port=data.get(CONF_PORT, 80),
            ssl=data.get(CONF_SSL, False),
        )
        return await client.device_info()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self._probe(user_input)
            except IsapiAuthError:
                errors["base"] = "invalid_auth"
            except IsapiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=f"{info.name} ({info.model})", data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                info = await self._probe(data)
            except IsapiAuthError:
                errors["base"] = "invalid_auth"
            except IsapiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            # An empty password keeps the saved one.
            if not user_input.get(CONF_PASSWORD):
                user_input.pop(CONF_PASSWORD, None)
            data = {**entry.data, **user_input}
            try:
                info = await self._probe(data)
            except IsapiAuthError:
                errors["base"] = "invalid_auth"
            except IsapiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=data)
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME]): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_PORT, default=entry.data.get(CONF_PORT, 80)): vol.All(
                    int, vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_SSL, default=entry.data.get(CONF_SSL, False)): bool,
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AnnkeOptionsFlow()


class AnnkeOptionsFlow(OptionsFlow):
    """Options: how long an event sensor stays on after the last alert."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_OFF_DELAY,
                        default=self.config_entry.options.get(CONF_OFF_DELAY, DEFAULT_OFF_DELAY),
                    ): vol.All(int, vol.Range(min=1, max=300)),
                }
            ),
        )
