"""Climate control for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import climate_options
from .const import (
    CONF_CLIMATE_TEMPERATURE,
    CONF_REGION,
    REGION_USA,
    default_climate_temperature,
)
from .coordinator import MoolinkConfigEntry, MoolinkCoordinator
from .entity import MoolinkEntity, supports


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a climate control per vehicle."""
    coordinator = entry.runtime_data
    if not supports(coordinator, "start_climate"):
        return
    async_add_entities(
        MoolinkClimate(coordinator, vehicle_id, "climate")
        for vehicle_id in coordinator.data
    )


class MoolinkClimate(MoolinkEntity, ClimateEntity):
    """Remote climate: off, or running towards a target temperature.

    Bluelink has no separate heat and cool modes; the car decides. The
    target temperature is kept in the integration options, so the
    `moolink.start_climate` action and options page share it.
    """

    _attr_translation_key = "climate"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self, coordinator: MoolinkCoordinator, vehicle_id: str, key: str
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, vehicle_id, key)
        region = coordinator.config_entry.data[CONF_REGION]
        self._attr_temperature_unit = (
            UnitOfTemperature.FAHRENHEIT
            if region == REGION_USA
            else UnitOfTemperature.CELSIUS
        )
        allowed = getattr(coordinator.vehicle_manager.api, "temperature_range", None)
        if allowed and len(allowed) > 1:
            self._attr_min_temp = float(allowed[0])
            self._attr_max_temp = float(allowed[-1])
            self._attr_target_temperature_step = float(allowed[1] - allowed[0])
        else:
            self._attr_target_temperature_step = 0.5
        if coordinator.climate_max is not None:
            self._attr_max_temp = min(
                getattr(self, "_attr_max_temp", coordinator.climate_max),
                coordinator.climate_max,
            )

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return whether climate control is running."""
        running = self.vehicle.air_control_is_on
        if running is None:
            return None
        return HVACMode.HEAT_COOL if running else HVACMode.OFF

    @property
    def target_temperature(self) -> float:
        """Return the temperature the next start will use."""
        entry = self.coordinator.config_entry
        return entry.options.get(
            CONF_CLIMATE_TEMPERATURE,
            default_climate_temperature(entry.data[CONF_REGION]),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Remember the target; apply it now if climate is already running."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self.coordinator.validate_temperature(temperature)
            entry = self.coordinator.config_entry
            self.hass.config_entries.async_update_entry(
                entry,
                options={**entry.options, CONF_CLIMATE_TEMPERATURE: temperature},
            )
            self.async_write_ha_state()
        if (mode := kwargs.get("hvac_mode")) is not None:
            await self.async_set_hvac_mode(mode)
        elif temperature is not None and self.hvac_mode == HVACMode.HEAT_COOL:
            await self._async_start()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Start or stop climate control."""
        if hvac_mode == HVACMode.OFF:
            await self._async_command("stop_climate")
        else:
            await self._async_start()

    async def async_turn_on(self) -> None:
        """Start climate control."""
        await self._async_start()

    async def async_turn_off(self) -> None:
        """Stop climate control."""
        await self._async_command("stop_climate")

    async def _async_start(self) -> None:
        await self._async_command(
            "start_climate", climate_options(self.coordinator.config_entry)
        )
