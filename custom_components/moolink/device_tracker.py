"""Location tracking for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MoolinkConfigEntry
from .entity import MoolinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a location tracker per vehicle."""
    coordinator = entry.runtime_data
    async_add_entities(
        MoolinkTracker(coordinator, vehicle_id, "location")
        for vehicle_id in coordinator.data
    )


class MoolinkTracker(MoolinkEntity, TrackerEntity):
    """The vehicle's last reported GPS position."""

    _attr_translation_key = "location"

    @property
    def latitude(self) -> float | None:
        """Return the latitude."""
        return self.vehicle.location_latitude

    @property
    def longitude(self) -> float | None:
        """Return the longitude."""
        return self.vehicle.location_longitude

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return when the position was recorded."""
        updated = self.vehicle.location_last_updated_at
        return {"location_updated_at": updated.isoformat() if updated else None}
