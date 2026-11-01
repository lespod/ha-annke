"""Base entities for the Annke integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device import AnnkeCoordinator


def device_info(coordinator: AnnkeCoordinator) -> DeviceInfo:
    info = coordinator.info
    return DeviceInfo(
        identifiers={(DOMAIN, info.serial)},
        connections={(CONNECTION_NETWORK_MAC, info.mac)} if info.mac else set(),
        manufacturer="Annke",
        model=info.model,
        name=info.name,
        serial_number=info.serial,
        sw_version=info.firmware,
        configuration_url=coordinator.client.base,
    )


class AnnkeEntity(CoordinatorEntity[AnnkeCoordinator]):
    """Entity backed by the polling coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnnkeCoordinator,
        key: str,
        channel: int | None = None,
        *,
        translation_key: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        multi = channel is not None and len(coordinator.features.channels) > 1
        suffix = f"_{channel}" if channel is not None else ""
        self._attr_unique_id = f"{coordinator.info.serial}_{key}{suffix}"
        self._attr_translation_key = translation_key or key
        if multi:
            self._attr_translation_key += "_channel"
            self._attr_translation_placeholders = {"channel": str(channel)}
        self._attr_device_info = device_info(coordinator)
        self.channel = channel


class AnnkePlainEntity(Entity):
    """Entity that is not driven by the coordinator (events, camera)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: AnnkeCoordinator, key: str, channel: int | None = None) -> None:
        multi = channel is not None and len(coordinator.features.channels) > 1
        suffix = f"_{channel}" if channel is not None else ""
        self.coordinator = coordinator
        self.channel = channel
        self._attr_unique_id = f"{coordinator.info.serial}_{key}{suffix}"
        self._attr_translation_key = key + ("_channel" if multi else "")
        if multi:
            self._attr_translation_placeholders = {"channel": str(channel)}
        self._attr_device_info = device_info(coordinator)
