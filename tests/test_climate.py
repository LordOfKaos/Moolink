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


@pytest.fixture
def capped_entry(eu_entry: MockConfigEntry) -> MockConfigEntry:
    """A car whose climate tops out at 25 °C (e.g. a Kona)."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=eu_entry.unique_id,
        data=dict(eu_entry.data),
        options={**NO_QUIET_HOURS, "climate_max_temperature": 25},
    )


async def test_car_maximum_caps_climate_control(
    hass: HomeAssistant, mock_vm: MagicMock, capped_entry
) -> None:
    await _setup(hass, capped_entry)
    state = hass.states.get(CLIMATE)
    assert state.attributes["max_temp"] == 25.0
    assert state.attributes["min_temp"] == 14.0


async def test_car_maximum_rejects_higher_target(
    hass: HomeAssistant, mock_vm: MagicMock, capped_entry
) -> None:
    await _setup(hass, capped_entry)
    # Home Assistant's climate control enforces max_temp itself.
    with pytest.raises(ServiceValidationError, match="14.0 to 25"):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": CLIMATE, "temperature": 26},
            blocking=True,
        )
    device_id = next(iter(hass.data["device_registry"].devices))
    with pytest.raises(ServiceValidationError, match="maximum of 25"):
        await hass.services.async_call(
            DOMAIN,
            "start_climate",
            {"device_id": device_id, "temperature": 27},
            blocking=True,
        )
    mock_vm.start_climate.assert_not_called()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": CLIMATE, "temperature": 25},
        blocking=True,
    )
    assert capped_entry.options["climate_temperature"] == 25


async def test_options_reject_target_above_new_maximum(
    hass: HomeAssistant, mock_vm: MagicMock, eu_entry
) -> None:
    await _setup(hass, eu_entry)
    result = await hass.config_entries.options.async_init(eu_entry.entry_id)
    user_input = {
        "scan_interval": 30,
        "force_refresh_interval": 240,
        "quiet_start": "22:00:00",
        "quiet_end": "07:00:00",
        "climate_temperature": 27,
        "climate_max_temperature": 25,
        "climate_duration": 10,
        "climate_defrost": False,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert result["errors"] == {"climate_temperature": "above_max"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**user_input, "climate_temperature": 21}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert eu_entry.runtime_data.climate_max == 25
    assert hass.states.get(CLIMATE).attributes["max_temp"] == 25.0
