"""Sensors for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from collections.abc import Callable
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
    UnitOfEnergy,
    UnitOfEnergyDistance,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from hyundai_kia_connect_api import Vehicle

from .coordinator import MoolinkConfigEntry, MoolinkCoordinator
from .entity import MoolinkEntity, account_device_info, reports, vehicle_unit


@dataclass(frozen=True, kw_only=True)
class MoolinkSensorDescription(SensorEntityDescription):
    """Sensor description; `key` is the Vehicle attribute to read.

    When `native_unit_of_measurement` is None and `unit_from_vehicle` is set,
    the unit reported by the library (km/mi, °C/°F, psi/kPa/bar) is used.
    """

    unit_from_vehicle: bool = False
    # For values computed from the vehicle rather than read from `key`.
    value_fn: Callable[[Vehicle], Any] | None = None
    unit_fn: Callable[[Vehicle], str | None] | None = None
    attrs_fn: Callable[[Vehicle], dict[str, Any]] | None = None


def _kwh(wh: float | None) -> float | None:
    return None if wh is None else round(wh / 1000, 2)


def _today_stats(vehicle: Vehicle) -> Any:
    """The car's daily energy record for today, if it has one."""
    today = dt_util.now().date()
    for day in vehicle.daily_stats or []:
        if day.date is not None and day.date.date() == today:
            return day
    return None


def _energy_today(vehicle: Vehicle) -> float | None:
    if not vehicle.daily_stats:
        return None
    day = _today_stats(vehicle)
    return _kwh(day.total_consumed) if day else 0.0


def _energy_today_breakdown(vehicle: Vehicle) -> dict[str, Any]:
    day = _today_stats(vehicle)
    if day is None:
        return {}
    return {
        "driving_kwh": _kwh(day.engine_consumption),
        "climate_kwh": _kwh(day.climate_consumption),
        "electronics_kwh": _kwh(day.onboard_electronics_consumption),
        "battery_care_kwh": _kwh(day.battery_care_consumption),
        "regenerated_kwh": _kwh(day.regenerated_energy),
        "distance": day.distance,
        "distance_unit": day.distance_unit,
    }


def _consumption_30d(vehicle: Vehicle) -> float | None:
    """Average consumption; Wh/km, or mi/kWh for cars reporting miles."""
    value = vehicle.power_consumption_30d
    if not value:
        return None
    if vehicle.odometer_unit == "mi":
        return round(1000 / value, 2)
    return value


def _consumption_unit(vehicle: Vehicle) -> str:
    if vehicle.odometer_unit == "mi":
        return UnitOfEnergyDistance.MILES_PER_KILO_WATT_HOUR
    return UnitOfEnergyDistance.WATT_HOUR_PER_KM


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
        key="energy_used_today",
        translation_key="energy_used_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_energy_today,
        attrs_fn=_energy_today_breakdown,
    ),
    MoolinkSensorDescription(
        key="total_power_consumed",
        translation_key="energy_consumed_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda v: _kwh(v.total_power_consumed),
    ),
    MoolinkSensorDescription(
        key="total_power_regenerated",
        translation_key="energy_regenerated_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda v: _kwh(v.total_power_regenerated),
    ),
    MoolinkSensorDescription(
        key="power_consumption_30d",
        translation_key="consumption_30d",
        device_class=SensorDeviceClass.ENERGY_DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_consumption_30d,
        unit_fn=_consumption_unit,
    ),
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
        if (
            description.value_fn(vehicle) is not None
            if description.value_fn
            else reports(vehicle, description.key)
        )
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
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.vehicle)
        value = getattr(self.vehicle, self.entity_description.key, None)
        if isinstance(value, datetime) and value.tzinfo is None:
            return None  # HA requires timezone-aware timestamps
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the fixed unit or the unit reported by the car."""
        if self.entity_description.unit_fn:
            return self.entity_description.unit_fn(self.vehicle)
        if self.entity_description.unit_from_vehicle:
            return vehicle_unit(self.vehicle, self.entity_description.key)
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra detail, such as today's energy breakdown."""
        if self.entity_description.attrs_fn:
            return self.entity_description.attrs_fn(self.vehicle)
        return None


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
            "polling_paused": self.coordinator.polling_paused_reason,
        }
