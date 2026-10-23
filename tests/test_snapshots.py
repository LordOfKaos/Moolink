"""Snapshot tests: every entity's registry entry and state.

Any change to what the integration exposes shows up as a snapshot diff.
After an intended change, update with: pytest --snapshot-update
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.moolink.const import CONF_TOKEN, DOMAIN

from .conftest import ENTRY_DATA, NO_QUIET_HOURS, make_token


@pytest.mark.parametrize(
    "platform",
    [
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
        Platform.CLIMATE,
        Platform.DEVICE_TRACKER,
        Platform.LOCK,
        Platform.NUMBER,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
)
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_vm: MagicMock,
    freezer: FrozenDateTimeFactory,
    platform: Platform,
) -> None:
    freezer.move_to("2026-10-23T12:00:00+00:00")
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01SNAPSHOTENTRY",
        unique_id="3_2_driver@example.com",
        data={**ENTRY_DATA, CONF_TOKEN: make_token().to_dict()},
        options=NO_QUIET_HOURS,
        title="Hyundai driver@example.com",
    )
    entry.add_to_hass(hass)
    with patch("custom_components.moolink.PLATFORMS", [platform]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
