"""Behaviour specific to European (including UK) accounts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from hyundai_kia_connect_api.KiaUvoApiEU import KiaUvoApiEU
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moolink.const import CONF_TOKEN, DOMAIN

from .conftest import ENTRY_DATA, NO_QUIET_HOURS, make_token

EU_INPUT = {**ENTRY_DATA, "region": "1", "brand": "2"}


@pytest.fixture
def eu_vm(mock_vm: MagicMock) -> MagicMock:
    """The mock VehicleManager, backed by the EU API class."""
    mock_vm.api.__class__ = KiaUvoApiEU
    mock_vm.api.temperature_range = KiaUvoApiEU.temperature_range
    return mock_vm


@pytest.fixture
def eu_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"1_2_{ENTRY_DATA['username']}",
        data={**ENTRY_DATA, "region": 1, CONF_TOKEN: make_token().to_dict()},
        options=NO_QUIET_HOURS,
    )


async def test_uk_home_assistant_suggests_europe(hass: HomeAssistant) -> None:
    hass.config.country = "GB"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    schema = result["data_schema"].schema
    region_key = next(k for k in schema if str(k) == "region")
    assert region_key.description["suggested_value"] == "1"


async def test_europe_requires_pin(hass: HomeAssistant, eu_vm: MagicMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**EU_INPUT, "pin": "  "}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"pin": "pin_required"}
    eu_vm.login.assert_not_called()

    with patch("custom_components.moolink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], EU_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["region"] == 1


async def test_usa_does_not_require_pin(
    hass: HomeAssistant, mock_vm: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch("custom_components.moolink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**ENTRY_DATA, "region": "3", "brand": "2", "pin": ""}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_europe_climate_defaults_to_celsius(
    hass: HomeAssistant, eu_vm: MagicMock, eu_entry
) -> None:
    eu_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(eu_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": "climate.ioniq_5_climate"}, blocking=True
    )
    _, options = eu_vm.start_climate.call_args.args
    assert options.set_temp == 21.0


@pytest.mark.parametrize("temperature", [70, 21.3, 13.5, 32])
async def test_europe_rejects_unsupported_temperature(
    hass: HomeAssistant, eu_vm: MagicMock, eu_entry, temperature: float
) -> None:
    eu_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(eu_entry.entry_id)
    await hass.async_block_till_done()
    device_id = next(iter(hass.data["device_registry"].devices))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "start_climate",
            {"device_id": device_id, "temperature": temperature},
            blocking=True,
        )
    eu_vm.start_climate.assert_not_called()


async def test_europe_options_reject_fahrenheit(
    hass: HomeAssistant, eu_vm: MagicMock, eu_entry
) -> None:
    eu_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(eu_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(eu_entry.entry_id)
    user_input = {
        "scan_interval": 30,
        "force_refresh_interval": 240,
        "climate_temperature": 70,
        "climate_duration": 10,
        "climate_defrost": False,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert result["errors"] == {"climate_temperature": "invalid_temperature"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**user_input, "climate_temperature": 19.5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
