"""Door lock for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MoolinkConfigEntry
from .entity import MoolinkEntity, supports


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a door lock per vehicle."""
    coordinator = entry.runtime_data
    if not supports(coordinator, "lock_action"):
        return
    async_add_entities(
        MoolinkLock(coordinator, vehicle_id, "door_lock")
        for vehicle_id in coordinator.data
    )


class MoolinkLock(MoolinkEntity, LockEntity):
    """Remote door lock."""

    _attr_translation_key = "door_lock"

    @property
    def is_locked(self) -> bool | None:
        """Return whether the doors are locked."""
        return self.vehicle.is_locked

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the doors."""
        await self._async_command("lock")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the doors."""
        await self._async_command("unlock")
