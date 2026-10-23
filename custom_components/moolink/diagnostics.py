"""Diagnostics for the Moolink (Hyundai Bluelink) integration.

Personal data is removed twice over: known fields are redacted by name,
and the account's VINs and vehicle ids are scrubbed wherever they appear,
because raw Bluelink responses nest them under keys that vary by region.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import MoolinkConfigEntry

# Field names that can identify the owner, the car or its whereabouts.
TO_REDACT = {
    # account
    "username",
    "password",
    "pin",
    "token",
    "email",
    "phone",
    "mobile",
    "userId",
    "user_id",
    "deviceId",
    "device_id",
    # car identity
    "VIN",
    "vin",
    "id",
    "vehicleId",
    "vehicle_id",
    "carId",
    "masterId",
    "regId",
    "key",
    "name",
    "nickname",
    "nickName",
    "vehicleName",
    "plateNumber",
    "licensePlate",
    "registration_date",
    "regDate",
    # location
    "lat",
    "lon",
    "lng",
    "latitude",
    "longitude",
    "Latitude",
    "Longitude",
    "coord",
    "_location_latitude",
    "_location_longitude",
    "_geocode_address",
    "_geocode_name",
    "address",
    "Location",
    "location",
    "vehicleLocation",
    "GeoCoord",
}


def _jsonable(value: Any) -> Any:
    """Make library objects (datetimes, enums, ...) JSON serialisable."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timezone):
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def _scrub(value: Any, secrets: set[str]) -> Any:
    """Replace any string containing one of `secrets` with REDACTED."""
    if isinstance(value, dict):
        return {k: _scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, secrets) for v in value]
    if isinstance(value, str) and any(s in value for s in secrets):
        return REDACTED
    return value


def _library_version() -> str | None:
    try:
        return version("hyundai_kia_connect_api")
    except PackageNotFoundError:
        return None


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MoolinkConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    coordinator = entry.runtime_data
    vehicles = coordinator.vehicle_manager.vehicles
    secrets = {
        str(s)
        for v in vehicles.values()
        for s in (v.id, v.VIN)
        if s and len(str(s)) >= 4
    }
    secrets.add(entry.data.get("username", "") or "\0")

    vehicle_dumps = []
    for vehicle in vehicles.values():
        attributes = {
            k: v for k, v in vars(vehicle).items() if k not in ("data", "timezone")
        }
        vehicle_dumps.append(
            {
                "attributes": _jsonable(attributes),
                # The raw cloud response, used to replay real data in tests.
                "raw": _jsonable(vehicle.data),
            }
        )

    diagnostics = {
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "library_version": _library_version(),
        "api_class": type(coordinator.vehicle_manager.api).__name__,
        "requests_today": coordinator.api_counter.count,
        "polling_paused": coordinator.polling_paused_reason,
        "vehicles": vehicle_dumps,
    }
    return _scrub(async_redact_data(diagnostics, TO_REDACT), secrets)
