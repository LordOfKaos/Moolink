"""Base entity for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from hyundai_kia_connect_api import Vehicle
from hyundai_kia_connect_api.ApiImpl import ApiImpl

from .const import BRANDS, CONF_BRAND, DOMAIN
from .coordinator import MoolinkCoordinator


def supports(coordinator: MoolinkCoordinator, api_method: str) -> bool:
    """Return whether the region's API implements a command.

    The library's base class raises NotImplementedError for every command, so
    a command is supported when the region subclass overrides it.
    """
    impl = type(coordinator.vehicle_manager.api)
    return getattr(impl, api_method, None) is not getattr(ApiImpl, api_method, None)


def vehicle_unit(vehicle: Vehicle, key: str) -> str | None:
    """Return the unit the library reported for a value, if any."""
    return getattr(vehicle, f"{key}_unit", None) or getattr(
        vehicle, f"_{key}_unit", None
    )


class MoolinkEntity(CoordinatorEntity[MoolinkCoordinator]):
    """An entity belonging to one vehicle."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MoolinkCoordinator, vehicle_id: str, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.vehicle_id = vehicle_id
        self._attr_unique_id = f"{vehicle_id}_{key}"
        vehicle = self.vehicle
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle_id)},
            manufacturer=BRANDS.get(coordinator.config_entry.data[CONF_BRAND]),
            model=vehicle.model,
            name=vehicle.name or vehicle.model or vehicle_id,
            serial_number=vehicle.VIN or None,
            sw_version=vehicle.software_version,
        )

    @property
    def vehicle(self) -> Vehicle:
        """Return the current vehicle object."""
        return self.coordinator.vehicle_manager.vehicles[self.vehicle_id]

    @property
    def available(self) -> bool:
        """Entities are available while the vehicle is known and polling works."""
        return (
            super().available
            and self.vehicle_id in self.coordinator.vehicle_manager.vehicles
        )

    async def _async_command(self, method: str, *args: Any) -> None:
        """Send a remote command for this vehicle."""
        await self.coordinator.async_send_command(self.vehicle_id, method, *args)
