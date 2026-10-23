"""The Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType
from hyundai_kia_connect_api import ClimateRequestOptions

from .const import (
    CONF_CLIMATE_DEFROST,
    CONF_CLIMATE_DURATION,
    CONF_CLIMATE_TEMPERATURE,
    CONF_REGION,
    DEFAULT_CLIMATE_DEFROST,
    DEFAULT_CLIMATE_DURATION,
    DOMAIN,
    PLATFORMS,
    SERVICE_FORCE_REFRESH,
    SERVICE_SET_CHARGE_LIMITS,
    SERVICE_START_CLIMATE,
    default_climate_temperature,
)
from .coordinator import MoolinkConfigEntry, MoolinkCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_DURATION = "duration"
ATTR_DEFROST = "defrost"
ATTR_CLIMATE = "climate"
ATTR_HEATING = "heating"
ATTR_FRONT_LEFT_SEAT = "front_left_seat"
ATTR_FRONT_RIGHT_SEAT = "front_right_seat"
ATTR_REAR_LEFT_SEAT = "rear_left_seat"
ATTR_REAR_RIGHT_SEAT = "rear_right_seat"
ATTR_STEERING_WHEEL = "steering_wheel"
ATTR_AC_LIMIT = "ac_limit"
ATTR_DC_LIMIT = "dc_limit"

# Seat levels as understood by the API: 0 off, 1-3 cool low..high,
# 4-6 heat low..high (region dependent; see README).
SEAT_LEVEL = vol.All(vol.Coerce(int), vol.Range(min=0, max=8))
CHARGE_LIMIT = vol.All(vol.Coerce(int), vol.Range(min=50, max=100))

START_CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_TEMPERATURE): vol.Coerce(float),
        vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(1, 30)),
        vol.Optional(ATTR_DEFROST): cv.boolean,
        vol.Optional(ATTR_CLIMATE): cv.boolean,
        vol.Optional(ATTR_HEATING): vol.All(vol.Coerce(int), vol.Range(0, 4)),
        vol.Optional(ATTR_FRONT_LEFT_SEAT): SEAT_LEVEL,
        vol.Optional(ATTR_FRONT_RIGHT_SEAT): SEAT_LEVEL,
        vol.Optional(ATTR_REAR_LEFT_SEAT): SEAT_LEVEL,
        vol.Optional(ATTR_REAR_RIGHT_SEAT): SEAT_LEVEL,
        vol.Optional(ATTR_STEERING_WHEEL): vol.All(vol.Coerce(int), vol.Range(0, 3)),
    }
)
FORCE_REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICE_ID): cv.string})
SET_CHARGE_LIMITS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_AC_LIMIT): CHARGE_LIMIT,
        vol.Required(ATTR_DC_LIMIT): CHARGE_LIMIT,
    }
)


def climate_options(
    entry: MoolinkConfigEntry, overrides: dict | None = None
) -> ClimateRequestOptions:
    """Build climate options from the entry's defaults plus any overrides."""
    overrides = overrides or {}
    opts = entry.options
    set_temp = overrides.get(
        ATTR_TEMPERATURE,
        opts.get(
            CONF_CLIMATE_TEMPERATURE,
            default_climate_temperature(entry.data[CONF_REGION]),
        ),
    )
    entry.runtime_data.validate_temperature(set_temp)
    return ClimateRequestOptions(
        set_temp=set_temp,
        duration=overrides.get(
            ATTR_DURATION, opts.get(CONF_CLIMATE_DURATION, DEFAULT_CLIMATE_DURATION)
        ),
        defrost=overrides.get(
            ATTR_DEFROST, opts.get(CONF_CLIMATE_DEFROST, DEFAULT_CLIMATE_DEFROST)
        ),
        climate=overrides.get(ATTR_CLIMATE, True),
        heating=overrides.get(ATTR_HEATING),
        front_left_seat=overrides.get(ATTR_FRONT_LEFT_SEAT),
        front_right_seat=overrides.get(ATTR_FRONT_RIGHT_SEAT),
        rear_left_seat=overrides.get(ATTR_REAR_LEFT_SEAT),
        rear_right_seat=overrides.get(ATTR_REAR_RIGHT_SEAT),
        steering_wheel=overrides.get(ATTR_STEERING_WHEEL),
    )


def _resolve_device(
    hass: HomeAssistant, device_id: str
) -> tuple[MoolinkConfigEntry, str]:
    """Map a device id to its config entry and Bluelink vehicle id."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for domain, vehicle_id in device.identifiers:
            if domain != DOMAIN:
                continue
            for entry_id in device.config_entries:
                entry = hass.config_entries.async_get_entry(entry_id)
                if (
                    entry is not None
                    and entry.domain == DOMAIN
                    and entry.state is ConfigEntryState.LOADED
                ):
                    return entry, vehicle_id
    raise ServiceValidationError(f"Device {device_id} is not a loaded Moolink vehicle")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide services."""

    async def start_climate(call: ServiceCall) -> None:
        entry, vehicle_id = _resolve_device(hass, call.data[ATTR_DEVICE_ID])
        await entry.runtime_data.async_send_command(
            vehicle_id, "start_climate", climate_options(entry, dict(call.data))
        )

    async def force_refresh(call: ServiceCall) -> None:
        if ATTR_DEVICE_ID in call.data:
            entry, vehicle_id = _resolve_device(hass, call.data[ATTR_DEVICE_ID])
            await entry.runtime_data.async_force_refresh(vehicle_id)
            return
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            await entry.runtime_data.async_force_refresh()

    async def set_charge_limits(call: ServiceCall) -> None:
        entry, vehicle_id = _resolve_device(hass, call.data[ATTR_DEVICE_ID])
        await entry.runtime_data.async_send_command(
            vehicle_id,
            "set_charge_limits",
            call.data[ATTR_AC_LIMIT],
            call.data[ATTR_DC_LIMIT],
        )

    hass.services.async_register(
        DOMAIN, SERVICE_START_CLIMATE, start_climate, schema=START_CLIMATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FORCE_REFRESH, force_refresh, schema=FORCE_REFRESH_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHARGE_LIMITS,
        set_charge_limits,
        schema=SET_CHARGE_LIMITS_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MoolinkConfigEntry) -> bool:
    """Set up a Bluelink account from a config entry."""
    coordinator = MoolinkCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MoolinkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
