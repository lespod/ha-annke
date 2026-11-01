"""Services: PTZ moves and presets."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .device import AnnkeCoordinator

SPEED = vol.All(vol.Coerce(int), vol.Range(min=-100, max=100))

PTZ_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional("channel", default=1): cv.positive_int,
        vol.Optional("pan", default=0): SPEED,
        vol.Optional("tilt", default=0): SPEED,
        vol.Optional("zoom", default=0): SPEED,
        vol.Optional("duration", default=0.5): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
    }
)
PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional("channel", default=1): cv.positive_int,
        vol.Required("preset"): cv.positive_int,
    }
)


def _coordinator(hass: HomeAssistant, device_id: str) -> AnnkeCoordinator:
    device = dr.async_get(hass).async_get(device_id)
    if device:
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry and entry.domain == DOMAIN and hasattr(entry, "runtime_data"):
                return entry.runtime_data.coordinator
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="unknown_device"
    )


def _ptz(coordinator: AnnkeCoordinator, channel: int) -> None:
    if channel not in coordinator.features.ptz_channels:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_ptz",
            translation_placeholders={"name": coordinator.info.name},
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def ptz_move(call: ServiceCall) -> None:
        c = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        _ptz(c, call.data["channel"])
        await c.async_ptz(
            call.data["channel"], call.data["pan"], call.data["tilt"], call.data["zoom"], call.data["duration"]
        )

    async def goto_preset(call: ServiceCall) -> None:
        c = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        _ptz(c, call.data["channel"])
        await c.async_goto_preset(call.data["channel"], call.data["preset"])

    hass.services.async_register(DOMAIN, "ptz_move", ptz_move, schema=PTZ_SCHEMA)
    hass.services.async_register(DOMAIN, "goto_preset", goto_preset, schema=PRESET_SCHEMA)
