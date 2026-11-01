"""The Annke integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_OFF_DELAY, DEFAULT_OFF_DELAY, DOMAIN
from .device import AnnkeCoordinator, discover
from .events import EventHub
from .isapi import IsapiAuthError, IsapiClient, IsapiError
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class AnnkeData:
    coordinator: AnnkeCoordinator
    events: EventHub


type AnnkeConfigEntry = ConfigEntry[AnnkeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AnnkeConfigEntry) -> bool:
    ssl = entry.data.get(CONF_SSL, False)
    client = IsapiClient(
        get_async_client(hass, verify_ssl=False),
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        port=entry.data.get(CONF_PORT, 443 if ssl else 80),
        ssl=ssl,
    )
    try:
        info = await client.device_info()
        features = await discover(client)
    except IsapiAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except IsapiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = AnnkeCoordinator(hass, entry, client, info, features)
    await coordinator.async_config_entry_first_refresh()

    events = EventHub(
        hass, client, info.serial, entry.options.get(CONF_OFF_DELAY, DEFAULT_OFF_DELAY)
    )
    entry.runtime_data = AnnkeData(coordinator, events)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    events.start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    missing = await coordinator.async_missing_linkage()
    issue_id = f"linkage_{info.serial}"
    if missing:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="missing_linkage",
            translation_placeholders={"name": info.name, "events": ", ".join(missing)},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AnnkeConfigEntry) -> bool:
    await entry.runtime_data.events.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: AnnkeConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
