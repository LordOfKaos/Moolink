"""Telling the user how commands ended."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from hyundai_kia_connect_api.const import ORDER_STATUS
from pytest_homeassistant_custom_component.common import async_capture_events

from .conftest import VIN

NOTIFICATION = f"moolink_{VIN}_command"


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _lock(hass: HomeAssistant) -> None:
    with patch("custom_components.moolink.coordinator.COMMAND_REFRESH_DELAY", 0):
        await hass.services.async_call(
            "lock", "lock", {"entity_id": "lock.ioniq_5_doors"}, blocking=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)


def _notices(hass: HomeAssistant) -> dict:
    return persistent_notification._async_get_or_create_notifications(hass)


@pytest.mark.parametrize(
    ("status", "text"),
    [
        (ORDER_STATUS.FAILED, "refused"),
        (ORDER_STATUS.TIMEOUT, "didn't respond"),
    ],
)
async def test_failure_creates_notification_and_event(
    hass: HomeAssistant,
    mock_vm: MagicMock,
    config_entry,
    status: ORDER_STATUS,
    text: str,
) -> None:
    await _setup(hass, config_entry)
    events = async_capture_events(hass, "moolink_command")
    mock_vm.check_action_status.return_value = status
    await _lock(hass)

    notice = _notices(hass)[NOTIFICATION]
    assert notice["title"] == "Moolink command failed"
    assert "Ioniq 5" in notice["message"] and text in notice["message"]
    assert events[0].data == {
        "vehicle_id": VIN,
        "vehicle": "Ioniq 5",
        "command": "lock",
        "status": status.value.lower(),
    }


async def test_success_clears_earlier_failure(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    events = async_capture_events(hass, "moolink_command")
    mock_vm.check_action_status.return_value = ORDER_STATUS.FAILED
    await _lock(hass)
    assert NOTIFICATION in _notices(hass)

    mock_vm.check_action_status.return_value = ORDER_STATUS.SUCCESS
    await _lock(hass)
    assert NOTIFICATION not in _notices(hass)
    assert events[-1].data["status"] == "success"


async def test_unknown_outcome_is_not_reported_as_failure(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    """Regions without a status check give no result; don't cry wolf."""
    await _setup(hass, config_entry)
    events = async_capture_events(hass, "moolink_command")
    mock_vm.check_action_status.return_value = None
    await _lock(hass)
    assert NOTIFICATION not in _notices(hass)
    assert events == []


async def test_status_checked_sparingly_until_final(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    """Pending answers are re-checked, but only a few times."""
    await _setup(hass, config_entry)
    mock_vm.check_action_status.side_effect = [
        ORDER_STATUS.PENDING,
        ORDER_STATUS.PENDING,
        ORDER_STATUS.SUCCESS,
    ]
    events = async_capture_events(hass, "moolink_command")
    await _lock(hass)
    assert mock_vm.check_action_status.call_count == 3
    # Quick, non-blocking checks rather than the library's 5 s loop.
    assert mock_vm.check_action_status.call_args.args[2] is False
    assert events[-1].data["status"] == "success"


async def test_still_pending_after_last_check_is_not_a_failure(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    mock_vm.check_action_status.return_value = ORDER_STATUS.PENDING
    await _lock(hass)
    assert mock_vm.check_action_status.call_count == 4
    assert NOTIFICATION not in _notices(hass)
