"""End-to-end tests against the fake camera."""

from __future__ import annotations

from datetime import timedelta
import json

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util

from custom_components.annke.isapi import parse_event, split_alerts

from .conftest import DATA
from .fake_camera import FakeCamera

SERIAL = "NC500-TEST-001"


def eid(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, "annke", f"{SERIAL}_{key}")
    assert entity_id, f"no {platform} {key}"
    return entity_id


async def test_config_flow(hass: HomeAssistant, patch_client) -> None:
    result = await hass.config_entries.flow.async_init("annke", context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DATA, "username": "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brama (NC500)"
    assert result["result"].unique_id == SERIAL


async def test_entities_created(hass: HomeAssistant, setup_entry) -> None:
    for platform, key in [
        ("switch", "white_light_1"),
        ("switch", "motion_detection_1"),
        ("switch", "intrusion_detection_1"),
        ("switch", "alarm_output_1"),
        ("select", "supplement_light_mode_1"),
        ("select", "day_night_mode_1"),
        ("select", "strobe_frequency_1"),
        ("select", "siren_sound"),
        ("number", "white_light_brightness_1"),
        ("number", "siren_volume"),
        ("binary_sensor", "motion_1"),
        ("binary_sensor", "human_1"),
        ("binary_sensor", "line_crossing_1"),
        ("binary_sensor", "event_stream"),
        ("sensor", "cpu"),
        ("sensor", "storage_free"),
        ("button", "reboot"),
        ("button", "siren_test"),
        ("button", "wiper_1"),
        ("camera", "main_stream_1"),
    ]:
        eid(hass, platform, key)
    # No region entrance on this camera -> no entity.
    assert er.async_get(hass).async_get_entity_id("binary_sensor", "annke", f"{SERIAL}_region_entrance_1") is None
    assert hass.states.get(eid(hass, "switch", "white_light_1")).state == "off"
    assert hass.states.get(eid(hass, "switch", "motion_detection_1")).state == "on"
    assert hass.states.get(eid(hass, "select", "day_night_mode_1")).state == "auto"
    assert hass.states.get(eid(hass, "sensor", "cpu")).state == "12.0"
    device = dr.async_get(hass).async_get_device({("annke", SERIAL)})
    assert device.model == "NC500" and device.manufacturer == "Annke"


async def test_white_light(hass: HomeAssistant, setup_entry, camera: FakeCamera) -> None:
    entity_id = eid(hass, "switch", "white_light_1")
    await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    path, body = camera.puts[-1]
    assert path == "/ISAPI/Image/channels/1/supplementLight"
    assert "<supplementLightMode>colorVuWhiteLight</supplementLightMode>" in body
    assert "<mixedLightBrightnessRegulatMode>manual</mixedLightBrightnessRegulatMode>" in body
    assert 'xmlns="http://www.std-cgi.com/ver20/XMLSchema"' in body
    assert hass.states.get(entity_id).state == "on"
    assert hass.states.get(eid(hass, "select", "supplement_light_mode_1")).state == "color_vu_white_light"

    # Day/night mode is left alone.
    assert not any(p == "/ISAPI/Image/channels/1/IrcutFilter" for p, _ in camera.puts)
    assert hass.states.get(eid(hass, "select", "day_night_mode_1")).state == "auto"

    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    assert "<supplementLightMode>close</supplementLightMode>" in camera.puts[-1][1]
    assert hass.states.get(entity_id).state == "off"


async def test_select_and_number(hass: HomeAssistant, setup_entry, camera: FakeCamera) -> None:
    await hass.services.async_call(
        "select", "select_option", {"entity_id": eid(hass, "select", "day_night_mode_1"), "option": "night"}, blocking=True
    )
    assert camera.puts[-1][0] == "/ISAPI/Image/channels/1/IrcutFilter"
    assert "<IrcutFilterType>night</IrcutFilterType>" in camera.puts[-1][1]

    await hass.services.async_call(
        "number", "set_value", {"entity_id": eid(hass, "number", "white_light_brightness_1"), "value": 40}, blocking=True
    )
    assert "<whiteLightBrightness>40</whiteLightBrightness>" in camera.puts[-1][1]

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": eid(hass, "switch", "intrusion_detection_1")}, blocking=True
    )
    assert camera.puts[-1][0] == "/ISAPI/Smart/FieldDetection/1"
    assert "<enabled>true</enabled>" in camera.puts[-1][1]


async def test_siren(hass: HomeAssistant, setup_entry, camera: FakeCamera) -> None:
    sound = eid(hass, "select", "siren_sound")
    assert hass.states.get(sound).state == "1: Siren"
    await hass.services.async_call(
        "select", "select_option", {"entity_id": sound, "option": "2: Warning, this is a protected area"}, blocking=True
    )
    assert json.loads(camera.puts[-1][1])["AudioAlarm"]["audioID"] == 2
    await hass.services.async_call(
        "number", "set_value", {"entity_id": eid(hass, "number", "siren_volume"), "value": 55}, blocking=True
    )
    assert camera.audio["AudioAlarm"]["audioVolume"] == 55
    assert camera.audio["AudioAlarm"]["audioID"] == 2
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, "button", "siren_test")}, blocking=True)
    assert camera.puts[-1][0] == "/ISAPI/Event/triggers/notifications/AudioAlarm/2/test?format=json"


