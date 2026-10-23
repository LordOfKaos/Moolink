"""Charging switch for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MoolinkConfigEntry
from .entity import MoolinkEntity, supports


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create charging switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    for vehicle_id, vehicle in coordinator.data.items():
        if vehicle.ev_battery_is_charging is not None and supports(
            coordinator, "start_charge"
        ):
            entities.append(MoolinkChargingSwitch(coordinator, vehicle_id, "charging"))
    async_add_entities(entities)


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
