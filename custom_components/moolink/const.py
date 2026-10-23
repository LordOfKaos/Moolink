"""Constants for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "moolink"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
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
# Highest temperature the car itself accepts, if lower than the region's.
CONF_CLIMATE_MAX_TEMPERATURE = "climate_max_temperature"
CONF_QUIET_START = "quiet_start"
CONF_QUIET_END = "quiet_end"

# Region / brand ids as defined by hyundai_kia_connect_api.const
REGIONS: dict[int, str] = {
    1: "Europe",
    9: "Europe (new Bluelink app backend)",
    2: "Canada",
    3: "USA",
    4: "China",
    5: "Australia",
    6: "India",
    8: "Brazil",
}
REGION_EUROPE = 1
REGION_CANADA = 2
REGION_USA = 3
REGION_EUROPE_CCI = 9
# EU accounts need the Bluelink PIN for every remote command.
PIN_REQUIRED_REGIONS = {REGION_EUROPE, REGION_EUROPE_CCI}

# Suggested region for Home Assistant's configured country.
_COUNTRY_REGIONS = {
    "US": REGION_USA,
    "CA": REGION_CANADA,
    "CN": 4,
    "AU": 5,
    "IN": 6,
    "BR": 8,
}
_EUROPEAN_COUNTRIES = {
    "AD",
    "AT",
    "BE",
    "BG",
    "CH",
    "CY",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IS",
    "IT",
    "LI",
    "LT",
    "LU",
    "LV",
    "MC",
    "MT",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SE",
    "SI",
    "SK",
    "SM",
}


def default_region(country: str | None) -> int:
    """Suggest a Bluelink region for a Home Assistant country code."""
    if country in _EUROPEAN_COUNTRIES:
        return REGION_EUROPE
    return _COUNTRY_REGIONS.get(country or "", REGION_USA)


BRANDS: dict[int, str] = {2: "Hyundai", 3: "Genesis", 1: "Kia"}
BRAND_HYUNDAI = 2

DEFAULT_SCAN_INTERVAL = 30  # minutes, cached data from the cloud
# Minutes between forced refreshes, which wake the car and cost 12V battery.
# 0 disables forced refreshes entirely.
DEFAULT_FORCE_REFRESH_INTERVAL = 240
DEFAULT_CLIMATE_DURATION = 10
DEFAULT_CLIMATE_DEFROST = False


def default_climate_temperature(region: int) -> float:
    """Default cabin temperature in the unit the region's API expects."""
    return 70.0 if region == REGION_USA else 21.0


# Overnight window with no automatic polling (no requests, car never woken).
# Setting start and end to the same time turns it off.
DEFAULT_QUIET_START = "22:00:00"
DEFAULT_QUIET_END = "07:00:00"
# Requests kept back for commands: automatic polling stops this close to a
# known daily limit.
REQUEST_RESERVE = 30

# Daily request limit commonly reported for Hyundai/Kia Europe. Hyundai
# doesn't publish it; exceeding it returns error 5091 until midnight.
EU_DAILY_REQUEST_LIMIT = 200

# Delay before re-reading state after a remote command was sent.
COMMAND_REFRESH_DELAY = 30  # seconds
# How often and how long to ask Bluelink whether the car carried out a
# command. The library's own wait asks every 5 s; this spends fewer requests.
ACTION_STATUS_INTERVAL = 15  # seconds
ACTION_STATUS_CHECKS = 4

# Fired when the car reports how a command ended.
EVENT_COMMAND = f"{DOMAIN}_command"

SERVICE_START_CLIMATE = "start_climate"
SERVICE_FORCE_REFRESH = "force_refresh"
SERVICE_SET_CHARGE_LIMITS = "set_charge_limits"
ATTR_VEHICLE_ID = "vehicle_id"
