"""Gentler polling: quiet hours and keeping requests back for commands."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
import requests
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moolink.const import CONF_TOKEN, DOMAIN

from .conftest import ENTRY_DATA, make_token

SENSOR = "sensor.bluelink_driver_example_com_api_requests_today"


def _at(freezer: FrozenDateTimeFactory, hour: int, minute: int = 0) -> None:
    freezer.move_to(
        datetime(2026, 10, 23, hour, minute, tzinfo=dt_util.get_default_time_zone())
    )


def _entry(region: int = 3, **options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{region}_2_driver",
        data={**ENTRY_DATA, "region": region, CONF_TOKEN: make_token().to_dict()},
        options=options,
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("hour", "polls"),
    [(21, True), (22, False), (2, False), (6, False), (7, True), (12, True)],
)
async def test_default_quiet_hours_overnight(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    freezer: FrozenDateTimeFactory,
    hour: int,
    polls: bool,
) -> None:
    """Default quiet hours are 22:00-07:00."""
    entry = _entry()
    _at(freezer, 12)
    await _setup(hass, entry)
    calls = mock_vm.check_and_force_update_vehicles.call_count

    _at(freezer, hour)
    await entry.runtime_data.async_refresh()
    polled = mock_vm.check_and_force_update_vehicles.call_count > calls
    assert polled is polls
    paused = hass.states.get(SENSOR).attributes["polling_paused"]
    assert (paused == "quiet hours") is not polls


async def test_first_poll_happens_even_in_quiet_hours(
    hass: HomeAssistant, mock_vm: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Entities need data at startup, whatever the time."""
    _at(freezer, 3)
    await _setup(hass, _entry())
    assert hass.states.get("lock.ioniq_5_doors").state == "locked"


async def test_custom_daytime_quiet_hours(
    hass: HomeAssistant, mock_vm: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    entry = _entry(quiet_start="09:00:00", quiet_end="17:00:00")
    _at(freezer, 8)
    await _setup(hass, entry)
    calls = mock_vm.check_and_force_update_vehicles.call_count
    _at(freezer, 12)
    await entry.runtime_data.async_refresh()
    assert mock_vm.check_and_force_update_vehicles.call_count == calls
    _at(freezer, 23)
    await entry.runtime_data.async_refresh()
    assert mock_vm.check_and_force_update_vehicles.call_count == calls + 1


async def test_reserve_kept_for_commands_in_europe(
    hass: HomeAssistant, mock_vm: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Near Europe's ~200/day limit, polling stops but commands still go out."""
    session = requests.Session()
    mock_vm.api.session = session
    entry = _entry(region=1, quiet_start="00:00:00", quiet_end="00:00:00")
    _at(freezer, 12)
    await _setup(hass, entry)
    for _ in range(170):
        session.hooks["response"][0](requests.Response())

    calls = mock_vm.check_and_force_update_vehicles.call_count
    await entry.runtime_data.async_refresh()
    assert mock_vm.check_and_force_update_vehicles.call_count == calls
    assert (
        hass.states.get(SENSOR).attributes["polling_paused"]
        == "saving remaining requests for commands"
    )

    await hass.services.async_call(
        "lock", "lock", {"entity_id": "lock.ioniq_5_doors"}, blocking=True
    )
    mock_vm.lock.assert_called_once()
