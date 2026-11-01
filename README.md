# Annke for Home Assistant

Local control of Annke IP cameras from Home Assistant: the ColorVu white
light, infrared, day/night mode, siren and strobe, detections and real-time
events. It talks to the camera directly over Hikvision ISAPI (the firmware
inside most Annke IP cameras) on your network. No cloud, no YAML.

The integration probes each camera when you add it and only creates the
entities that camera actually supports, so the same code works for a basic
turret and for a 4K camera with a siren and a strobe.

## Features

| Area | Entities |
| --- | --- |
| Light | White light switch, supplement light mode (white / infrared / smart / off), white and IR brightness, auto or manual brightness control |
| Day/night | Mode (auto, day, night, schedule), sensitivity, switch delay |
| Live events | Motion, person, vehicle, intrusion, line crossing, region entrance and exit, tampering, scene change, defocus, audio exception, PIR, alarm inputs |
| Detection settings | Turn motion, intrusion, line crossing, region, tampering, scene change detection and the privacy mask on or off |
| Active deterrence | Siren sound, volume, repeat count and a test button; strobe duration and frequency |
| Hardware | Alarm outputs, wiper, auto focus, PTZ (`annke.ptz_move`, `annke.goto_preset`), dual-lens cameras |
| Video | Main and sub stream (RTSP) with snapshots |
| Diagnostics | CPU, memory, last boot, SD card status and free space, reboot, event connection |

Every event is also fired once on the event bus as `annke_event`, with the
camera serial, event type, target, region and channel, for automations.

Translations: English, Polish (polski), German (Deutsch).

## Supported cameras

Any Annke IP camera that answers on `http://<camera>/ISAPI/System/deviceInfo`
should work. Tested with:

| Model | Notes |
| --- | --- |
| I81HE | ColorVu white light, motion |
| I51DS | Infrared only, motion |

Annke NVRs, and cameras that only speak ONVIF or XMeye, are not supported.
Reports for other models are welcome; see [Reporting a camera](#reporting-a-camera).

## Installation

### HACS

1. HACS → three dots → **Custom repositories**.
2. Add `https://github.com/lespod/ha-annke` with type **Integration**.
3. Install **Annke** and restart Home Assistant.

### Manual

Copy `custom_components/annke` into `<config>/custom_components/annke` and
restart Home Assistant.

Home Assistant 2025.2 or newer is required. The integration icon is shown
from Home Assistant 2026.3 onwards.

## Setup

**Settings → Devices & services → Add integration → Annke**, then enter the
camera address, user name and password.

### Camera account and permissions

Create a separate user on the camera for Home Assistant. It needs the
**Remote: Parameters Settings** permission, otherwise reading works but every
change fails with HTTP 403 and Home Assistant shows a "not allowed to change
settings" error. An administrator account also works.

The password is stored by Home Assistant in `.storage`, like for any other
integration, not in your YAML files.

To change the address or account later: the integration's three-dot menu →
**Reconfigure**. Leave the password empty to keep the saved one.

### Events

Real-time sensors only receive events the camera sends to the "surveillance
center". If an event type has that linkage turned off, Home Assistant shows a
repair issue listing it. Press **Enable event notifications** on the device
page, or enable **Notify Surveillance Center** in the camera's web interface
under *Event → Linkage Action*.

**Person** and **Vehicle** only turn on when the camera classifies targets.
Enable a human/vehicle detection target in the camera's motion or smart event
settings (AcuSense models); without it the camera only reports plain motion.

## Things to know

- **White light in day mode.** ColorVu cameras keep the white light dark while
  they are in day mode, whatever the light mode says. In *auto* the camera's
  light sensor decides, and street lights can keep it in day mode after dark.
  If the light does not come on, set day/night to *night*.
- **Siren test** plays the selected sound for a few seconds; longer manual
  alarms are not available over ISAPI.
- **Strobe** can be configured, but not triggered manually; the camera fires
  it on events.
- **Options:** how long a detection stays on after the camera's last alert
  (default 5 s).

## Reporting a camera

`tools/probe_cameras.py` reads a camera's capabilities (GET requests only)
and saves the answers, which makes adding a model much easier:

```bash
python3 tools/probe_cameras.py 192.168.1.64
```

It asks for the user name and a hidden password, and writes
`camera_dumps/<address>/`. Check the files before attaching them to an issue;
they contain the camera's serial number and MAC address.

On macOS, run it from the Terminal app: terminals inside other apps may not
have the *Local Network* permission and fail with "No route to host".

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check custom_components tests tools
```

The tests run the integration in a real Home Assistant against an in-memory
camera (`tests/fake_camera.py`).

User-facing texts live in `tools/gen_translations.py` as English, Polish and
German triples. Edit them there and run `python3 tools/gen_translations.py`
to regenerate `strings.json` and `translations/`.

## License

[MIT](LICENSE)

This project is not affiliated with Annke or Hikvision.
