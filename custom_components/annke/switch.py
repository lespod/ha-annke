"""Switches: white light, detections, alarm outputs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnnkeConfigEntry
from .device import AnnkeCoordinator, BoundSetting, output_active
from .entity import AnnkeEntity

WHITE = "colorVuWhiteLight"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnnkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    features = coordinator.features
    entities: list[SwitchEntity] = [
        AnnkeSettingSwitch(coordinator, s) for s in features.settings if s.spec.kind == "bool"
    ]
    entities += [
        AnnkeWhiteLightSwitch(coordinator, s)
        for s in features.settings
        if s.spec.key == "supplement_light_mode" and WHITE in s.options
    ]
    entities += [AnnkeOutputSwitch(coordinator, port) for port in features.io_outputs]
    async_add_entities(entities)


class AnnkeSettingSwitch(AnnkeEntity, SwitchEntity):
    """A boolean field in an ISAPI document, e.g. motion detection enabled."""

    def __init__(self, coordinator: AnnkeCoordinator, setting: BoundSetting) -> None:
        super().__init__(coordinator, setting.spec.key, setting.channel)
        self.setting = setting
        self._attr_entity_category = EntityCategory.CONFIG if setting.spec.config else None
        self._attr_entity_registry_enabled_default = setting.spec.enabled_default
        if setting.spec.icon:
            self._attr_icon = setting.spec.icon

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.value(self.setting)
        return None if value is None else value.lower() == "true"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_values(self.setting.path, {self.setting.spec.element: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_values(self.setting.path, {self.setting.spec.element: False})


class AnnkeWhiteLightSwitch(AnnkeEntity, SwitchEntity):
    """Turns the ColorVu white LED on, and back to the previous mode when off."""

    _attr_icon = "mdi:spotlight-beam"

    def __init__(self, coordinator: AnnkeCoordinator, mode: BoundSetting) -> None:
        super().__init__(coordinator, "white_light", mode.channel)
        self.mode = mode
        self._off_mode = next(
            (m for m in ("irLight", "eventIntelligence", "close") if m in mode.options), "close"
        )

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.value(self.mode)
        return None if value is None else value == WHITE

    async def async_turn_on(self, **kwargs: Any) -> None:
        current = self.coordinator.value(self.mode)
        if current and current != WHITE:
            self._off_mode = current
        changes: dict[str, Any] = {"supplementLightMode": WHITE}
        root = (self.coordinator.data or {}).get(self.mode.path)
        if root is not None and root.find("mixedLightBrightnessRegulatMode") is not None:
            # In "auto" the camera decides on its own and may keep the LED dark.
            changes["mixedLightBrightnessRegulatMode"] = "manual"
        await self.coordinator.async_set_values(self.mode.path, changes)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_values(
            self.mode.path, {"supplementLightMode": self._off_mode}
        )


class AnnkeOutputSwitch(AnnkeEntity, SwitchEntity):
    """A relay / alarm output on the camera."""

    _attr_icon = "mdi:electric-switch"

    def __init__(self, coordinator: AnnkeCoordinator, port: str) -> None:
        super().__init__(coordinator, f"alarm_output_{port}", translation_key="alarm_output")
        self._attr_translation_placeholders = {"port": port}
        self.port = port

    @property
    def is_on(self) -> bool | None:
        return output_active(self.coordinator.data, self.port)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_output(self.port, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_output(self.port, False)
