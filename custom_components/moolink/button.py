"""Buttons for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MoolinkConfigEntry, MoolinkCoordinator
from .entity import MoolinkEntity, supports


@dataclass(frozen=True, kw_only=True)
class MoolinkButtonDescription(ButtonEntityDescription):
    """Button that calls a VehicleManager command.

    `api_method` is the region API method used to check support; `command` is
    the VehicleManager method invoked. `ev_only` limits it to cars with an
    EV battery.
    """

    command: str
    api_method: str
    ev_only: bool = False


BUTTONS: tuple[MoolinkButtonDescription, ...] = (
    MoolinkButtonDescription(
        key="force_refresh",
        translation_key="force_refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        command="force_refresh_vehicle_state",
        api_method="force_refresh_vehicle_state",
    ),
    MoolinkButtonDescription(
        key="hazard_lights",
        translation_key="hazard_lights",
        command="start_hazard_lights",
        api_method="start_hazard_lights",
    ),
    MoolinkButtonDescription(
        key="hazard_lights_and_horn",
        translation_key="hazard_lights_and_horn",
        command="start_hazard_lights_and_horn",
        api_method="start_hazard_lights_and_horn",
    ),
    MoolinkButtonDescription(
        key="open_charge_port",
        translation_key="open_charge_port",
        command="open_charge_port",
        api_method="charge_port_action",
        ev_only=True,
    ),
    MoolinkButtonDescription(
        key="close_charge_port",
        translation_key="close_charge_port",
        command="close_charge_port",
        api_method="charge_port_action",
        ev_only=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create buttons for commands this region supports."""
    coordinator = entry.runtime_data
    async_add_entities(
        MoolinkButton(coordinator, vehicle_id, description)
        for vehicle_id, vehicle in coordinator.data.items()
        for description in BUTTONS
        if supports(coordinator, description.api_method)
        and (not description.ev_only or vehicle.ev_battery_percentage is not None)
    )


class MoolinkButton(MoolinkEntity, ButtonEntity):
    """A one-shot vehicle command."""

    entity_description: MoolinkButtonDescription

    def __init__(
        self,
        coordinator: MoolinkCoordinator,
        vehicle_id: str,
        description: MoolinkButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, vehicle_id, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the command."""
        if self.entity_description.key == "force_refresh":
            await self.coordinator.async_force_refresh(self.vehicle_id)
        else:
            await self._async_command(self.entity_description.command)
