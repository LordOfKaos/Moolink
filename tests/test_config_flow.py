"""Config flow tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from hyundai_kia_connect_api.ApiImpl import OTPRequest
from hyundai_kia_connect_api.const import OTP_NOTIFY_TYPE
from hyundai_kia_connect_api.exceptions import AuthenticationError

from custom_components.moolink.const import CONF_TOKEN, DOMAIN

from .conftest import ENTRY_DATA

USER_INPUT = {
    **ENTRY_DATA,
    "region": str(ENTRY_DATA["region"]),
    "brand": str(ENTRY_DATA["brand"]),
}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_success(hass: HomeAssistant, mock_vm: MagicMock) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.moolink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["region"] == 3
    assert result["data"]["brand"] == 2
    assert result["data"][CONF_TOKEN]["access_token"] == "access"


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_vm: MagicMock) -> None:
    mock_vm.login.side_effect = AuthenticationError("bad")
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_otp(hass: HomeAssistant, mock_vm: MagicMock) -> None:
    mock_vm.otp_request = OTPRequest(
        request_id="r",
        otp_key="k",
        has_email=True,
        has_sms=False,
        email="d***@example.com",
        sms=None,
    )
    mock_vm.login.return_value = mock_vm.otp_request
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["step_id"] == "otp_method"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"otp_method": "EMAIL"}
    )
    mock_vm.send_otp.assert_called_once_with(OTP_NOTIFY_TYPE.EMAIL)
    assert result["step_id"] == "otp_code"

    mock_vm.verify_otp_and_complete_login.side_effect = AuthenticationError("no")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"otp_code": "000000"}
    )
    assert result["errors"] == {"base": "invalid_otp"}

    mock_vm.verify_otp_and_complete_login.side_effect = None
    with patch("custom_components.moolink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"otp_code": " 123456 "}
        )
    mock_vm.verify_otp_and_complete_login.assert_called_with("123456")
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_aborts(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    config_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, mock_vm: MagicMock, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    with patch("custom_components.moolink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-pass", "pin": "1234"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["password"] == "new-pass"


async def test_options_flow(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    # US entries default to Fahrenheit.
    schema = result["data_schema"].schema
    defaults = {str(k): k.default() for k in schema}
    assert defaults["climate_temperature"] == 70.0
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 15,
            "force_refresh_interval": 0,
            "climate_temperature": 68,
            "climate_duration": 10,
            "climate_defrost": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.runtime_data.force_refresh_interval == 0


async def test_reconfigure_updates_pin_keeps_password(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    with patch("custom_components.moolink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "", "pin": " 4321 "}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["pin"] == "4321"
    assert config_entry.data["password"] == "hunter2"


async def test_reconfigure_changes_password(
    hass: HomeAssistant, mock_vm: MagicMock, config_entry
) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    with patch("custom_components.moolink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-pass", "pin": "1234"}
        )
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["password"] == "new-pass"
