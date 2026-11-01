"""Minimal async client for the Hikvision ISAPI used by Annke cameras."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
import logging
import re
from typing import Any
import xml.etree.ElementTree as ET

import httpx

_LOGGER = logging.getLogger(__name__)

NS = "http://www.hikvision.com/ver20/XMLSchema"
NS_STD = "http://www.std-cgi.com/ver20/XMLSchema"
_NS_RE = re.compile(r"\{[^}]*\}")


class IsapiError(Exception):
    """Generic ISAPI failure."""


class IsapiAuthError(IsapiError):
    """Wrong username or password."""


class IsapiNotSupported(IsapiError):
    """Endpoint not available on this device."""


class IsapiForbidden(IsapiNotSupported):
    """The account may not use this endpoint (HTTP 403)."""


def strip_ns(root: ET.Element) -> ET.Element:
    """Remove XML namespaces in place so lookups can use plain tag names."""
    for el in root.iter():
        el.tag = _NS_RE.sub("", el.tag)
    return root


def parse(text: str | bytes) -> ET.Element:
    """Parse an ISAPI XML document without namespaces."""
    return strip_ns(ET.fromstring(text))


def text_of(root: ET.Element | None, path: str, default: str | None = None) -> str | None:
    """Return the stripped text of a child element."""
    if root is None:
        return default
    el = root.find(path)
    if el is None or el.text is None:
        return default
    return el.text.strip()


def options_of(root: ET.Element | None, path: str) -> list[str]:
    """Return the values listed in an element's ``opt`` attribute."""
    if root is None:
        return []
    el = root.find(path)
    if el is None:
        return []
    opt = el.get("opt")
    return [o.strip() for o in opt.split(",") if o.strip()] if opt else []


def range_of(root: ET.Element | None, path: str) -> tuple[int, int] | None:
    """Return the min/max attributes of an element, if present."""
    if root is None:
        return None
    el = root.find(path)
    if el is None or el.get("min") is None or el.get("max") is None:
        return None
    return int(el.get("min")), int(el.get("max"))


def set_text(root: ET.Element, path: str, value: Any) -> bool:
    """Set the text of an existing element; return False if it is missing."""
    el = root.find(path)
    if el is None:
        return False
    el.text = str(value).lower() if isinstance(value, bool) else str(value)
    return True


def to_xml(root: ET.Element, namespace: str) -> bytes:
    """Serialise a namespace-stripped tree back with the device namespace."""
    root.set("xmlns", namespace)
    # Some firmwares reject ElementTree's single-quoted XML declaration.
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8", xml_declaration=False)


def declared_only(root: ET.Element, caps: ET.Element) -> ET.Element:
    """Copy of ``root`` keeping only top-level fields listed in ``caps``."""
    out = ET.Element(root.tag, {k: v for k, v in root.attrib.items() if k != "xmlns"})
    for child in root:
        if caps.find(child.tag) is not None:
            out.append(child)
    return out


def minimal_doc(root: ET.Element, changes: dict[str, Any]) -> ET.Element:
    """A document with the same root but only the changed fields."""
    out = ET.Element(root.tag, {k: v for k, v in root.attrib.items() if k != "xmlns"})
    for path, value in changes.items():
        parent = out
        parts = path.split("/")
        for part in parts[:-1]:
            child = parent.find(part)
            parent = child if child is not None else ET.SubElement(parent, part)
        el = ET.SubElement(parent, parts[-1])
        el.text = str(value).lower() if isinstance(value, bool) else str(value)
    return out


@dataclass
class DeviceInfo:
    """Static device information."""

    name: str
    model: str
    serial: str
    mac: str | None
    firmware: str | None
    device_type: str | None


@dataclass
class Event:
    """One parsed EventNotificationAlert."""

    event_type: str
    state: str
    channel: int
    target: str | None = None
    region: str | None = None
    description: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        return self.state == "active"


