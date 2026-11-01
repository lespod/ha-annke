"""Feature discovery and polling for one Annke camera."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any
import xml.etree.ElementTree as ET

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LINKAGE_TRIGGERS, XML_SETTINGS, XmlSetting
from .isapi import (
    DeviceInfo,
    IsapiAuthError,
    IsapiClient,
    IsapiError,
    IsapiForbidden,
    options_of,
    range_of,
    set_text,
    text_of,
)

_LOGGER = logging.getLogger(__name__)

AUDIO_ALARM = "/ISAPI/Event/triggers/notifications/AudioAlarm?format=json"
AUDIO_ALARM_CAPS = "/ISAPI/Event/triggers/notifications/AudioAlarm/capabilities?format=json"
SYSTEM_STATUS = "/ISAPI/System/status"
STORAGE = "/ISAPI/ContentMgmt/Storage"


@dataclass
class BoundSetting:
    """An XmlSetting resolved for a channel, with the device's options."""

    spec: XmlSetting
    channel: int
    path: str
    options: list[str] = field(default_factory=list)
    range: tuple[int, int] | None = None

    @property
    def unique_key(self) -> str:
        return f"{self.spec.key}_{self.channel}"


@dataclass
class AudioAlarmInfo:
    """Siren (audio alarm) capabilities."""

    sounds: dict[int, str]
    volume: tuple[int, int] | None
    repeats: tuple[int, int] | None


@dataclass
class Features:
    """Everything this camera supports, found once at setup."""

    channels: list[int]
    settings: list[BoundSetting]
    audio_alarm: AudioAlarmInfo | None = None
    io_inputs: list[str] = field(default_factory=list)
    io_outputs: list[str] = field(default_factory=list)
    ptz_channels: list[int] = field(default_factory=list)
    wiper_channels: list[int] = field(default_factory=list)
    focus_channels: list[int] = field(default_factory=list)
    human_vehicle: bool = False
    has_status: bool = False
    has_storage: bool = False
    has_two_way_audio: bool = False

    def setting_keys(self) -> set[str]:
        return {s.spec.key for s in self.settings}


def _ids(root: ET.Element | None, tag: str) -> list[str]:
    if root is None:
        return []
    return [i.text.strip() for i in root.iter(tag) if i.find("id") is None and i.text] or [
        text_of(el, "id") for el in root.iter(tag) if text_of(el, "id")
    ]


