"""Selects: light mode, day/night, siren sound, strobe frequency."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
    entities: list[SelectEntity] = [
        AnnkeSettingSelect(coordinator, s)
        for s in features.settings
        if s.spec.kind == "select" and s.options
    ]
    if features.audio_alarm and features.audio_alarm.sounds:
        entities.append(AnnkeSirenSoundSelect(coordinator))
    async_add_entities(entities)


def _slug(option: str) -> str:
    """Translation keys must be lowercase snake case."""
    out = "".join("_" + c.lower() if c.isupper() else c for c in option)
    return out.strip("_").replace("-", "_")


class AnnkeSettingSelect(AnnkeEntity, SelectEntity):
    """An enumerated field in an ISAPI document."""

    def __init__(self, coordinator: AnnkeCoordinator, setting: BoundSetting) -> None:
        super().__init__(coordinator, setting.spec.key, setting.channel)
        self.setting = setting
        self._raw = {_slug(o): o for o in setting.options}
        self._attr_options = list(self._raw)
        self._attr_entity_category = EntityCategory.CONFIG if setting.spec.config else None
        self._attr_entity_registry_enabled_default = setting.spec.enabled_default
        if setting.spec.icon:
            self._attr_icon = setting.spec.icon

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.value(self.setting)
        return None if value is None else _slug(value)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_values(
            self.setting.path, {self.setting.spec.element: self._raw[option]}
        )


class AnnkeSirenSoundSelect(AnnkeEntity, SelectEntity):
    """Which built-in sound the siren plays."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:bullhorn"

    def __init__(self, coordinator: AnnkeCoordinator) -> None:
        super().__init__(coordinator, "siren_sound")
        sounds = coordinator.features.audio_alarm.sounds
        self._by_name = {f"{i}: {name}": i for i, name in sorted(sounds.items())}
        self._attr_options = list(self._by_name)

    @property
    def current_option(self) -> str | None:
        alarm = ((self.coordinator.data or {}).get(AUDIO_ALARM) or {}).get("AudioAlarm", {})
        current = alarm.get("audioID")
        return next((n for n, i in self._by_name.items() if i == current), None)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_audio_alarm({"audioID": self._by_name[option]})
