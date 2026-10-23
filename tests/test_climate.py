"""The climate control."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from hyundai_kia_connect_api.KiaUvoApiEU import KiaUvoApiEU
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moolink.const import CONF_TOKEN, DOMAIN

from .conftest import ENTRY_DATA, NO_QUIET_HOURS, VIN, make_token

CLIMATE = "climate.ioniq_5_climate"


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def eu_entry(mock_vm: MagicMock) -> MockConfigEntry:
    mock_vm.api.__class__ = KiaUvoApiEU
    mock_vm.api.temperature_range = KiaUvoApiEU.temperature_range
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="1_2_driver",
        data={**ENTRY_DATA, "region": 1, CONF_TOKEN: make_token().to_dict()},
        options=NO_QUIET_HOURS,
    )


async def test_europe_range_and_unit(
    hass: HomeAssistant, mock_vm: MagicMock, eu_entry
) -> None:
    await _setup(hass, eu_entry)
    state = hass.states.get(CLIMATE)
    assert state.state == "off"
    assert state.attributes["min_temp"] == 14.0
    assert state.attributes["max_temp"] == 31.5
    assert state.attributes["target_temp_step"] == 0.5
    assert state.attributes["temperature"] == 21.0
    assert state.attributes["hvac_modes"] == ["off", "heat_cool"]


async def test_usa_uses_fahrenheit_range(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    state = hass.states.get(CLIMATE)
    assert state.attributes["temperature"] is not None
    entity = hass.data["entity_components"]["climate"].get_entity(CLIMATE)
    assert entity.temperature_unit == "°F"
    assert (entity.min_temp, entity.max_temp) == (62.0, 81.0)


async def test_mode_starts_and_stops(
    hass: HomeAssistant, mock_vm: MagicMock, eu_entry
) -> None:
    await _setup(hass, eu_entry)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": CLIMATE, "hvac_mode": "heat_cool"},
        blocking=True,
    )
    vehicle_id, options = mock_vm.start_climate.call_args.args
    assert vehicle_id == VIN and options.set_temp == 21.0

    eu_entry.runtime_data._pending.clear()  # pretend the car has acted
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": CLIMATE, "hvac_mode": "off"},
        blocking=True,
    )
    mock_vm.stop_climate.assert_called_once_with(VIN)


async def test_set_temperature_is_remembered_not_sent_when_off(
    hass: HomeAssistant, mock_vm: MagicMock, eu_entry
) -> None:
    await _setup(hass, eu_entry)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": CLIMATE, "temperature": 19.5},
        blocking=True,
    )
    assert eu_entry.options["climate_temperature"] == 19.5
    assert hass.states.get(CLIMATE).attributes["temperature"] == 19.5
    mock_vm.start_climate.assert_not_called()


async def test_set_temperature_applies_when_running(
    hass: HomeAssistant, mock_vm: MagicMock, eu_entry
) -> None:
    mock_vm.vehicles[VIN].air_control_is_on = True
    await _setup(hass, eu_entry)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": CLIMATE, "temperature": 23},
        blocking=True,
    )
    _, options = mock_vm.start_climate.call_args.args
    assert options.set_temp == 23


async def test_set_temperature_with_mode_starts_once(
    hass: HomeAssistant, mock_vm: MagicMock, eu_entry
) -> None:
    await _setup(hass, eu_entry)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": CLIMATE, "temperature": 22, "hvac_mode": "heat_cool"},
        blocking=True,
    )
    mock_vm.start_climate.assert_called_once()
    assert mock_vm.start_climate.call_args.args[1].set_temp == 22


async def test_unsupported_temperature_rejected(
    hass: HomeAssistant, mock_vm: MagicMock, eu_entry
) -> None:
    await _setup(hass, eu_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": CLIMATE, "temperature": 21.3},
            blocking=True,
        )
    assert "climate_temperature" not in eu_entry.options
