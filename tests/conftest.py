"""Fixtures for Moolink tests."""

from __future__ import annotations

import datetime as dt
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from hyundai_kia_connect_api import Token, Vehicle
from hyundai_kia_connect_api.HyundaiBlueLinkApiUSA import HyundaiBlueLinkApiUSA
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moolink.const import (
    CONF_BRAND,
    CONF_PIN,
    CONF_REGION,
    CONF_TOKEN,
    DOMAIN,
)

VIN = "KM8TESTVIN0000001"
# Tests poll the cache only, at any time of day, unless they say otherwise.
NO_QUIET_HOURS = {
    "quiet_start": "00:00:00",
    "quiet_end": "00:00:00",
    "force_refresh_interval": 0,
    "charging_refresh_interval": 0,
}
ENTRY_DATA = {
    CONF_USERNAME: "driver@example.com",
    CONF_PASSWORD: "hunter2",
    CONF_PIN: "1234",
    CONF_REGION: 3,
    CONF_BRAND: 2,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom_components in every test."""
    return


@pytest.fixture(autouse=True)
def fast_status_checks() -> Generator[None]:
    """Don't wait 15 s between command status checks in tests."""
    with patch("custom_components.moolink.coordinator.ACTION_STATUS_INTERVAL", 0):
        yield


def make_token() -> Token:
    return Token(
        username=ENTRY_DATA[CONF_USERNAME],
        password=ENTRY_DATA[CONF_PASSWORD],
        access_token="access",
        refresh_token="refresh",
        valid_until=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
        pin="1234",
    )


def make_vehicle() -> Vehicle:
    vehicle = Vehicle(id=VIN, name="Ioniq 5", model="IONIQ 5", VIN=VIN)
    vehicle.is_locked = True
    vehicle.engine_is_running = False
    vehicle.trunk_is_open = False
    vehicle.air_control_is_on = False
    vehicle.ev_battery_percentage = 80
    vehicle.ev_battery_is_charging = False
    vehicle.ev_battery_is_plugged_in = True
    vehicle.ev_charge_limits_ac = 90
    vehicle.ev_charge_limits_dc = 80
    vehicle.car_battery_percentage = 77
    vehicle.odometer = (12345.6, "mi")
    vehicle.ev_driving_range = (210, "mi")
    vehicle.location = (40.0, -75.0, dt.datetime(2026, 10, 1, tzinfo=dt.UTC))
    vehicle.last_updated_at = dt.datetime(2026, 10, 1, 12, tzinfo=dt.UTC)
    return vehicle


@pytest.fixture
def mock_vm() -> Generator[MagicMock]:
    """Patch VehicleManager with a mock backed by the real US API class."""
    vm = MagicMock()
    vm.api = MagicMock(spec=HyundaiBlueLinkApiUSA)
    # `supports()` inspects the class, so use the real implementation type.
    vm.api.__class__ = HyundaiBlueLinkApiUSA
    vm.api.temperature_range = range(62, 82)
    vm.token = make_token()
    vm.vehicles = {VIN: make_vehicle()}
    vm.login.return_value = True
    vm.check_and_refresh_token.return_value = False
    vm.lock.return_value = "tx-1"
    vm.check_action_status.return_value = None
    with patch("custom_components.moolink.coordinator.VehicleManager", return_value=vm):
        yield vm


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"3_2_{ENTRY_DATA[CONF_USERNAME]}",
        data={**ENTRY_DATA, CONF_TOKEN: make_token().to_dict()},
        # Quiet hours off, so tests don't depend on the time of day they run.
        options=NO_QUIET_HOURS,
        title="Hyundai driver@example.com",
    )
