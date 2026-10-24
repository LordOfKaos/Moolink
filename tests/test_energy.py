"""Energy sensors from the car's driving history (Europe)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from hyundai_kia_connect_api.Vehicle import DailyDrivingStats

from .conftest import VIN


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _give_energy_data(vehicle, today: datetime) -> None:
    vehicle.total_power_consumed = 4_321_000  # Wh
    vehicle.total_power_regenerated = 987_000
    vehicle.power_consumption_30d = 158  # Wh per km
    vehicle.daily_stats = [
        DailyDrivingStats(
            date=datetime(2026, 10, 23),
            total_consumed=9000,
        ),
        DailyDrivingStats(
            date=today.replace(tzinfo=None),
            total_consumed=5400,
            engine_consumption=4000,
            climate_consumption=900,
            onboard_electronics_consumption=300,
            battery_care_consumption=200,
            regenerated_energy=1100,
            distance=31,
            distance_unit="km",
        ),
    ]


async def test_energy_sensors(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    config_entry,
    freezer: FrozenDateTimeFactory,
) -> None:
    now = datetime(2026, 10, 24, 15, 0, tzinfo=dt_util.get_default_time_zone())
    freezer.move_to(now)
    vehicle = mock_vm.vehicles[VIN]
    vehicle.odometer = (12345.6, "km")
    _give_energy_data(vehicle, now)
    await _setup(hass, config_entry)

    today = hass.states.get("sensor.ioniq_5_energy_used_today")
    assert today.state == "5.4"
    assert today.attributes["unit_of_measurement"] == "kWh"
    assert today.attributes["climate_kwh"] == 0.9
    assert today.attributes["regenerated_kwh"] == 1.1
    assert hass.states.get("sensor.ioniq_5_energy_used_total").state == "4321.0"
    assert hass.states.get("sensor.ioniq_5_energy_regenerated_total").state == "987.0"
    consumption = hass.states.get("sensor.ioniq_5_average_consumption_30_days")
    assert consumption.state == "158"
    assert consumption.attributes["unit_of_measurement"] == "Wh/km"


async def test_no_trip_yet_today_reads_zero(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    config_entry,
    freezer: FrozenDateTimeFactory,
) -> None:
    now = datetime(2026, 10, 24, 8, 0, tzinfo=dt_util.get_default_time_zone())
    freezer.move_to(now)
    vehicle = mock_vm.vehicles[VIN]
    _give_energy_data(vehicle, now)
    # Only yesterday's record (the library keeps them sorted newest first).
    vehicle.daily_stats = [
        d for d in vehicle.daily_stats if d.date.date() != now.date()
    ]
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.ioniq_5_energy_used_today").state == "0.0"


async def test_mile_cars_get_miles_per_kwh(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    vehicle = mock_vm.vehicles[VIN]
    vehicle.power_consumption_30d = 250  # Wh per mile
    await _setup(hass, config_entry)
    state = hass.states.get("sensor.ioniq_5_average_consumption_30_days")
    assert state.attributes["unit_of_measurement"] == "mi/kWh"
    assert float(state.state) == 4.0


async def test_no_energy_entities_without_data(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.ioniq_5_energy_used_today") is None
    assert hass.states.get("sensor.ioniq_5_average_consumption_30_days") is None
