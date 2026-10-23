"""Sensors for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MoolinkConfigEntry, MoolinkCoordinator
from .entity import MoolinkEntity, account_device_info, reports, vehicle_unit


@dataclass(frozen=True, kw_only=True)
class MoolinkSensorDescription(SensorEntityDescription):
    """Sensor description; `key` is the Vehicle attribute to read.

    When `native_unit_of_measurement` is None and `unit_from_vehicle` is set,
    the unit reported by the library (km/mi, °C/°F, psi/kPa/bar) is used.
    """

    unit_from_vehicle: bool = False


def _distance(key: str, **kwargs) -> MoolinkSensorDescription:
    return MoolinkSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        unit_from_vehicle=True,
        **kwargs,
    )


def _tire(key: str) -> MoolinkSensorDescription:
    return MoolinkSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_from_vehicle=True,
    )


SENSORS: tuple[MoolinkSensorDescription, ...] = (
    MoolinkSensorDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        unit_from_vehicle=True,
    ),
    _distance("total_driving_range"),
    _distance("fuel_driving_range"),
    _distance("ev_driving_range"),
    _distance("next_service_distance"),
    MoolinkSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MoolinkSensorDescription(
        key="ev_battery_percentage",
        translation_key="ev_battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MoolinkSensorDescription(
        key="ev_battery_soh_percentage",
        translation_key="ev_battery_soh_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoolinkSensorDescription(
        key="car_battery_percentage",
        translation_key="car_battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoolinkSensorDescription(
        key="ev_charging_power",
        translation_key="ev_charging_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MoolinkSensorDescription(
        key="ev_estimated_current_charge_duration",
        translation_key="ev_estimated_current_charge_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    MoolinkSensorDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_from_vehicle=True,
    ),
    MoolinkSensorDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        unit_from_vehicle=True,
    ),
    _tire("tire_pressure_front_left"),
    _tire("tire_pressure_front_right"),
    _tire("tire_pressure_rear_left"),
    _tire("tire_pressure_rear_right"),
    MoolinkSensorDescription(
        key="dtc_count",
        translation_key="dtc_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoolinkSensorDescription(
        key="last_updated_at",
        translation_key="last_updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors for every value the vehicle actually reports."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        MoolinkSensor(coordinator, vehicle_id, description)
        for vehicle_id, vehicle in coordinator.data.items()
        for description in SENSORS
        if reports(vehicle, description.key)
    ]
    entities.append(MoolinkApiRequestsSensor(coordinator))
    async_add_entities(entities)


class MoolinkSensor(MoolinkEntity, SensorEntity):
    """A vehicle sensor."""

    entity_description: MoolinkSensorDescription

    def __init__(
        self,
        coordinator: MoolinkCoordinator,
        vehicle_id: str,
        description: MoolinkSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | datetime | None:
        """Return the value from the vehicle."""
        value = getattr(self.vehicle, self.entity_description.key, None)
        if isinstance(value, datetime) and value.tzinfo is None:
            return None  # HA requires timezone-aware timestamps
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the fixed unit or the unit reported by the car."""
        if self.entity_description.unit_from_vehicle:
            return vehicle_unit(self.vehicle, self.entity_description.key)
        return self.entity_description.native_unit_of_measurement


class MoolinkApiRequestsSensor(CoordinatorEntity[MoolinkCoordinator], RestoreSensor):
    """Requests made to the Bluelink cloud today, for the whole account."""

    _attr_has_entity_name = True
    _attr_translation_key = "api_requests_today"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: MoolinkCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_api_requests"
        self._attr_device_info = account_device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        """Carry today's count over a restart."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None:
            return
        try:
            day = date.fromisoformat(last.attributes.get("date", ""))
            count = int(last.state)
        except ValueError:
            return
        self.coordinator.api_counter.restore(day, count)

    @property
    def available(self) -> bool:
        """The count stays meaningful while Bluelink is unreachable."""
        return True

    @property
    def native_value(self) -> int:
        """Return today's request count."""
        return self.coordinator.api_counter.count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the day, the known limit and whether it was hit."""
        counter = self.coordinator.api_counter
        return {
            "date": counter.day.isoformat(),
            "daily_limit": counter.daily_limit,
            "limit_reached": self.coordinator.rate_limited,
        }
