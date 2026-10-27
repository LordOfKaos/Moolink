"""Telling Hyundai server outages apart from a wrong password."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from hyundai_kia_connect_api.exceptions import AuthenticationError

from custom_components.moolink.const import DOMAIN
from custom_components.moolink.coordinator import is_server_side_auth_failure

from .conftest import ENTRY_DATA

# The exact error seen in a user's log during a Hyundai outage.
OUTAGE_502 = AuthenticationError(
    'CCI token exchange failed: HTTP 502 — {"code":9001,'
    '"message":"External service error","errors":[]}. '
    "This may indicate an API change."
)
REFRESH_502 = AuthenticationError(
    'CCI token refresh failed: HTTP 502 — {"code":9001,'
    '"message":"External service error","errors":[]}'
)
WAF_BLOCK = AuthenticationError(
    "IDPConnect authorize was blocked by the WAF ('abusing request'). "
    "This is a server-side block, not a credentials problem. See #1273."
)
WRONG_PASSWORD = AuthenticationError(
    "Authentication rejected: invalid_credentials. Check username and password."
)
SIGNIN_401 = AuthenticationError(
    "Signin failed: HTTP 401 — Unauthorized. Check username and password."
)


@pytest.mark.parametrize(
    ("err", "server_side"),
    [
        (OUTAGE_502, True),
        (REFRESH_502, True),
        (WAF_BLOCK, True),
        (AuthenticationError("Signin failed: HTTP 503 — busy."), True),
        (WRONG_PASSWORD, False),
        (SIGNIN_401, False),
        (RuntimeError("HTTP 502"), False),  # not an auth error at all
    ],
)
def test_classification(err: Exception, server_side: bool) -> None:
    assert is_server_side_auth_failure(err) is server_side


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _reauth_flows(hass: HomeAssistant) -> list:
    return [
        f
        for f in hass.config_entries.flow.async_progress()
        if f["context"]["source"] == "reauth"
    ]


async def test_outage_during_poll_is_retried_not_reauth(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data
    mock_vm.check_and_refresh_token.side_effect = OUTAGE_502
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _reauth_flows(hass) == []
    assert not coordinator.last_update_success

    # Hyundai recovers: the next poll just works with the stored login.
    mock_vm.check_and_refresh_token.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert hass.states.get("lock.ioniq_5_doors").state == "locked"


async def test_wrong_password_still_asks_to_sign_in(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    mock_vm.check_and_refresh_token.side_effect = WRONG_PASSWORD
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert len(_reauth_flows(hass)) == 1


async def test_outage_during_command_explained_without_reauth(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    mock_vm.lock.side_effect = OUTAGE_502
    with pytest.raises(HomeAssistantError, match="servers are having problems"):
        await hass.services.async_call(
            "lock", "lock", {"entity_id": "lock.ioniq_5_doors"}, blocking=True
        )
    await hass.async_block_till_done()
    assert _reauth_flows(hass) == []


async def test_outage_during_force_refresh_without_reauth(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    mock_vm.force_refresh_vehicle_state.side_effect = WAF_BLOCK
    with pytest.raises(HomeAssistantError, match="servers are having problems"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.ioniq_5_force_refresh"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert _reauth_flows(hass) == []


async def test_outage_during_setup_says_cannot_connect(
    hass: HomeAssistant, mock_vm: MagicMock
) -> None:
    mock_vm.login.side_effect = OUTAGE_502
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch("custom_components.moolink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**ENTRY_DATA, "region": "3", "brand": "2"},
        )
    assert result["errors"] == {"base": "cannot_connect"}