class IsapiClient:
    """Talks to one camera over ISAPI with HTTP digest authentication."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 80,
        ssl: bool = False,
    ) -> None:
        scheme = "https" if ssl else "http"
        default = 443 if ssl else 80
        self.host = host
        self.base = f"{scheme}://{host}" + ("" if port == default else f":{port}")
        self._client = client
        self._auth = httpx.DigestAuth(username, password)
        # Namespace per endpoint, so PUTs are sent back the way the device wrote them.
        self._ns: dict[str, str] = {}

    async def _request(
        self, method: str, path: str, content: bytes | None = None, timeout: float = 10
    ) -> httpx.Response:
        try:
            resp = await self._client.request(
                method,
                self.base + path,
                content=content,
                auth=self._auth,
                timeout=timeout,
                headers={"Content-Type": "application/xml"} if content else None,
            )
        except httpx.HTTPError as err:
            raise IsapiError(f"{method} {path}: {err!r}") from err
        if resp.status_code == 401:
            raise IsapiAuthError(f"{method} {path}: unauthorized")
        if resp.status_code == 403:
            raise IsapiForbidden(f"{method} {path}: HTTP 403")
        if resp.status_code in (404, 405, 501):
            raise IsapiNotSupported(f"{method} {path}: HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise IsapiError(f"{method} {path}: HTTP {resp.status_code} {resp.text[:200]}")
        return resp

    async def get_xml(self, path: str) -> ET.Element:
        resp = await self._request("GET", path)
        raw = ET.fromstring(resp.content)
        match = re.match(r"\{([^}]*)\}", raw.tag)
        self._ns[path] = match.group(1) if match else NS_STD
        return strip_ns(raw)

    async def try_get_xml(self, path: str) -> ET.Element | None:
        """GET an XML document, returning None when the device lacks it."""
        try:
            return await self.get_xml(path)
        except IsapiNotSupported:
            return None
        except IsapiError as err:
            if isinstance(err, IsapiAuthError):
                raise
            _LOGGER.debug("%s: %s", self.host, err)
            return None

    async def put_xml(self, path: str, root: ET.Element) -> None:
        body = to_xml(root, self._ns.get(path, NS_STD))
        resp = await self._request("PUT", path, content=body)
        status = parse(resp.content) if resp.content else None
        code = text_of(status, "statusCode")
        if code not in (None, "1", "7"):  # 7 = OK, reboot required
            raise IsapiError(
                f"PUT {path}: {text_of(status, 'statusString')} "
                f"({text_of(status, 'subStatusCode')})"
            )

    async def update_xml(self, path: str, changes: dict[str, Any]) -> ET.Element:
        """Read a document, change some fields and write it back."""
        root = await self.get_xml(path)
        minimal = minimal_doc(root, changes)
        for key, value in changes.items():
            if not set_text(root, key, value):
                raise IsapiNotSupported(f"{path} has no element {key}")
        try:
            await self.put_xml(path, root)
            return root
        except (IsapiAuthError, IsapiForbidden):
            raise
        except IsapiError as err:
            errors = [f"full: {err}"]
        # Firmwares often reject fields they echo back but do not declare as
        # writable (e.g. irLightBrightness on ColorVu-only models). Retry with
        # only the declared fields, then with only the changed ones.
        attempts = []
        caps = await self.try_get_xml(path + "/capabilities")
        if caps is not None:
            attempts.append(("declared", declared_only(root, caps)))
        attempts.append(("minimal", minimal))
        for name, doc in attempts:
            try:
                await self.put_xml(path, doc)
                _LOGGER.debug("%s: PUT %s needed the %s document", self.host, path, name)
                return root
            except (IsapiAuthError, IsapiForbidden):
                raise
            except IsapiError as err:
                errors.append(f"{name}: {err}")
        raise IsapiError("; ".join(errors))

    async def get_json(self, path: str) -> dict[str, Any]:
        resp = await self._request("GET", path)
        try:
            return resp.json()
        except ValueError as err:
            raise IsapiNotSupported(f"GET {path}: not JSON") from err

    async def try_get_json(self, path: str) -> dict[str, Any] | None:
        try:
            return await self.get_json(path)
        except IsapiAuthError:
            raise
        except IsapiError as err:
            _LOGGER.debug("%s: %s", self.host, err)
            return None

    async def put_json(self, path: str, data: dict[str, Any] | None = None) -> None:
        resp = await self._client.request(
            "PUT",
            self.base + path,
            json=data or {},
            auth=self._auth,
            timeout=10,
        )
        if resp.status_code == 401:
            raise IsapiAuthError(f"PUT {path}: unauthorized")
        if resp.status_code == 403:
            raise IsapiForbidden(f"PUT {path}: HTTP 403")
        if resp.status_code >= 400:
            raise IsapiError(f"PUT {path}: HTTP {resp.status_code} {resp.text[:200]}")
        try:
            body = resp.json()
        except ValueError:
            return
        if str(body.get("statusCode", 1)) not in ("1", "7"):
            raise IsapiError(f"PUT {path}: {body.get('statusString')} ({body.get('subStatusCode')})")

    async def put_raw(self, path: str, body: bytes) -> None:
        """PUT a prepared XML body and check the ResponseStatus."""
        resp = await self._request("PUT", path, content=body)
        status = parse(resp.content) if resp.content else None
        code = text_of(status, "statusCode")
        if code not in (None, "1", "7"):
            raise IsapiError(f"PUT {path}: {text_of(status, 'statusString')}")

    async def get_bytes(self, path: str, timeout: float = 10) -> bytes:
        return (await self._request("GET", path, timeout=timeout)).content

    async def device_info(self) -> DeviceInfo:
        root = await self.get_xml("/ISAPI/System/deviceInfo")
        return DeviceInfo(
            name=text_of(root, "deviceName") or self.host,
            model=text_of(root, "model") or "Unknown",
            serial=text_of(root, "serialNumber") or self.host,
            mac=text_of(root, "macAddress"),
            firmware=" ".join(
                p for p in (text_of(root, "firmwareVersion"), text_of(root, "firmwareReleasedDate")) if p
            )
            or None,
            device_type=text_of(root, "deviceType"),
        )

    async def reboot(self) -> None:
        await self._request("PUT", "/ISAPI/System/reboot")

    async def alert_stream(self) -> AsyncIterator[Event]:
        """Yield events from the long-lived multipart alert stream."""
        url = self.base + "/ISAPI/Event/notification/alertStream"
        timeout = httpx.Timeout(10, read=90)
        async with self._client.stream("GET", url, auth=self._auth, timeout=timeout) as resp:
            if resp.status_code == 401:
                raise IsapiAuthError("alertStream: unauthorized")
            if resp.status_code >= 400:
                raise IsapiError(f"alertStream: HTTP {resp.status_code}")
            buffer = b""
            async for chunk in resp.aiter_bytes():
                docs, buffer = split_alerts(buffer + chunk)
                for doc in docs:
                    event = parse_event(doc)
                    if event is not None:
                        yield event


_ALERT_RE = re.compile(rb"<EventNotificationAlert\b.*?</EventNotificationAlert>", re.S)
_MAX_BUFFER = 1_000_000


def split_alerts(buffer: bytes) -> tuple[list[bytes], bytes]:
    """Return complete alert documents in the buffer and the unparsed rest."""
    docs = [m.group(0) for m in _ALERT_RE.finditer(buffer)]
    end = buffer.rfind(b"</EventNotificationAlert>")
    rest = buffer[end + len(b"</EventNotificationAlert>"):] if end >= 0 else buffer
    start = rest.find(b"<EventNotificationAlert")
    # Drop multipart headers and attached pictures; keep only a pending document.
    rest = rest[start:] if start >= 0 else rest[-32:]
    if len(rest) > _MAX_BUFFER:
        rest = b""
    return docs, rest


def parse_event(doc: bytes) -> Event | None:
    """Turn one EventNotificationAlert document into an Event."""
    try:
        root = parse(doc)
    except ET.ParseError:
        _LOGGER.debug("Unparsable event: %r", doc[:200])
        return None
    event_type = (text_of(root, "eventType") or "").lower()
    if not event_type:
        return None
    channel = text_of(root, "channelID") or text_of(root, "dynChannelID") or "1"
    target = text_of(root, ".//targetType") or text_of(root, ".//detectionTarget")
    region = text_of(root, ".//regionID")
    extra = {}
    for tag in ("inputIOPortID", "outputIOPortID", "activePostCount"):
        val = text_of(root, f".//{tag}")
        if val is not None:
            extra[tag] = val
    return Event(
        event_type=event_type,
        state=(text_of(root, "eventState") or "active").lower(),
        channel=int(channel) if channel.isdigit() else 1,
        target=target.lower() if target else None,
        region=region,
        description=text_of(root, "eventDescription"),
        extra=extra,
    )


async def run_alert_stream(
    client: IsapiClient,
    on_event: Callable[[Event], None],
    on_connected: Callable[[bool], None],
) -> None:
    """Keep the alert stream connected forever, backing off on errors."""
    delay = 5
    while True:
        try:
            on_connected(True)
            async for event in client.alert_stream():
                delay = 5
                on_event(event)
            _LOGGER.debug("%s: alert stream closed by device", client.host)
        except asyncio.CancelledError:
            raise
        except IsapiError as err:
            _LOGGER.debug("%s: alert stream error: %s", client.host, err)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("%s: unexpected alert stream error", client.host)
        on_connected(False)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 300)
