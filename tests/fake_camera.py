"""An in-memory ISAPI camera for tests, served through httpx.MockTransport."""

from __future__ import annotations

import json
import re

import httpx

NS = 'xmlns="http://www.hikvision.com/ver20/XMLSchema"'
STD = 'xmlns="http://www.std-cgi.com/ver20/XMLSchema"'
BAD = f'<?xml version="1.0" encoding="UTF-8"?><ResponseStatus {NS}><statusCode>6</statusCode><statusString>Invalid Content</statusString><subStatusCode>badXmlContent</subStatusCode></ResponseStatus>'
OK = f'<?xml version="1.0" encoding="UTF-8"?><ResponseStatus {NS}><statusCode>1</statusCode><statusString>OK</statusString></ResponseStatus>'


def default_docs() -> dict[str, str]:
    return {
        "/ISAPI/System/deviceInfo": f"""<DeviceInfo {NS}><deviceName>Brama</deviceName><model>NC500</model>
            <serialNumber>NC500-TEST-001</serialNumber><macAddress>aa:bb:cc:dd:ee:ff</macAddress>
            <firmwareVersion>V5.7.3</firmwareVersion><firmwareReleasedDate>build 230101</firmwareReleasedDate>
            <deviceType>IPCamera</deviceType></DeviceInfo>""",
        "/ISAPI/System/Video/inputs/channels": f"""<VideoInputChannelList {NS}><VideoInputChannel><id>1</id></VideoInputChannel></VideoInputChannelList>""",
        "/ISAPI/Image/channels/1/supplementLight": f"""<SupplementLight version="2.0" {STD}>
            <supplementLightMode>close</supplementLightMode>
            <mixedLightBrightnessRegulatMode>auto</mixedLightBrightnessRegulatMode>
            <whiteLightBrightness>100</whiteLightBrightness><irLightBrightness>100</irLightBrightness></SupplementLight>""",
        "/ISAPI/Image/channels/1/supplementLight/capabilities": f"""<SupplementLight version="2.0" {STD}>
            <supplementLightMode opt="colorVuWhiteLight,close">close</supplementLightMode>
            <mixedLightBrightnessRegulatMode opt="auto,manual">manual</mixedLightBrightnessRegulatMode>
            <whiteLightBrightness min="0" max="100">100</whiteLightBrightness></SupplementLight>""",
        "/ISAPI/Image/channels/1/IrcutFilter": f"""<IrcutFilter {NS}><IrcutFilterType>auto</IrcutFilterType>
            <nightToDayFilterLevel>4</nightToDayFilterLevel><nightToDayFilterTime>5</nightToDayFilterTime></IrcutFilter>""",
        "/ISAPI/Image/channels/1/IrcutFilter/capabilities": f"""<IrcutFilter {NS}>
            <IrcutFilterType opt="auto,day,night,schedule">auto</IrcutFilterType>
            <nightToDayFilterLevel min="0" max="7">4</nightToDayFilterLevel>
            <nightToDayFilterTime min="5" max="120">5</nightToDayFilterTime></IrcutFilter>""",
        "/ISAPI/System/Video/inputs/channels/1/motionDetection": f"""<MotionDetection {NS}><enabled>true</enabled>
            <enableHighlight>false</enableHighlight></MotionDetection>""",
        "/ISAPI/System/Video/inputs/channels/1/motionDetection/capabilities": f"""<MotionDetection {NS}>
            <enabled opt="true,false"/><targetType opt="human,vehicle"/></MotionDetection>""",
        "/ISAPI/Smart/FieldDetection/1": f"""<FieldDetection {NS}><id>1</id><enabled>false</enabled></FieldDetection>""",
        "/ISAPI/Smart/LineDetection/1": f"""<LineDetection {NS}><id>1</id><enabled>true</enabled></LineDetection>""",
        "/ISAPI/Event/triggers/notifications/channels/1/whiteLightAlarm": f"""<WhiteLightAlarm {NS}>
            <durationTime>15</durationTime><frequency>high</frequency></WhiteLightAlarm>""",
        "/ISAPI/Event/triggers/notifications/channels/1/whiteLightAlarm/capabilities": f"""<WhiteLightAlarm {NS}>
            <durationTime min="1" max="60">15</durationTime><frequency opt="high,medium,low,normallyOn">high</frequency></WhiteLightAlarm>""",
        "/ISAPI/System/IO/outputs": f"""<IOOutputPortList {NS}><IOOutputPort><id>1</id></IOOutputPort></IOOutputPortList>""",
        "/ISAPI/System/IO/outputs/1/status": f"""<IOPortStatus {NS}><ioPortID>1</ioPortID><ioState>inactive</ioState></IOPortStatus>""",
        "/ISAPI/PTZCtrl/channels/1/capabilities": f"""<PTZChanelCap {NS}><ContinuousPanTiltSpace/>
            <PTZAuxList><PTZAux><type>WIPER</type></PTZAux></PTZAuxList></PTZChanelCap>""",
        "/ISAPI/System/status": f"""<DeviceStatus {NS}><deviceUpTime>3600</deviceUpTime>
            <CPUList><CPU><cpuUtilization>12</cpuUtilization></CPU></CPUList>
            <MemoryList><Memory><memoryUsage>100</memoryUsage><memoryAvailable>300</memoryAvailable></Memory></MemoryList></DeviceStatus>""",
        "/ISAPI/ContentMgmt/Storage": f"""<storage {NS}><hddList><hdd><id>1</id><status>ok</status>
            <capacity>60000</capacity><freeSpace>20000</freeSpace></hdd></hddList></storage>""",
        "/ISAPI/Event/triggers": f"""<EventTriggerList {NS}>
            <EventTrigger><id>VMD-1</id><eventType>VMD</eventType><EventTriggerNotificationList>
              <EventTriggerNotification><id>center</id><notificationMethod>center</notificationMethod></EventTriggerNotification>
            </EventTriggerNotificationList></EventTrigger>
            <EventTrigger><id>linedetection-1</id><eventType>linedetection</eventType><EventTriggerNotificationList>
              <EventTriggerNotification><id>record</id><notificationMethod>record</notificationMethod></EventTriggerNotification>
            </EventTriggerNotificationList></EventTrigger></EventTriggerList>""",
        "/ISAPI/Event/triggers/linedetection-1": f"""<EventTrigger {NS}><id>linedetection-1</id><eventType>linedetection</eventType>
            <EventTriggerNotificationList><EventTriggerNotification><id>record</id><notificationMethod>record</notificationMethod>
            </EventTriggerNotification></EventTriggerNotificationList></EventTrigger>""",
    }


