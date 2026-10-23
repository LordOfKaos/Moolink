"""Climate and charging switches for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import climate_options
from .coordinator import MoolinkConfigEntry
from .entity import MoolinkEntity, supports


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create climate and charging switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    for vehicle_id, vehicle in coordinator.data.items():
        if supports(coordinator, "start_climate"):
            entities.append(MoolinkClimateSwitch(coordinator, vehicle_id, "climate"))
        if vehicle.ev_battery_is_charging is not None and supports(
            coordinator, "start_charge"
        ):
            entities.append(MoolinkChargingSwitch(coordinator, vehicle_id, "charging"))
    async_add_entities(entities)


class MoolinkClimateSwitch(MoolinkEntity, SwitchEntity):
    """Remote climate start/stop using the configured defaults.

    For per-call temperature, seat or defrost settings use the
    `moolink.start_climate` action.
    """

    _attr_translation_key = "climate"

    @property
    def is_on(self) -> bool | None:
        """Return whether climate control is running."""
        return self.vehicle.air_control_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start climate control."""
        await self._async_command(
            "start_climate", climate_options(self.coordinator.config_entry)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop climate control."""
        await self._async_command("stop_climate")


class MoolinkChargingSwitch(MoolinkEntity, SwitchEntity):
    """Start/stop EV charging."""

    _attr_translation_key = "charging"

    @property
    def is_on(self) -> bool | None:
        """Return whether the car is charging."""
        return self.vehicle.ev_battery_is_charging

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""
        await self._async_command("start_charge")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""
        await self._async_command("stop_charge")
