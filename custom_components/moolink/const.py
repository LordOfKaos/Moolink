"""Constants for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "moolink"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_REGION = "region"
CONF_BRAND = "brand"
CONF_PIN = "pin"
CONF_TOKEN = "token"
CONF_OTP_METHOD = "otp_method"
CONF_OTP_CODE = "otp_code"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_FORCE_REFRESH_INTERVAL = "force_refresh_interval"
CONF_CLIMATE_TEMPERATURE = "climate_temperature"
CONF_CLIMATE_DURATION = "climate_duration"
CONF_CLIMATE_DEFROST = "climate_defrost"

# Region / brand ids as defined by hyundai_kia_connect_api.const
REGIONS: dict[int, str] = {
    1: "Europe",
    9: "Europe (CCI/GSPA, newer accounts)",
    2: "Canada",
    3: "USA",
    4: "China",
    5: "Australia",
    6: "India",
    8: "Brazil",
}
BRANDS: dict[int, str] = {2: "Hyundai", 3: "Genesis", 1: "Kia"}
BRAND_HYUNDAI = 2

DEFAULT_SCAN_INTERVAL = 30  # minutes, cached data from the cloud
# Minutes between forced refreshes, which wake the car and cost 12V battery.
# 0 disables forced refreshes entirely.
DEFAULT_FORCE_REFRESH_INTERVAL = 240
REGION_USA = 3
DEFAULT_CLIMATE_DURATION = 10
DEFAULT_CLIMATE_DEFROST = False



def default_climate_temperature(region: int) -> float:
    """Default cabin temperature in the unit the region's API expects."""
    return 70.0 if region == REGION_USA else 21.0


# Delay before re-reading state after a remote command was sent.
COMMAND_REFRESH_DELAY = 30  # seconds
ACTION_STATUS_TIMEOUT = 60  # seconds

SERVICE_START_CLIMATE = "start_climate"
SERVICE_FORCE_REFRESH = "force_refresh"
SERVICE_SET_CHARGE_LIMITS = "set_charge_limits"
ATTR_VEHICLE_ID = "vehicle_id"
