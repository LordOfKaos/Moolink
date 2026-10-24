"""Repair issues: rejected PIN, low 12V battery, daily limit."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from hyundai_kia_connect_api.exceptions import APIError, RateLimitingError

from custom_components.moolink.const import DOMAIN
from custom_components.moolink.repairs import async_create_fix_flow

from .conftest import VIN


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _lock(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "lock", "lock", {"entity_id": "lock.ioniq_5_doors"}, blocking=True
    )


async def test_rejected_pin_raises_fixable_issue(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    config_entry,
    issue_registry: ir.IssueRegistry,
) -> None:
    await _setup(hass, config_entry)
    mock_vm.lock.side_effect = APIError("PIN verification failed")
    with pytest.raises(HomeAssistantError, match="Repairs"):
        await _lock(hass)
    issue = issue_registry.async_get_issue(
        DOMAIN, f"pin_rejected_{config_entry.entry_id}"
    )
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.ERROR

    # The fix flow saves the new PIN and reloads the integration.
    flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    flow.hass = hass
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await flow.async_step_init()
        assert result["type"] == "form"
        result = await flow.async_step_init({"pin": " 9876 "})
    assert result["type"] == "create_entry"
    assert config_entry.data["pin"] == "9876"
    reload.assert_called_once_with(config_entry.entry_id)


async def test_accepted_command_clears_pin_issue(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    config_entry,
    issue_registry: ir.IssueRegistry,
) -> None:
    await _setup(hass, config_entry)
    mock_vm.lock.side_effect = APIError("PIN verification failed")
    with pytest.raises(HomeAssistantError):
        await _lock(hass)
    mock_vm.lock.side_effect = None
    await _lock(hass)
    assert (
        issue_registry.async_get_issue(DOMAIN, f"pin_rejected_{config_entry.entry_id}")
        is None
    )


async def test_low_12v_issue_comes_and_goes(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    config_entry,
    issue_registry: ir.IssueRegistry,
) -> None:
    vehicle = mock_vm.vehicles[VIN]
    vehicle.car_battery_percentage = 41
    await _setup(hass, config_entry)
    issue = issue_registry.async_get_issue(DOMAIN, f"low_12v_battery_{VIN}")
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "vehicle": "Ioniq 5",
        "level": "41",
        "threshold": "50",
    }

    vehicle.car_battery_percentage = 77
    await config_entry.runtime_data.async_refresh()
    assert issue_registry.async_get_issue(DOMAIN, f"low_12v_battery_{VIN}") is None


async def test_daily_limit_issue_clears_next_day(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    config_entry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-10-24T12:00:00+00:00")
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    issue_id = f"daily_limit_reached_{config_entry.entry_id}"

    mock_vm.update_vehicle_with_cached_state.side_effect = RateLimitingError("5091")
    await coordinator.async_refresh()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    mock_vm.update_vehicle_with_cached_state.side_effect = None
    freezer.tick(timedelta(days=1))
    await coordinator.async_refresh()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_limit_hit_by_a_command_raises_issue(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    config_entry,
    issue_registry: ir.IssueRegistry,
) -> None:
    await _setup(hass, config_entry)
    mock_vm.lock.side_effect = RateLimitingError("5091")
    with pytest.raises(HomeAssistantError):
        await _lock(hass)
    assert issue_registry.async_get_issue(
        DOMAIN, f"daily_limit_reached_{config_entry.entry_id}"
    )
