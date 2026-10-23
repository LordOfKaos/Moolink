"""Setup, entity and command tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from hyundai_kia_connect_api.const import ENGINE_TYPES
from hyundai_kia_connect_api.exceptions import AuthenticationError

from custom_components.moolink.const import DOMAIN

from .conftest import VIN


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_creates_entities(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("lock.ioniq_5_doors").state == "locked"
    assert hass.states.get("sensor.ioniq_5_ev_battery").state == "80"
    odo = hass.states.get("sensor.ioniq_5_odometer")
    assert odo.attributes["unit_of_measurement"] in ("mi", "km")
    assert hass.states.get("binary_sensor.ioniq_5_plugged_in").state == "on"
    tracker = hass.states.get("device_tracker.ioniq_5_location")
    assert tracker.attributes["latitude"] == 40.0
    assert hass.states.get("switch.ioniq_5_climate").state == "off"
    assert hass.states.get("switch.ioniq_5_charging").state == "off"
    assert hass.states.get("number.ioniq_5_ac_charge_limit").state == "90"
    assert hass.states.get("button.ioniq_5_flash_hazard_lights") is not None
    # Values the car doesn't report produce no entity.
    assert hass.states.get("sensor.ioniq_5_fuel_level") is None


async def test_lock_command_and_follow_up(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    with patch("custom_components.moolink.coordinator.COMMAND_REFRESH_DELAY", 0):
        await hass.services.async_call(
            "lock", "unlock", {"entity_id": "lock.ioniq_5_doors"}, blocking=True
        )
        mock_vm.vehicles[VIN].is_locked = False
        await hass.async_block_till_done()
    mock_vm.unlock.assert_called_once_with(VIN)
    mock_vm.update_vehicle_with_cached_state.assert_called_with(VIN)
    assert hass.states.get("lock.ioniq_5_doors").state == "unlocked"


async def test_charge_limit_keeps_other_limit(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.ioniq_5_dc_charge_limit", "value": 70},
        blocking=True,
    )
    mock_vm.set_charge_limits.assert_called_once_with(VIN, 90, 70)


async def test_start_climate_service(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, VIN)})
    await hass.services.async_call(
        DOMAIN,
        "start_climate",
        {"device_id": device.id, "temperature": 72, "defrost": True},
        blocking=True,
    )
    vehicle_id, options = mock_vm.start_climate.call_args.args
    assert vehicle_id == VIN
    assert options.set_temp == 72
    assert options.defrost is True
    assert options.duration == 10


async def test_climate_switch_uses_defaults(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.ioniq_5_climate"}, blocking=True
    )
    _, options = mock_vm.start_climate.call_args.args
    assert options.set_temp == 70.0  # US default, °F


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    mock_vm.check_and_refresh_token.side_effect = AuthenticationError("expired")
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_token_persisted(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    mock_vm.token.access_token = "rotated"
    await _setup(hass, config_entry)
    assert config_entry.data["token"]["access_token"] == "rotated"


async def test_unload(hass: HomeAssistant, mock_vm: MagicMock, config_entry) -> None:
    await _setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_failure_marks_unavailable(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    mock_vm.check_and_force_update_vehicles.side_effect = RuntimeError("boom")
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("lock.ioniq_5_doors").state == "unavailable"


async def test_unsupported_command_raises(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    mock_vm.lock.side_effect = NotImplementedError
    with pytest.raises(HomeAssistantError, match="not supported"):
        await hass.services.async_call(
            "lock", "lock", {"entity_id": "lock.ioniq_5_doors"}, blocking=True
        )


async def test_force_refresh_service(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    mock_vm.force_refresh_all_vehicles_states.assert_called_once()

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, VIN)})
    await hass.services.async_call(
        DOMAIN, "force_refresh", {"device_id": device.id}, blocking=True
    )
    mock_vm.force_refresh_vehicle_state.assert_called_once_with(VIN)


async def test_service_rejects_unknown_device(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "start_climate", {"device_id": "nope"}, blocking=True
        )


async def test_ev_has_no_fuel_entities(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    vehicle = mock_vm.vehicles[VIN]
    vehicle.engine_type = ENGINE_TYPES.EV
    vehicle.fuel_level = 0
    vehicle.fuel_level_is_low = False
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.ioniq_5_fuel_level") is None
    assert hass.states.get("binary_sensor.ioniq_5_low_fuel") is None
    assert hass.states.get("sensor.ioniq_5_ev_battery") is not None


async def test_petrol_car_keeps_fuel_entities(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    vehicle = mock_vm.vehicles[VIN]
    vehicle.engine_type = ENGINE_TYPES.ICE
    vehicle.fuel_level = 40
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.ioniq_5_fuel_level").state == "40"


async def test_distances_display_as_whole_numbers(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    entry = er.async_get(hass).async_get("sensor.ioniq_5_ev_range")
    assert entry.options["sensor"]["suggested_display_precision"] == 0


async def test_wrong_pin_explains_how_to_fix(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    mock_vm.start_hazard_lights.side_effect = Exception(
        "PIN verification failed, ensure PIN is entered correctly."
    )
    with pytest.raises(HomeAssistantError, match="Reconfigure"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.ioniq_5_flash_hazard_lights"},
            blocking=True,
        )