async def discover(client: IsapiClient) -> Features:
    """Probe the device for every feature the integration knows about."""
    inputs = await client.try_get_xml("/ISAPI/System/Video/inputs/channels")
    channels = sorted(
        int(c) for c in (text_of(el, "id") for el in (inputs.iter("VideoInputChannel") if inputs is not None else [])) if c and c.isdigit()
    ) or [1]

    settings: list[BoundSetting] = []
    docs: dict[str, ET.Element | None] = {}
    caps: dict[str, ET.Element | None] = {}
    for ch in channels:
        for spec in XML_SETTINGS:
            path = spec.path.format(ch=ch)
            if path not in docs:
                docs[path] = await client.try_get_xml(path)
            doc = docs[path]
            if doc is None or doc.find(spec.element) is None:
                continue
            if spec.kind != "bool" and path not in caps:
                caps[path] = await client.try_get_xml(path + "/capabilities")
            cap = caps.get(path)
            if cap is not None and cap.find(spec.element) is None:
                # Present in the document but not writable on this model.
                continue
            options = options_of(cap, spec.element) or list(spec.fallback_options)
            if spec.kind == "select":
                current = text_of(doc, spec.element)
                if current and current not in options:
                    options.append(current)
            settings.append(
                BoundSetting(
                    spec=spec,
                    channel=ch,
                    path=path,
                    options=options,
                    range=range_of(cap, spec.element) or spec.fallback_range,
                )
            )

    features = Features(channels=channels, settings=settings)

    motion_caps = await client.try_get_xml(
        f"/ISAPI/System/Video/inputs/channels/{channels[0]}/motionDetection/capabilities"
    )
    smart_caps = await client.try_get_xml("/ISAPI/Smart/capabilities")
    blob = b"".join(ET.tostring(x) for x in (motion_caps, smart_caps) if x is not None).lower()
    features.human_vehicle = any(k in blob for k in (b"targettype", b"humanvehicle", b"detectiontarget"))

    audio = await client.try_get_json(AUDIO_ALARM)
    audio_caps = await client.try_get_json(AUDIO_ALARM_CAPS)
    if audio and "AudioAlarm" in audio:
        cap = (audio_caps or {}).get("AudioAlarmCap", {})
        sounds = {
            int(s["audioID"]): s.get("audioDescription") or f"Sound {s['audioID']}"
            for s in cap.get("audioTypeListCap", [])
            if "audioID" in s
        }
        current = audio["AudioAlarm"].get("audioID")
        if current is not None and int(current) not in sounds:
            sounds[int(current)] = f"Sound {current}"

        def _rng(name: str) -> tuple[int, int] | None:
            r = cap.get(name)
            if isinstance(r, dict) and "min" in r and "max" in r:
                return int(r["min"]), int(r["max"])
            return None

        features.audio_alarm = AudioAlarmInfo(
            sounds=sounds,
            volume=_rng("audioVolume") or (1, 100),
            repeats=_rng("alarmTimes"),
        )

    io_in = await client.try_get_xml("/ISAPI/System/IO/inputs")
    io_out = await client.try_get_xml("/ISAPI/System/IO/outputs")
    features.io_inputs = [text_of(p, "id") for p in (io_in.iter("IOInputPort") if io_in is not None else []) if text_of(p, "id")]
    features.io_outputs = [text_of(p, "id") for p in (io_out.iter("IOOutputPort") if io_out is not None else []) if text_of(p, "id")]

    for ch in channels:
        ptz_caps = await client.try_get_xml(f"/ISAPI/PTZCtrl/channels/{ch}/capabilities")
        if ptz_caps is not None:
            raw = ET.tostring(ptz_caps).lower()
            if b"continuous" in raw or b"presetnum" in raw or b"abs" in raw:
                features.ptz_channels.append(ch)
            if b"wiper" in raw:
                features.wiper_channels.append(ch)
        focus = await client.try_get_xml(f"/ISAPI/Image/channels/{ch}/focusConfiguration")
        if focus is not None:
            features.focus_channels.append(ch)

    features.has_status = await client.try_get_xml(SYSTEM_STATUS) is not None
    storage = await client.try_get_xml(STORAGE)
    features.has_storage = storage is not None and storage.find(".//hdd") is not None
    features.has_two_way_audio = (
        await client.try_get_xml("/ISAPI/System/TwoWayAudio/channels") is not None
    )
    return features


class AnnkeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls every settings document the camera supports."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: IsapiClient,
        info: DeviceInfo,
        features: Features,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {info.name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.info = info
        self.features = features
        self._lock = asyncio.Lock()

    def _error(self, err: IsapiError) -> HomeAssistantError:
        if isinstance(err, IsapiForbidden):
            return HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="forbidden",
                translation_placeholders={"name": self.info.name},
            )
        return HomeAssistantError(f"{self.info.name}: {err}")

    @property
    def xml_paths(self) -> list[str]:
        return sorted({s.path for s in self.features.settings})

    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        try:
            for path in self.xml_paths:
                data[path] = await self.client.try_get_xml(path)
            if self.features.audio_alarm:
                data[AUDIO_ALARM] = await self.client.try_get_json(AUDIO_ALARM)
            for port in self.features.io_outputs:
                data[f"io_out_{port}"] = await self.client.try_get_xml(
                    f"/ISAPI/System/IO/outputs/{port}/status"
                )
            if self.features.has_status:
                data[SYSTEM_STATUS] = await self.client.try_get_xml(SYSTEM_STATUS)
            if self.features.has_storage:
                data[STORAGE] = await self.client.try_get_xml(STORAGE)
        except IsapiAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except IsapiError as err:
            raise UpdateFailed(str(err)) from err
        if self.xml_paths and all(data.get(p) is None for p in self.xml_paths):
            raise UpdateFailed(f"{self.client.host} did not answer")
        return data

    def value(self, setting: BoundSetting) -> str | None:
        return text_of(self.data.get(setting.path), setting.spec.element) if self.data else None

    async def async_set_values(self, path: str, changes: dict[str, Any]) -> None:
        """Write fields into a settings document and refresh local state."""
        async with self._lock:
            try:
                root = await self.client.update_xml(path, changes)
            except IsapiAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except IsapiError as err:
                raise self._error(err) from err
        self.async_set_updated_data({**self.data, path: root})

    async def async_set_audio_alarm(self, changes: dict[str, Any]) -> None:
        current = (self.data or {}).get(AUDIO_ALARM) or await self.client.get_json(AUDIO_ALARM)
        body = {"AudioAlarm": {**current["AudioAlarm"], **changes}}
        try:
            await self.client.put_json(AUDIO_ALARM, body)
        except IsapiError as err:
            raise self._error(err) from err
        self.async_set_updated_data({**self.data, AUDIO_ALARM: body})

    async def async_test_audio_alarm(self) -> None:
        current = ((self.data or {}).get(AUDIO_ALARM) or {}).get("AudioAlarm", {})
        audio_id = current.get("audioID", 1)
        try:
            await self.client.put_json(
                f"/ISAPI/Event/triggers/notifications/AudioAlarm/{audio_id}/test?format=json"
            )
        except IsapiError as err:
            raise self._error(err) from err

    async def async_set_output(self, port: str, on: bool) -> None:
        body = (
            "<IOPortData><outputState>"
            + ("high" if on else "low")
            + "</outputState></IOPortData>"
        ).encode()
        try:
            await self.client.put_raw(f"/ISAPI/System/IO/outputs/{port}/trigger", body)
        except IsapiError as err:
            raise self._error(err) from err
        await self.async_request_refresh()

    async def async_missing_linkage(self) -> list[str]:
        """Event triggers that do not notify the surveillance center (alert stream)."""
        triggers = await self.client.try_get_xml("/ISAPI/Event/triggers")
        if triggers is None:
            return []
        missing = []
        for trig in triggers.iter("EventTrigger"):
            etype = text_of(trig, "eventType") or ""
            if etype.lower() not in {t.lower() for t in LINKAGE_TRIGGERS}:
                continue
            methods = {(m.text or "").strip() for m in trig.iter("notificationMethod")}
            if "center" not in methods:
                missing.append(text_of(trig, "id") or etype)
        return missing

    async def async_enable_linkage(self) -> list[str]:
        """Add 'notify surveillance center' to every event trigger missing it."""
        fixed = []
        for trigger_id in await self.async_missing_linkage():
            path = f"/ISAPI/Event/triggers/{trigger_id}"
            try:
                root = await self.client.get_xml(path)
                lst = root.find("EventTriggerNotificationList")
                if lst is None:
                    lst = ET.SubElement(root, "EventTriggerNotificationList")
                note = ET.SubElement(lst, "EventTriggerNotification")
                for tag, val in (
                    ("id", "center"),
                    ("notificationMethod", "center"),
                    ("notificationRecurrence", "beginning"),
                ):
                    ET.SubElement(note, tag).text = val
                await self.client.put_xml(path, root)
                fixed.append(trigger_id)
            except IsapiError as err:
                _LOGGER.warning("%s: could not update %s: %s", self.info.name, trigger_id, err)
        return fixed

    async def async_ptz(self, channel: int, pan: int, tilt: int, zoom: int, duration: float) -> None:
        path = f"/ISAPI/PTZCtrl/channels/{channel}/continuous"
        move = f"<PTZData><pan>{pan}</pan><tilt>{tilt}</tilt><zoom>{zoom}</zoom></PTZData>"
        stop = "<PTZData><pan>0</pan><tilt>0</tilt><zoom>0</zoom></PTZData>"
        try:
            await self.client.put_raw(path, move.encode())
            await asyncio.sleep(duration)
            await self.client.put_raw(path, stop.encode())
        except IsapiError as err:
            raise self._error(err) from err

    async def async_goto_preset(self, channel: int, preset: int) -> None:
        try:
            await self.client.put_raw(f"/ISAPI/PTZCtrl/channels/{channel}/presets/{preset}/goto", b"")
        except IsapiError as err:
            raise self._error(err) from err

    async def async_wiper(self, channel: int) -> None:
        path = f"/ISAPI/PTZCtrl/channels/{channel}/auxcontrols/1"
        try:
            for status in ("on", "off"):
                body = f"<PTZAux><id>1</id><type>WIPER</type><status>{status}</status></PTZAux>"
                await self.client.put_raw(path, body.encode())
                if status == "on":
                    await asyncio.sleep(3)
        except IsapiError as err:
            raise self._error(err) from err

    async def async_focus(self, channel: int) -> None:
        try:
            # "foucs" is how the firmware spells it.
            await self.client.put_raw(f"/ISAPI/PTZCtrl/channels/{channel}/onepushfoucs/start", b"")
        except IsapiError as err:
            raise self._error(err) from err

    async def async_reboot(self) -> None:
        try:
            await self.client.reboot()
        except IsapiError as err:
            raise self._error(err) from err


def output_active(data: dict[str, Any] | None, port: str) -> bool | None:
    state = text_of((data or {}).get(f"io_out_{port}"), "ioState")
    return None if state is None else state.lower() == "active"


def set_bool(root: ET.Element, element: str, value: bool) -> bool:
    return set_text(root, element, value)
