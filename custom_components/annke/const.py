"""Constants and feature tables for the Annke integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

DOMAIN: Final = "annke"

CONF_OFF_DELAY: Final = "off_delay"
DEFAULT_OFF_DELAY: Final = 5
DEFAULT_SCAN_INTERVAL: Final = 30
EVENT_ANNKE: Final = "annke_event"

SettingKind = Literal["bool", "select", "number"]


@dataclass(frozen=True, kw_only=True)
class XmlSetting:
    """A single field in an ISAPI XML document exposed as an entity.

    ``path`` may contain ``{ch}`` for the video channel. Options and ranges
    are read from ``path + "/capabilities"``; ``fallback_options`` and
    ``fallback_range`` are used when the device has no capabilities document.
    """

    key: str
    path: str
    element: str
    kind: SettingKind
    config: bool = True
    enabled_default: bool = True
    fallback_options: tuple[str, ...] = ()
    fallback_range: tuple[int, int] | None = None
    unit: str | None = None
    icon: str | None = None


SUPPLEMENT_LIGHT = "/ISAPI/Image/channels/{ch}/supplementLight"
IRCUT = "/ISAPI/Image/channels/{ch}/IrcutFilter"
WHITE_LIGHT_ALARM = "/ISAPI/Event/triggers/notifications/channels/{ch}/whiteLightAlarm"

XML_SETTINGS: Final[tuple[XmlSetting, ...]] = (
    # Supplement light (ColorVu white LED, IR, smart hybrid light)
    XmlSetting(
        key="supplement_light_mode",
        path=SUPPLEMENT_LIGHT,
        element="supplementLightMode",
        kind="select",
        config=False,
        fallback_options=("colorVuWhiteLight", "irLight", "eventIntelligence", "close"),
        icon="mdi:lightbulb-auto",
    ),
    XmlSetting(
        key="light_brightness_mode",
        path=SUPPLEMENT_LIGHT,
        element="mixedLightBrightnessRegulatMode",
        kind="select",
        fallback_options=("auto", "manual"),
    ),
    XmlSetting(
        key="white_light_brightness",
        path=SUPPLEMENT_LIGHT,
        element="whiteLightBrightness",
        kind="number",
        config=False,
        fallback_range=(0, 100),
        unit="%",
        icon="mdi:brightness-6",
    ),
    XmlSetting(
        key="ir_light_brightness",
        path=SUPPLEMENT_LIGHT,
        element="irLightBrightness",
        kind="number",
        fallback_range=(0, 100),
        unit="%",
    ),
    XmlSetting(
        key="white_light_brightness_limit",
        path=SUPPLEMENT_LIGHT,
        element="whiteLightbrightLimit",
        kind="number",
        enabled_default=False,
        fallback_range=(0, 100),
        unit="%",
    ),
    # Day/night (IR cut filter)
    XmlSetting(
        key="day_night_mode",
        path=IRCUT,
        element="IrcutFilterType",
        kind="select",
        config=False,
        fallback_options=("auto", "day", "night", "schedule"),
        icon="mdi:theme-light-dark",
    ),
    XmlSetting(
        key="day_night_sensitivity",
        path=IRCUT,
        element="nightToDayFilterLevel",
        kind="number",
        enabled_default=False,
        fallback_range=(0, 7),
    ),
    XmlSetting(
        key="day_night_delay",
        path=IRCUT,
        element="nightToDayFilterTime",
        kind="number",
        enabled_default=False,
        fallback_range=(5, 120),
        unit="s",
    ),
    # Detection switches
    XmlSetting(key="motion_detection", path="/ISAPI/System/Video/inputs/channels/{ch}/motionDetection", element="enabled", kind="bool", icon="mdi:motion-sensor"),
    XmlSetting(key="tamper_detection", path="/ISAPI/System/Video/inputs/channels/{ch}/tamperDetection", element="enabled", kind="bool", icon="mdi:eye-off"),
    XmlSetting(key="intrusion_detection", path="/ISAPI/Smart/FieldDetection/{ch}", element="enabled", kind="bool", icon="mdi:shield-alert"),
    XmlSetting(key="line_crossing_detection", path="/ISAPI/Smart/LineDetection/{ch}", element="enabled", kind="bool", icon="mdi:vector-line"),
    XmlSetting(key="region_entrance_detection", path="/ISAPI/Smart/regionEntrance/{ch}", element="enabled", kind="bool", icon="mdi:location-enter"),
    XmlSetting(key="region_exiting_detection", path="/ISAPI/Smart/regionExiting/{ch}", element="enabled", kind="bool", icon="mdi:location-exit"),
    XmlSetting(key="scene_change_detection", path="/ISAPI/Smart/SceneChangeDetection/{ch}", element="enabled", kind="bool", icon="mdi:image-edit"),
    XmlSetting(key="defocus_detection", path="/ISAPI/Smart/DefocusDetection/{ch}", element="enabled", kind="bool", enabled_default=False, icon="mdi:image-filter-tilt-shift"),
    XmlSetting(key="audio_exception_detection", path="/ISAPI/Smart/AudioDetection/channels/{ch}", element="AudioException/enabled", kind="bool", enabled_default=False, icon="mdi:microphone"),
    XmlSetting(key="privacy_mask", path="/ISAPI/System/Video/inputs/channels/{ch}/privacyMask", element="enabled", kind="bool", icon="mdi:incognito"),
    # Image
    XmlSetting(key="wdr_mode", path="/ISAPI/Image/channels/{ch}/WDR", element="mode", kind="select", enabled_default=False, fallback_options=("open", "close", "auto")),
    XmlSetting(key="image_flip", path="/ISAPI/Image/channels/{ch}/imageFlip", element="enabled", kind="bool", enabled_default=False),
    # Active deterrence: strobe (flashing light alarm)
    XmlSetting(key="strobe_duration", path=WHITE_LIGHT_ALARM, element="durationTime", kind="number", fallback_range=(1, 60), unit="s", icon="mdi:alarm-light"),
    XmlSetting(key="strobe_frequency", path=WHITE_LIGHT_ALARM, element="frequency", kind="select", fallback_options=("high", "medium", "low", "normallyOn"), icon="mdi:alarm-light"),
)


@dataclass(frozen=True, kw_only=True)
class EventSpec:
    """A binary sensor fed by the alert stream."""

    key: str
    event_types: tuple[str, ...] = ()
    target: str | None = None
    device_class: str = "motion"
    # Setting key whose presence on the device means the event is available.
    requires: str | None = None


EVENTS: Final[tuple[EventSpec, ...]] = (
    EventSpec(key="motion", event_types=("vmd", "motiondetection", "vmdhumanvehicle"), requires="motion_detection"),
    EventSpec(key="human", target="human", device_class="occupancy"),
    EventSpec(key="vehicle", target="vehicle", device_class="motion"),
    EventSpec(key="intrusion", event_types=("fielddetection",), requires="intrusion_detection"),
    EventSpec(key="line_crossing", event_types=("linedetection",), requires="line_crossing_detection"),
    EventSpec(key="region_entrance", event_types=("regionentrance",), requires="region_entrance_detection"),
    EventSpec(key="region_exiting", event_types=("regionexiting",), requires="region_exiting_detection"),
    EventSpec(key="tamper", event_types=("shelteralarm", "tamperdetection"), device_class="tamper", requires="tamper_detection"),
    EventSpec(key="scene_change", event_types=("scenechangedetection",), device_class="problem", requires="scene_change_detection"),
    EventSpec(key="defocus", event_types=("defocus", "defocusdetection"), device_class="problem", requires="defocus_detection"),
    EventSpec(key="audio_exception", event_types=("audioexception",), device_class="sound", requires="audio_exception_detection"),
    EventSpec(key="pir", event_types=("pir", "pirdetection"), device_class="motion"),
)

# Event triggers whose "notify surveillance center" linkage feeds the alert stream.
LINKAGE_TRIGGERS: Final = (
    "VMD",
    "shelteralarm",
    "fielddetection",
    "linedetection",
    "regionEntrance",
    "regionExiting",
    "scenechangedetection",
)
