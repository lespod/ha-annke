"""Sensors: system load, uptime and SD card."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
import xml.etree.ElementTree as ET

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AnnkeConfigEntry
from .device import STORAGE, SYSTEM_STATUS, AnnkeCoordinator
from .entity import AnnkeEntity
from .isapi import text_of


def _float(root: ET.Element | None, path: str) -> float | None:
    value = text_of(root, path)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _memory_percent(root: ET.Element | None) -> float | None:
    used = _float(root, ".//memoryUsage")
    free = _float(root, ".//memoryAvailable")
    if used is None or free is None or used + free == 0:
        return None
    return round(100 * used / (used + free), 1)


def _uptime(root: ET.Element | None) -> datetime | None:
    seconds = _float(root, "deviceUpTime")
    if seconds is None:
        return None
    # Round to the minute so the state does not change on every poll.
    boot = dt_util.utcnow() - timedelta(seconds=seconds)
    return boot.replace(second=0, microsecond=0)


@dataclass(frozen=True, kw_only=True)
class AnnkeSensorDescription(SensorEntityDescription):
    source: str
    value: Callable[[ET.Element | None], Any]


STATUS_SENSORS = (
    AnnkeSensorDescription(
        key="cpu",
        translation_key="cpu",
        source=SYSTEM_STATUS,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda r: _float(r, ".//cpuUtilization"),
    ),
    AnnkeSensorDescription(
        key="memory",
        translation_key="memory",
        source=SYSTEM_STATUS,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_memory_percent,
    ),
    AnnkeSensorDescription(
        key="boot_time",
        translation_key="boot_time",
        source=SYSTEM_STATUS,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_uptime,
    ),
)

STORAGE_SENSORS = (
    AnnkeSensorDescription(
        key="storage_status",
        translation_key="storage_status",
        source=STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:sd",
        value=lambda r: (text_of(r, ".//hdd/status") or "").lower() or None,
    ),
    AnnkeSensorDescription(
        key="storage_free",
        translation_key="storage_free",
        source=STORAGE,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda r: _float(r, ".//hdd/freeSpace"),
    ),
    AnnkeSensorDescription(
        key="storage_capacity",
        translation_key="storage_capacity",
        source=STORAGE,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda r: _float(r, ".//hdd/capacity"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnnkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    descriptions: list[AnnkeSensorDescription] = []
    if coordinator.features.has_status:
        descriptions += STATUS_SENSORS
    if coordinator.features.has_storage:
        descriptions += STORAGE_SENSORS
    async_add_entities(AnnkeSensor(coordinator, d) for d in descriptions)


class AnnkeSensor(AnnkeEntity, SensorEntity):
    entity_description: AnnkeSensorDescription

    def __init__(self, coordinator: AnnkeCoordinator, description: AnnkeSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value((self.coordinator.data or {}).get(self.entity_description.source))
