"""EV charge limits for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MoolinkConfigEntry, MoolinkCoordinator
from .entity import MoolinkEntity, supports

# Vehicle attribute for each limit; the API sets both limits in one call.
LIMIT_KEYS = ("ev_charge_limits_ac", "ev_charge_limits_dc")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create AC/DC charge limit numbers for EVs that report them."""
    coordinator = entry.runtime_data
    if not supports(coordinator, "set_charge_limits"):
        return
    async_add_entities(
        MoolinkChargeLimit(coordinator, vehicle_id, key)
        for vehicle_id, vehicle in coordinator.data.items()
        if all(getattr(vehicle, k, None) is not None for k in LIMIT_KEYS)
        for key in LIMIT_KEYS
    )


class MoolinkChargeLimit(MoolinkEntity, NumberEntity):
    """Target state of charge for AC or DC charging."""

    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 10
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: MoolinkCoordinator, vehicle_id: str, key: str
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, vehicle_id, key)
        self._key = key
        self._attr_translation_key = key

    @property
    def native_value(self) -> float | None:
        """Return the current limit."""
        return getattr(self.vehicle, self._key)

    async def async_set_native_value(self, value: float) -> None:
        """Set this limit, keeping the other one unchanged."""
        limits = {k: getattr(self.vehicle, k) for k in LIMIT_KEYS}
        limits[self._key] = int(value)
        await self._async_command(
            "set_charge_limits",
            limits["ev_charge_limits_ac"],
            limits["ev_charge_limits_dc"],
        )
