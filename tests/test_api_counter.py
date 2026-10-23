"""API request counting and Bluelink's daily limit."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
import requests
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from hyundai_kia_connect_api.exceptions import RateLimitingError
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.moolink.api_counter import ApiRequestCounter

SENSOR = "sensor.bluelink_driver_example_com_api_requests_today"


def _fire(session: requests.Session, times: int = 1) -> None:
    """Simulate the library receiving responses on its session."""
    for _ in range(times):
        for hook in session.hooks["response"]:
            hook(requests.Response())


@pytest.fixture
def session(mock_vm: MagicMock) -> requests.Session:
    session = requests.Session()
    mock_vm.api.session = session
    return session


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def test_counter_resets_at_midnight(freezer: FrozenDateTimeFactory) -> None:
    # One minute before midnight in Home Assistant's own time zone.
    freezer.move_to(
        datetime(2026, 10, 23, 23, 59, tzinfo=dt_util.get_default_time_zone())
    )
    counter = ApiRequestCounter(region=1)
    session = requests.Session()
    counter.attach(session)
    _fire(session, 3)
    assert counter.count == 3
    freezer.tick(timedelta(minutes=2))
    assert counter.count == 0
    _fire(session)
    assert counter.count == 1


def test_europe_has_known_limit() -> None:
    assert ApiRequestCounter(region=1).daily_limit == 200
    assert ApiRequestCounter(region=9).daily_limit == 200
    assert ApiRequestCounter(region=3).daily_limit is None


async def test_sensor_counts_requests(
    hass: HomeAssistant, mock_vm: MagicMock, session, config_entry
) -> None:
    await _setup(hass, config_entry)
    _fire(session, 5)
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR)
    assert state.state == "5"
    assert state.attributes["date"] == dt_util.now().date().isoformat()
    assert state.attributes["limit_reached"] is False


async def test_count_survives_restart(
    hass: HomeAssistant, mock_vm: MagicMock, session, config_entry
) -> None:
    today = dt_util.now().date().isoformat()
    mock_restore_cache(hass, [State(SENSOR, "40", {"date": today})])
    await _setup(hass, config_entry)
    assert hass.states.get(SENSOR).state == "40"


async def test_yesterdays_count_is_not_restored(
    hass: HomeAssistant, mock_vm: MagicMock, session, config_entry
) -> None:
    yesterday = (dt_util.now().date() - timedelta(days=1)).isoformat()
    mock_restore_cache(hass, [State(SENSOR, "180", {"date": yesterday})])
    await _setup(hass, config_entry)
    assert hass.states.get(SENSOR).state == "0"


async def test_limit_pauses_polling_and_keeps_data(
    hass: HomeAssistant, mock_vm: MagicMock, session, config_entry
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    mock_vm.check_and_force_update_vehicles.side_effect = RateLimitingError("5091")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    # Last known state stays visible instead of going unavailable.
    assert hass.states.get("lock.ioniq_5_doors").state == "locked"
    assert hass.states.get(SENSOR).attributes["limit_reached"] is True

    calls = mock_vm.check_and_force_update_vehicles.call_count
    await coordinator.async_refresh()
    assert mock_vm.check_and_force_update_vehicles.call_count == calls


async def test_limit_on_command_explained(
    hass: HomeAssistant, mock_vm: MagicMock, session, config_entry
) -> None:
    await _setup(hass, config_entry)
    mock_vm.lock.side_effect = RateLimitingError("5091")
    with pytest.raises(HomeAssistantError, match="daily request limit"):
        await hass.services.async_call(
            "lock", "lock", {"entity_id": "lock.ioniq_5_doors"}, blocking=True
        )
