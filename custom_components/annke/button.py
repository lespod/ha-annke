"""Buttons: reboot, siren test, wiper, focus, event linkage fix."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnnkeConfigEntry
from .const import DOMAIN
from .device import AnnkeCoordinator
from .entity import AnnkeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnnkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    c = entry.runtime_data.coordinator
    f = c.features
    entities: list[ButtonEntity] = [
        AnnkeButton(c, "reboot", c.async_reboot, device_class=ButtonDeviceClass.RESTART, category=EntityCategory.CONFIG),
        AnnkeButton(c, "enable_event_linkage", lambda: _fix_linkage(hass, c), category=EntityCategory.CONFIG, icon="mdi:link-variant"),
    ]
    if f.audio_alarm:
        entities.append(AnnkeButton(c, "siren_test", c.async_test_audio_alarm, icon="mdi:bullhorn"))
    entities += [
        AnnkeButton(c, "wiper", lambda ch=ch: c.async_wiper(ch), channel=ch, icon="mdi:wiper")
        for ch in f.wiper_channels
    ]
    entities += [
        AnnkeButton(c, "focus", lambda ch=ch: c.async_focus(ch), channel=ch, icon="mdi:image-filter-center-focus")
        for ch in f.focus_channels
    ]
    async_add_entities(entities)


async def _fix_linkage(hass: HomeAssistant, coordinator: AnnkeCoordinator) -> None:
    await coordinator.async_enable_linkage()
    if not await coordinator.async_missing_linkage():
        ir.async_delete_issue(hass, DOMAIN, f"linkage_{coordinator.info.serial}")


class AnnkeButton(AnnkeEntity, ButtonEntity):
    def __init__(
        self,
        coordinator: AnnkeCoordinator,
        key: str,
        press: Callable[[], Awaitable[None]],
        *,
        channel: int | None = None,
        device_class: ButtonDeviceClass | None = None,
        category: EntityCategory | None = None,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator, key, channel)
        self._press = press
        self._attr_device_class = device_class
        self._attr_entity_category = category
        if icon:
            self._attr_icon = icon

    async def async_press(self) -> None:
        await self._press()