async def test_alarm_output(hass: HomeAssistant, setup_entry, camera: FakeCamera) -> None:
    await hass.services.async_call("switch", "turn_on", {"entity_id": eid(hass, "switch", "alarm_output_1")}, blocking=True)
    assert camera.puts[-1] == ("/ISAPI/System/IO/outputs/1/trigger", "<IOPortData><outputState>high</outputState></IOPortData>")


async def test_events(hass: HomeAssistant, setup_entry) -> None:
    hub = setup_entry.runtime_data.events
    fired = []
    hass.bus.async_listen("annke_event", fired.append)
    doc = b"""--boundary\r\nContent-Type: application/xml\r\n\r\n<?xml version="1.0"?>
<EventNotificationAlert version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<ipAddress>192.168.0.30</ipAddress><channelID>1</channelID><eventType>VMD</eventType>
<eventState>active</eventState><eventDescription>Motion alarm</eventDescription>
<DetectionRegionList><DetectionRegionEntry><regionID>1</regionID><targetType>human</targetType></DetectionRegionEntry></DetectionRegionList>
</EventNotificationAlert>\r\n--boundary\r\n<EventNotificationAlert><eventType>videoloss</eventType><eventState>inactive</eventState>"""
    docs, rest = split_alerts(doc)
    assert len(docs) == 1 and rest.startswith(b"<EventNotificationAlert")
    for _ in range(5):  # the camera repeats "active" while motion lasts
        hub._on_event(parse_event(docs[0]))
    await hass.async_block_till_done()
    assert len(fired) == 1
    assert hass.states.get(eid(hass, "binary_sensor", "motion_1")).state == "on"
    assert hass.states.get(eid(hass, "binary_sensor", "human_1")).state == "on"
    assert hass.states.get(eid(hass, "binary_sensor", "line_crossing_1")).state == "off"
    assert fired and fired[0].data["target"] == "human"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "binary_sensor", "motion_1")).state == "off"
    assert hass.states.get(eid(hass, "binary_sensor", "human_1")).state == "off"


async def test_linkage_issue_and_fix(hass: HomeAssistant, setup_entry, camera: FakeCamera) -> None:
    issues = ir.async_get(hass)
    assert issues.async_get_issue("annke", f"linkage_{SERIAL}") is not None
    # Fixing writes the trigger with a "center" notification.
    camera.docs["/ISAPI/Event/triggers"] = camera.docs["/ISAPI/Event/triggers"].replace(
        "<id>record</id><notificationMethod>record</notificationMethod>",
        "<id>center</id><notificationMethod>center</notificationMethod>",
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": eid(hass, "button", "enable_event_linkage")}, blocking=True
    )
    assert issues.async_get_issue("annke", f"linkage_{SERIAL}") is None


async def test_ptz_and_wiper(hass: HomeAssistant, setup_entry, camera: FakeCamera) -> None:
    device = dr.async_get(hass).async_get_device({("annke", SERIAL)})
    await hass.services.async_call(
        "annke", "ptz_move", {"device_id": device.id, "pan": 50, "duration": 0.1}, blocking=True
    )
    assert camera.puts[-2] == ("/ISAPI/PTZCtrl/channels/1/continuous", "<PTZData><pan>50</pan><tilt>0</tilt><zoom>0</zoom></PTZData>")
    assert "<pan>0</pan>" in camera.puts[-1][1]


async def test_unload(hass: HomeAssistant, setup_entry) -> None:
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()


async def test_every_entity_has_translated_name(hass: HomeAssistant, setup_entry) -> None:
    for lang in ("en", "pl", "de"):
        hass.config.language = lang
        await hass.config_entries.async_reload(setup_entry.entry_id)
        await hass.async_block_till_done()
        reg = er.async_get(hass)
        names = {}
        for entry in er.async_entries_for_config_entry(reg, setup_entry.entry_id):
            state = hass.states.get(entry.entity_id)
            if state is None:  # disabled by default
                continue
            name = state.attributes.get("friendly_name") or ""
            assert name.startswith("Brama ") and len(name) > len("Brama "), (lang, entry.unique_id, name)
            names[entry.unique_id] = name
        if lang == "pl":
            assert names[f"{SERIAL}_white_light_1"] == "Brama Biała dioda"
            assert names[f"{SERIAL}_alarm_output_1"] == "Brama Wyjście alarmowe 1"
        if lang == "de":
            assert names[f"{SERIAL}_white_light_1"] == "Brama Weißlicht"


async def test_undeclared_field_has_no_entity(hass: HomeAssistant, setup_entry) -> None:
    # irLightBrightness is in the document but not in capabilities (as on the NC500).
    assert er.async_get(hass).async_get_entity_id("number", "annke", f"{SERIAL}_ir_light_brightness_1") is None


async def test_read_only_account(hass: HomeAssistant, setup_entry, camera: FakeCamera) -> None:
    import pytest
    from homeassistant.exceptions import HomeAssistantError

    camera.read_only = True
    before = len(camera.puts)
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": eid(hass, "switch", "white_light_1")}, blocking=True
        )
    assert exc.value.translation_key == "forbidden"
    assert len(camera.puts) == before + 1  # no pointless retries on 403


async def test_reconfigure_changes_account(hass: HomeAssistant, setup_entry) -> None:
    result = await setup_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.0.30", "username": "admin", "password": "", "port": 80, "ssl": False}
    )
    assert result["reason"] == "reconfigure_successful"
    assert setup_entry.data["password"] == "secret"  # empty keeps the old one
    result = await setup_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.0.30", "username": "admin2", "password": "new", "port": 80, "ssl": False}
    )
    assert setup_entry.data["username"] == "admin2" and setup_entry.data["password"] == "new"
