"""Turns the camera's alert stream into binary sensor states."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import EVENT_ANNKE, EVENTS, EventSpec
from .isapi import Event, IsapiClient, run_alert_stream

_LOGGER = logging.getLogger(__name__)

# Sent every few seconds as a heartbeat; not a real alarm.
_HEARTBEAT = "videoloss"


class EventHub:
    """Keeps per-sensor on/off state fed by the alert stream."""

    def __init__(
        self, hass: HomeAssistant, client: IsapiClient, serial: str, off_delay: float
    ) -> None:
        self.hass = hass
        self.client = client
        self.serial = serial
        self.off_delay = off_delay
        self.connected = False
        self._state: dict[tuple[str, int], bool] = {}
        self._timers: dict[tuple[str, int], CALLBACK_TYPE] = {}
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = self.hass.async_create_background_task(
            run_alert_stream(self.client, self._on_event, self._on_connected),
            f"annke alert stream {self.client.host}",
        )

    async def stop(self) -> None:
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def is_on(self, key: str, channel: int) -> bool:
        return self._state.get((key, channel), False)

    @callback
    def add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    @callback
    def _on_connected(self, connected: bool) -> None:
        if connected != self.connected:
            self.connected = connected
            self._notify()

    @staticmethod
    def matches(spec: EventSpec, event: Event) -> bool:
        if spec.target:
            return event.target is not None and spec.target in event.target
        return event.event_type in spec.event_types

    @callback
    def _on_event(self, event: Event) -> None:
        if event.event_type == _HEARTBEAT and not event.active:
            return
        # Cameras repeat "active" several times a second while it lasts; fire
        # the HA event once per occurrence, keyed like the sensors' state.
        raw = (f"raw:{event.event_type}:{event.target}", event.channel)
        started = event.active and not self._state.get(raw, False)
        self._set(raw, event.active)
        if started:
            self.hass.bus.async_fire(
                EVENT_ANNKE,
                {
                    "serial": self.serial,
                    "host": self.client.host,
                    "channel": event.channel,
                    "event_type": event.event_type,
                    "target": event.target,
                    "region": event.region,
                    "description": event.description,
                    **event.extra,
                },
            )
        keys = [spec.key for spec in EVENTS if self.matches(spec, event)]
        if event.event_type == "io" and "inputIOPortID" in event.extra:
            keys.append(f"io_{event.extra['inputIOPortID']}")
        changed = False
        for key in keys:
            changed |= self._set((key, event.channel), event.active)
        if changed:
            self._notify()

    @callback
    def _set(self, slot: tuple[str, int], active: bool) -> bool:
        if cancel := self._timers.pop(slot, None):
            cancel()
        if active:
            # Devices repeat "active" while the event lasts; turn off after silence.
            @callback
            def _expire(_now) -> None:
                self._expire(slot)

            self._timers[slot] = async_call_later(self.hass, self.off_delay, _expire)
        old = self._state.get(slot, False)
        self._state[slot] = active
        return old != active

    @callback
    def _expire(self, slot: tuple[str, int]) -> None:
        self._timers.pop(slot, None)
        if self._state.get(slot):
            self._state[slot] = False
            self._notify()
