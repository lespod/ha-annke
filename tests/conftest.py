"""Fixtures for Annke tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SSL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .fake_camera import FakeCamera

DATA = {
    CONF_HOST: "192.168.0.30",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
    CONF_PORT: 80,
    CONF_SSL: False,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def camera() -> FakeCamera:
    return FakeCamera()


@pytest.fixture
def patch_client(camera: FakeCamera):
    client = camera.client()
    with (
        patch("custom_components.annke.get_async_client", return_value=client),
        patch("custom_components.annke.config_flow.get_async_client", return_value=client),
    ):
        yield client


@pytest.fixture
async def setup_entry(hass: HomeAssistant, patch_client) -> MockConfigEntry:
    entry = MockConfigEntry(domain="annke", data=DATA, unique_id="NC500-TEST-001", title="Brama")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
