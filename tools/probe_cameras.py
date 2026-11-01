#!/usr/bin/env python3
"""Read-only dump of Hikvision/Annke ISAPI capabilities.

Usage: python3 tools/probe_cameras.py <camera address> [<camera address> ...]

Asks for the password interactively and only performs GET requests.
Responses are written to camera_dumps/<address>/ in the current directory.
The files contain the camera's serial number and MAC address; review them
before sharing.
"""
import getpass
import pathlib
import sys
import urllib.error
import urllib.request


PATHS = [
    "/ISAPI/System/deviceInfo",
    "/ISAPI/System/capabilities",
    "/ISAPI/System/status",
    "/ISAPI/System/Hardware",
    "/ISAPI/System/Hardware/capabilities",
    "/ISAPI/System/IO/inputs",
    "/ISAPI/System/IO/outputs",
    "/ISAPI/System/IO/capabilities",
    "/ISAPI/System/Video/inputs/channels",
    "/ISAPI/System/Video/inputs/channels/1/motionDetection",
    "/ISAPI/System/Video/inputs/channels/1/motionDetection/capabilities",
    "/ISAPI/System/Video/inputs/channels/1/tamperDetection",
    "/ISAPI/System/Video/inputs/channels/1/privacyMask",
    "/ISAPI/System/Audio/channels",
    "/ISAPI/System/TwoWayAudio/channels",
    "/ISAPI/Image/channels",
    "/ISAPI/Image/channels/1",
    "/ISAPI/Image/channels/1/capabilities",
    "/ISAPI/Image/channels/1/supplementLight",
    "/ISAPI/Image/channels/1/supplementLight/capabilities",
    "/ISAPI/Image/channels/1/IrcutFilter",
    "/ISAPI/Image/channels/1/IrcutFilter/capabilities",
    "/ISAPI/Image/channels/1/WDR",
    "/ISAPI/Image/channels/1/BLC",
    "/ISAPI/Image/channels/1/imageFlip",
    "/ISAPI/Image/channels/1/color",
    "/ISAPI/Event/capabilities",
    "/ISAPI/Event/channels/capabilities",
    "/ISAPI/Event/triggers",
    "/ISAPI/Event/notification/httpHosts",
    "/ISAPI/Event/triggers/notifications/channels/1/whiteLightAlarm",
    "/ISAPI/Event/triggers/notifications/channels/1/whiteLightAlarm/capabilities",
    "/ISAPI/Event/triggers/notifications/AudioAlarm",
    "/ISAPI/Event/triggers/notifications/AudioAlarm/capabilities",
    "/ISAPI/Smart/capabilities",
    "/ISAPI/Smart/FieldDetection/1",
    "/ISAPI/Smart/LineDetection/1",
    "/ISAPI/Smart/regionEntrance/1",
    "/ISAPI/Smart/regionExiting/1",
    "/ISAPI/Smart/SceneChangeDetection/1",
    "/ISAPI/Smart/AudioDetection/channels/1",
    "/ISAPI/Smart/channels/1/smartOverlap",
    "/ISAPI/Streaming/channels",
    "/ISAPI/ContentMgmt/Storage",
    "/ISAPI/ContentMgmt/capabilities",
    "/ISAPI/PTZCtrl/channels",
]


def main() -> None:
    cameras = sys.argv[1:]
    if not cameras:
        sys.exit(__doc__)
    user = input("User name [admin]: ").strip() or "admin"
    password = getpass.getpass(f"Password for {user} (hidden): ")
    out_root = pathlib.Path.cwd() / "camera_dumps"

    for ip in cameras:
        base = f"http://{ip}"
        mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, base, user, password)
        opener = urllib.request.build_opener(
            urllib.request.HTTPDigestAuthHandler(mgr)
        )
        out = out_root / ip
        out.mkdir(parents=True, exist_ok=True)
        summary = []
        for path in PATHS:
            name = path.strip("/").replace("/", "_") + ".xml"
            try:
                with opener.open(base + path, timeout=8) as resp:
                    body = resp.read()
                    status = resp.status
            except urllib.error.HTTPError as err:
                body, status = err.read(), err.code
            except Exception as err:  # noqa: BLE001
                body, status = str(err).encode(), "ERR"
            (out / name).write_bytes(body)
            summary.append(f"{status}\t{path}")
            if status == 401:
                print(f"{ip}: 401 - wrong user name or password, skipping this camera.")
                break
        (out / "_summary.txt").write_text("\n".join(summary) + "\n")
        ok = sum(1 for s in summary if s.startswith("200"))
        print(f"{ip}: saved {len(summary)} answers, {ok} with HTTP 200 -> {out}")
        if ok == 0 and any(s.startswith("ERR") for s in summary):
            print("  No answers at all. On macOS, run this from the Terminal app (Local Network permission).")


if __name__ == "__main__":
    main()
