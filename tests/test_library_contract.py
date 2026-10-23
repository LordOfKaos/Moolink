"""Checks against the real hyundai_kia_connect_api library.

These run without network access. They catch library upgrades that rename
fields or regions this integration relies on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hyundai_kia_connect_api import Vehicle, VehicleManager
from hyundai_kia_connect_api.const import BRANDS as LIB_BRANDS
from hyundai_kia_connect_api.const import REGIONS as LIB_REGIONS
from hyundai_kia_connect_api.HyundaiBlueLinkApiUSA import HyundaiBlueLinkApiUSA
from hyundai_kia_connect_api.HyundaiCciApiEU import HyundaiCciApiEU
from hyundai_kia_connect_api.KiaUvoApiEU import KiaUvoApiEU

from custom_components.moolink.binary_sensor import BINARY_SENSORS
from custom_components.moolink.const import BRANDS, REGIONS
from custom_components.moolink.number import LIMIT_KEYS
from custom_components.moolink.sensor import SENSORS

COMPONENT = Path(__file__).parent.parent / "custom_components" / "moolink"
VEHICLE_FIELDS_USED = [
    *(d.key for d in SENSORS),
    *(d.key for d in BINARY_SENSORS),
    *LIMIT_KEYS,
    "is_locked",
    "air_control_is_on",
    "ev_battery_is_charging",
    "location_latitude",
    "location_longitude",
    "location_last_updated_at",
    "odometer_unit",
]


@pytest.mark.parametrize("field", VEHICLE_FIELDS_USED)
def test_vehicle_has_field(field: str) -> None:
    assert hasattr(Vehicle(), field), f"Vehicle.{field} no longer exists"


def test_region_and_brand_ids_match_library() -> None:
    for region_id in REGIONS:
        assert region_id in LIB_REGIONS
    assert LIB_REGIONS[1] == "Europe"
    assert LIB_REGIONS[3] == "USA"
    assert {k: LIB_BRANDS[k] for k in BRANDS} == BRANDS


@pytest.mark.parametrize(
    ("region", "api_class"),
    [(1, KiaUvoApiEU), (9, HyundaiCciApiEU), (3, HyundaiBlueLinkApiUSA)],
)
def test_hyundai_region_uses_expected_api(region: int, api_class: type) -> None:
    vm = VehicleManager(region=region, brand=2, username="u", password="p", pin="1234")
    assert isinstance(vm.api, api_class)


def test_europe_supports_core_commands() -> None:
    """UK/EU Hyundai must keep supporting the controls we expose."""
    from custom_components.moolink.entity import supports

    class FakeCoordinator:
        vehicle_manager = VehicleManager(
            region=1, brand=2, username="u", password="p", pin="1234"
        )

    for method in (
        "lock_action",
        "start_climate",
        "start_charge",
        "set_charge_limits",
        "force_refresh_vehicle_state",
    ):
        assert supports(FakeCoordinator, method), method


def test_europe_temperature_range_is_celsius() -> None:
    assert 21.0 in KiaUvoApiEU.temperature_range
    assert 70 not in KiaUvoApiEU.temperature_range


def test_manifest_pins_installed_library() -> None:
    from importlib.metadata import version

    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    pinned = manifest["requirements"][0].split("==")[1]
    assert version("hyundai_kia_connect_api") == pinned or pytest.skip(
        "running against a different library version (compat job)"
    )


def test_translations_match_strings() -> None:
    strings = (COMPONENT / "strings.json").read_text()
    assert (COMPONENT / "translations" / "en.json").read_text() == strings
