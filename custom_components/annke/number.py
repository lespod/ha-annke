"""Numbers: light brightness, day/night sensitivity, siren and strobe settings."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnnkeConfigEntry
from .device import AUDIO_ALARM, AnnkeCoordinator, BoundSetting
from .entity import AnnkeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnnkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    features = coordinator.features
    entities: list[NumberEntity] = [
        AnnkeSettingNumber(coordinator, s)
        for s in features.settings
        if s.spec.kind == "number" and s.range
    ]
    if alarm := features.audio_alarm:
        if alarm.volume:
            entities.append(AnnkeSirenNumber(coordinator, "siren_volume", "audioVolume", alarm.volume, "%"))
        if alarm.repeats:
            entities.append(AnnkeSirenNumber(coordinator, "siren_repeats", "alarmTimes", alarm.repeats, None))
    async_add_entities(entities)


class AnnkeSettingNumber(AnnkeEntity, NumberEntity):
    """A numeric field in an ISAPI document."""

    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: AnnkeCoordinator, setting: BoundSetting) -> None:
        super().__init__(coordinator, setting.spec.key, setting.channel)
        self.setting = setting
        self._attr_native_min_value, self._attr_native_max_value = setting.range
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = setting.spec.unit
        self._attr_entity_category = EntityCategory.CONFIG if setting.spec.config else None
        self._attr_entity_registry_enabled_default = setting.spec.enabled_default
        if setting.spec.icon:
            self._attr_icon = setting.spec.icon

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.value(self.setting)
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_values(
            self.setting.path, {self.setting.spec.element: int(value)}
        )


class AnnkeSirenNumber(AnnkeEntity, NumberEntity):
    """Siren volume / repeat count."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: AnnkeCoordinator,
        key: str,
        field: str,
        rng: tuple[int, int],
        unit: str | None,
    ) -> None:
        super().__init__(coordinator, key)
        self.field = field
        self._attr_native_min_value, self._attr_native_max_value = rng
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float | None:
        alarm = ((self.coordinator.data or {}).get(AUDIO_ALARM) or {}).get("AudioAlarm", {})
        value = alarm.get(self.field)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_audio_alarm({self.field: int(value)})
