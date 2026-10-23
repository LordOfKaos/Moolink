"""Diagnostics must be useful and must not leak personal data."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import ENTRY_DATA, VIN


async def _diagnostics(hass, hass_client, mock_vm, entry) -> dict:
    vehicle = mock_vm.vehicles[VIN]
    # A realistic raw response with identifying values nested in it.
    vehicle.data = {
        "Vehicle": {
            "Location": {"GeoCoord": {"Latitude": 51.9, "Longitude": -1.1}},
            "Green": {"BatteryManagement": {"BatteryRemain": {"Ratio": 50}}},
            "Body": {"Door": {"Row1": {"Driver": {"Open": 0}}}},
            "Note": f"vin {VIN} in free text",
        },
        "vinInfo": {"vin": VIN},
    }
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return await get_diagnostics_for_config_entry(hass, hass_client, entry)


async def test_no_personal_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_vm: MagicMock,
    config_entry,
) -> None:
    result = await _diagnostics(hass, hass_client, mock_vm, config_entry)
    dumped = json.dumps(result)
    for secret in (
        VIN,
        ENTRY_DATA["username"],
        ENTRY_DATA["password"],
        '"access"',  # token values, as JSON strings
        '"refresh"',
        "51.9",
        "-1.1",
        "-75.0",  # vehicle location in the fixture
    ):
        assert secret not in dumped, secret


async def test_keeps_useful_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_vm: MagicMock,
    config_entry,
) -> None:
    result = await _diagnostics(hass, hass_client, mock_vm, config_entry)
    vehicle = result["vehicles"][0]
    assert vehicle["raw"]["Vehicle"]["Green"]["BatteryManagement"] == {
        "BatteryRemain": {"Ratio": 50}
    }
    assert vehicle["attributes"]["ev_battery_percentage"] == 80
    assert vehicle["attributes"]["model"] == "IONIQ 5"
    assert result["entry"]["data"]["region"] == 3
    assert result["library_version"]