AUDIO = {"AudioAlarm": {"audioID": 1, "audioVolume": 80, "alarmTimes": 3, "audioClass": "alertAudio"}}
AUDIO_CAPS = {
    "AudioAlarmCap": {
        "audioTypeListCap": [
            {"audioID": 1, "audioDescription": "Siren"},
            {"audioID": 2, "audioDescription": "Warning, this is a protected area"},
        ],
        "audioVolume": {"min": 1, "max": 100},
        "alarmTimes": {"min": 1, "max": 50},
    }
}


class FakeCamera:
    def __init__(self, password: str = "secret") -> None:
        self.password = password
        self.docs = default_docs()
        self.audio = json.loads(json.dumps(AUDIO))
        self.puts: list[tuple[str, str]] = []
        self.read_only = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path + (f"?{request.url.query.decode()}" if request.url.query else "")
        auth = request.headers.get("authorization", "")
        if not auth:
            return httpx.Response(
                401,
                headers={"WWW-Authenticate": 'Digest qop="auth", realm="IP Camera(TEST)", nonce="abc", stale="FALSE"'},
            )
        if 'username="wrong"' in auth:
            return httpx.Response(401, headers={"WWW-Authenticate": 'Digest qop="auth", realm="x", nonce="n", stale="FALSE"'})

        if request.method == "PUT":
            body = request.content.decode()
            self.puts.append((path, body))
            if self.read_only:
                return httpx.Response(403, text="Forbidden")
            if "<?xml version='1.0'" in body:
                return httpx.Response(400, text=BAD)
            # Like the real NC500: fields absent from capabilities are rejected.
            if path == "/ISAPI/Image/channels/1/supplementLight" and (
                "irLightBrightness" in body
                or ("<mixedLightBrightnessRegulatMode>manual" in body and "whiteLightBrightness" not in body)
            ):
                return httpx.Response(400, text=BAD)
            if path.startswith("/ISAPI/Event/triggers/notifications/AudioAlarm?"):
                self.audio = json.loads(body)
                return httpx.Response(200, json={"statusCode": 1, "statusString": "OK"})
            if "AudioAlarm" in path and path.endswith("test?format=json"):
                return httpx.Response(200, json={"statusCode": 1, "statusString": "OK"})
            if request.url.path in self.docs and body.strip():
                self.docs[request.url.path] = re.sub(r"<\?xml[^>]*\?>", "", body)
            return httpx.Response(200, text=OK)

        if path == "/ISAPI/Event/triggers/notifications/AudioAlarm?format=json":
            return httpx.Response(200, json=self.audio)
        if path == "/ISAPI/Event/triggers/notifications/AudioAlarm/capabilities?format=json":
            return httpx.Response(200, json=AUDIO_CAPS)
        if path == "/ISAPI/Event/notification/alertStream":
            return httpx.Response(200, content=b"")
        if path.endswith("/picture"):
            return httpx.Response(200, content=b"\xff\xd8jpeg", headers={"Content-Type": "image/jpeg"})
        if path in self.docs:
            return httpx.Response(200, text=self.docs[path], headers={"Content-Type": "application/xml"})
        return httpx.Response(404, text="Not Found")

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
