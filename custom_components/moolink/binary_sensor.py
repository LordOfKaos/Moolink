"""Binary sensors for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MoolinkConfigEntry, MoolinkCoordinator
from .entity import MoolinkEntity

_DOOR = BinarySensorDeviceClass.DOOR
_WINDOW = BinarySensorDeviceClass.WINDOW
_PROBLEM = BinarySensorDeviceClass.PROBLEM


def _desc(
    key: str,
    device_class: BinarySensorDeviceClass | None = None,
    diagnostic: bool = False,
) -> BinarySensorEntityDescription:
    return BinarySensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=device_class,
        entity_category=EntityCategory.DIAGNOSTIC if diagnostic else None,
    )


# `key` is the boolean Vehicle attribute to read.
BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    _desc("engine_is_running", BinarySensorDeviceClass.RUNNING),
    _desc("front_left_door_is_open", _DOOR),
    _desc("front_right_door_is_open", _DOOR),
    _desc("back_left_door_is_open", _DOOR),
    _desc("back_right_door_is_open", _DOOR),
    _desc("trunk_is_open", _DOOR),
    _desc("hood_is_open", _DOOR),
    _desc("front_left_window_is_open", _WINDOW),
    _desc("front_right_window_is_open", _WINDOW),
    _desc("back_left_window_is_open", _WINDOW),
    _desc("back_right_window_is_open", _WINDOW),
    _desc("sunroof_is_open", _WINDOW),
    _desc("ev_battery_is_charging", BinarySensorDeviceClass.BATTERY_CHARGING),
    _desc("ev_battery_is_plugged_in", BinarySensorDeviceClass.PLUG),
    _desc("ev_charge_port_door_is_open", _DOOR),
    _desc("defrost_is_on"),
    _desc("steering_wheel_heater_is_on"),
    _desc("back_window_heater_is_on"),
    _desc("side_mirror_heater_is_on"),
    _desc("fuel_level_is_low", _PROBLEM),
    _desc("tire_pressure_all_warning_is_on", _PROBLEM),
    _desc("washer_fluid_warning_is_on", _PROBLEM, diagnostic=True),
    _desc("brake_fluid_warning_is_on", _PROBLEM, diagnostic=True),
    _desc("oil_level_warning_is_on", _PROBLEM, diagnostic=True),
    _desc("smart_key_battery_warning_is_on", _PROBLEM, diagnostic=True),
    _desc("battery_auxiliary_fail_warning_is_on", _PROBLEM, diagnostic=True),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create binary sensors for every flag the vehicle actually reports."""
    coordinator = entry.runtime_data
    async_add_entities(
        MoolinkBinarySensor(coordinator, vehicle_id, description)
        for vehicle_id, vehicle in coordinator.data.items()
        for description in BINARY_SENSORS
        if getattr(vehicle, description.key, None) is not None
    )


class MoolinkBinarySensor(MoolinkEntity, BinarySensorEntity):
    """A vehicle binary sensor."""

    def __init__(
        self,
        coordinator: MoolinkCoordinator,
        vehicle_id: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, vehicle_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the flag from the vehicle."""
        value = getattr(self.vehicle, self.entity_description.key, None)
        return None if value is None else bool(value)
