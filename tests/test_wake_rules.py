"""When the car may be woken: charging refresh and 12V battery protection."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moolink.const import CONF_TOKEN, DOMAIN

from .conftest import ENTRY_DATA, VIN, make_token

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=dt_util.UTC)


def _entry(**options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="3_2_driver",
        data={**ENTRY_DATA, CONF_TOKEN: make_token().to_dict()},
        options={
            "quiet_start": "00:00:00",
            "quiet_end": "00:00:00",
            "scan_interval": 60,
            "force_refresh_interval": 0,
            "charging_refresh_interval": 30,
            "min_12v_battery": 50,
            **options,
        },
    )


async def _poll_once(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    *,
    charging: bool,
    data_age: timedelta,
    battery_12v: int = 80,
) -> None:
    """Set up, then run one poll with the car in the given state."""
    freezer.move_to(NOW)
    vehicle = mock_vm.vehicles[VIN]
    vehicle.ev_battery_is_charging = charging
    vehicle.car_battery_percentage = battery_12v
    vehicle.last_updated_at = NOW - data_age
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_vm.force_refresh_vehicle_state.reset_mock()
    mock_vm.update_vehicle_with_cached_state.reset_mock()
    await entry.runtime_data.async_refresh()


@pytest.mark.parametrize(
    ("charging", "age_min", "battery", "wakes"),
    [
        (True, 45, 80, True),  # charging, data 45 min old: wake
        (True, 10, 80, False),  # charging, data fresh: cache is enough
        (False, 300, 80, False),  # parked, wake-ups off: never wake
        (True, 45, 40, False),  # charging but 12V below 50%: protect it
    ],
)
async def test_charging_refresh(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    freezer: FrozenDateTimeFactory,
    charging: bool,
    age_min: int,
    battery: int,
    wakes: bool,
) -> None:
    await _poll_once(
        hass,
        mock_vm,
        freezer,
        _entry(),
        charging=charging,
        data_age=timedelta(minutes=age_min),
        battery_12v=battery,
    )
    assert mock_vm.force_refresh_vehicle_state.called is wakes
    assert mock_vm.update_vehicle_with_cached_state.called is not wakes


async def test_low_12v_blocks_scheduled_force_refresh(
    hass: HomeAssistant, mock_vm: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    await _poll_once(
        hass,
        mock_vm,
        freezer,
        _entry(force_refresh_interval=240),
        charging=False,
        data_age=timedelta(hours=6),
        battery_12v=45,
    )
    mock_vm.force_refresh_vehicle_state.assert_not_called()


async def test_scheduled_force_refresh_with_healthy_12v(
    hass: HomeAssistant, mock_vm: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    await _poll_once(
        hass,
        mock_vm,
        freezer,
        _entry(force_refresh_interval=240),
        charging=False,
        data_age=timedelta(hours=6),
    )
    mock_vm.force_refresh_vehicle_state.assert_called_once_with(VIN)


async def test_polls_faster_only_while_charging(
    hass: HomeAssistant, mock_vm: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    entry = _entry()
    await _poll_once(
        hass, mock_vm, freezer, entry, charging=True, data_age=timedelta(minutes=5)
    )
    assert entry.runtime_data.update_interval == timedelta(minutes=30)

    mock_vm.vehicles[VIN].ev_battery_is_charging = False
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.update_interval == timedelta(minutes=60)


async def test_manual_force_refresh_still_allowed_on_low_12v(
    hass: HomeAssistant, mock_vm: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Protection is for automatic wake-ups; a button press is deliberate."""
    entry = _entry()
    await _poll_once(
        hass,
        mock_vm,
        freezer,
        entry,
        charging=False,
        data_age=timedelta(hours=1),
        battery_12v=30,
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.ioniq_5_force_refresh"}, blocking=True
    )
    mock_vm.force_refresh_vehicle_state.assert_called_once_with(VIN)


async def test_timestamp_without_timezone_does_not_break_polling(
    hass: HomeAssistant, mock_vm: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    entry = _entry()
    await _poll_once(
        hass, mock_vm, freezer, entry, charging=True, data_age=timedelta(minutes=5)
    )
    naive_old = (dt_util.as_local(NOW) - timedelta(hours=2)).replace(tzinfo=None)
    mock_vm.vehicles[VIN]._last_updated_at = naive_old
    mock_vm.force_refresh_vehicle_state.reset_mock()
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.last_update_success
    mock_vm.force_refresh_vehicle_state.assert_called_once_with(VIN)
