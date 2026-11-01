"""Binary sensors: real-time detections from the camera's alert stream."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnnkeConfigEntry
from .const import EVENTS, EventSpec
from .device import AnnkeCoordinator
from .entity import AnnkePlainEntity
from .events import EventHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnnkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    hub = entry.runtime_data.events
    features = coordinator.features
    keys = features.setting_keys()
    entities: list[BinarySensorEntity] = []
    for ch in features.channels:
        for spec in EVENTS:
            if spec.target:
                enabled = features.human_vehicle
            elif spec.requires:
                if spec.requires not in keys:
                    continue
                enabled = True
            else:
                enabled = False  # e.g. PIR: only some models, cannot be probed reliably
            entities.append(AnnkeEventSensor(coordinator, hub, spec, ch, enabled))
    entities += [AnnkeInputSensor(coordinator, hub, port) for port in features.io_inputs]
    entities.append(AnnkeStreamSensor(coordinator, hub))
    async_add_entities(entities)


class _HubEntity(AnnkePlainEntity, BinarySensorEntity):
    def __init__(self, coordinator: AnnkeCoordinator, hub: EventHub, key: str, channel: int | None) -> None:
        super().__init__(coordinator, key, channel)
        self.hub = hub

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.hub.add_listener(self.async_write_ha_state))


class AnnkeEventSensor(_HubEntity):
    """On while the camera reports the event."""

    def __init__(
        self,
        coordinator: AnnkeCoordinator,
        hub: EventHub,
        spec: EventSpec,
        channel: int,
        enabled: bool,
    ) -> None:
        super().__init__(coordinator, hub, spec.key, channel)
        self.spec = spec
        self._attr_device_class = BinarySensorDeviceClass(spec.device_class)
        self._attr_entity_registry_enabled_default = enabled

    @property
    def is_on(self) -> bool:
        return self.hub.is_on(self.spec.key, self.channel)


class AnnkeInputSensor(_HubEntity):
    """A wired alarm input on the camera."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: AnnkeCoordinator, hub: EventHub, port: str) -> None:
        super().__init__(coordinator, hub, f"alarm_input_{port}", None)
        self._attr_translation_key = "alarm_input"
        self._attr_translation_placeholders = {"port": port}
        self.port = port

    @property
    def is_on(self) -> bool:
        return self.hub.is_on(f"io_{self.port}", 1)


class AnnkeStreamSensor(_HubEntity):
    """Whether the event connection to the camera is up."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AnnkeCoordinator, hub: EventHub) -> None:
        super().__init__(coordinator, hub, "event_stream", None)

    @property
    def is_on(self) -> bool:
        return self.hub.connected
