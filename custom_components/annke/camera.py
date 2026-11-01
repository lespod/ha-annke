"""Camera entities: main stream and sub stream per channel."""

from __future__ import annotations

from urllib.parse import quote

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnnkeConfigEntry
from .device import AnnkeCoordinator
from .entity import AnnkePlainEntity
from .isapi import IsapiError

RTSP_PORT = 554


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnnkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        AnnkeCamera(coordinator, entry, ch, stream)
        for ch in coordinator.features.channels
        for stream in (1, 2)
    )


class AnnkeCamera(AnnkePlainEntity, Camera):
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self, coordinator: AnnkeCoordinator, entry: AnnkeConfigEntry, channel: int, stream: int
    ) -> None:
        key = "main_stream" if stream == 1 else "sub_stream"
        AnnkePlainEntity.__init__(self, coordinator, key, channel)
        Camera.__init__(self)
        self._stream_id = f"{channel}0{stream}"
        self._user = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]
        self._attr_entity_registry_enabled_default = stream == 1
        self._attr_brand = "Annke"
        self._attr_model = coordinator.info.model

    async def stream_source(self) -> str:
        cred = f"{quote(self._user, safe='')}:{quote(self._password, safe='')}"
        return f"rtsp://{cred}@{self.coordinator.client.host}:{RTSP_PORT}/Streaming/Channels/{self._stream_id}"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            return await self.coordinator.client.get_bytes(
                f"/ISAPI/Streaming/channels/{self._stream_id}/picture", timeout=15
            )
        except IsapiError:
            return None
