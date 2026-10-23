"""Data update coordinator for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from hyundai_kia_connect_api import Token, Vehicle, VehicleManager
from hyundai_kia_connect_api.const import ORDER_STATUS
from hyundai_kia_connect_api.exceptions import (
    AuthenticationError,
    DuplicateRequestError,
    HyundaiKiaException,
    RateLimitingError,
)

from .api_counter import ApiRequestCounter
from .const import (
    ACTION_STATUS_TIMEOUT,
    COMMAND_REFRESH_DELAY,
    CONF_BRAND,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_PIN,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_FORCE_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# How commands are described in errors; others fall back to the method name.
COMMAND_NAMES = {
    "start_hazard_lights": "flash hazard lights",
    "start_hazard_lights_and_horn": "hazard lights and horn",
    "start_climate": "start climate",
    "stop_climate": "stop climate",
    "start_charge": "start charging",
    "stop_charge": "stop charging",
    "set_charge_limits": "set charge limits",
    "force_refresh_vehicle_state": "force refresh",
}

type MoolinkConfigEntry = ConfigEntry[MoolinkCoordinator]


def build_vehicle_manager(data: dict[str, Any]) -> VehicleManager:
    """Create a VehicleManager from config entry data."""
    token = data.get(CONF_TOKEN)
    return VehicleManager(
        region=data[CONF_REGION],
        brand=data[CONF_BRAND],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        pin=data.get(CONF_PIN) or "",
        token=Token.from_dict(token) if token else None,
    )


class MoolinkCoordinator(DataUpdateCoordinator[dict[str, Vehicle]]):
    """Polls the Bluelink cloud for all vehicles on one account."""

    config_entry: MoolinkConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MoolinkConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.vehicle_manager = build_vehicle_manager(dict(entry.data))
        self.api_counter = ApiRequestCounter(entry.data[CONF_REGION])
        self.api_counter.attach(getattr(self.vehicle_manager.api, "session", None))
        # Day on which Bluelink said the daily request limit was used up.
        self.rate_limited_on: date | None = None
        self.force_refresh_interval: int = entry.options.get(
            CONF_FORCE_REFRESH_INTERVAL, DEFAULT_FORCE_REFRESH_INTERVAL
        )
        # The library is synchronous and not thread-safe; serialize all calls.
        self._api_lock = asyncio.Lock()
        # Command still being carried out, per vehicle. Bluelink rejects a
        # second command while one is in progress, so we refuse it up front.
        self._pending: dict[str, str] = {}

    def validate_temperature(self, value: float) -> None:
        """Reject temperatures the region's API can't encode."""
        allowed = getattr(self.vehicle_manager.api, "temperature_range", None)
        if allowed and value not in allowed:
            raise ServiceValidationError(
                f"Temperature {value} is not supported here; use "
                f"{allowed[0]}-{allowed[-1]} in steps of "
                f"{allowed[1] - allowed[0]}"
            )

    async def _async_run(self, func: Callable[..., Any], *args: Any) -> Any:
        """Run a blocking library call after making sure the token is valid."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self.vehicle_manager.check_and_refresh_token
            )
            result = await self.hass.async_add_executor_job(func, *args)
        self._persist_token()
        return result

    def _persist_token(self) -> None:
        """Store the current token so restarts don't need a fresh login/OTP."""
        token = self.vehicle_manager.token
        if token is None:
            return
        token_dict = token.to_dict()
        if self.config_entry.data.get(CONF_TOKEN) != token_dict:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token_dict},
            )

    def _update_all(self) -> None:
        vm = self.vehicle_manager
        if self.force_refresh_interval > 0:
            vm.check_and_force_update_vehicles(self.force_refresh_interval * 60)
        else:
            vm.update_all_vehicles_with_cached_state()

    @property
    def rate_limited(self) -> bool:
        """Whether Bluelink's daily request limit is used up for today."""
        return self.rate_limited_on == dt_util.now().date()

    async def _async_update_data(self) -> dict[str, Vehicle]:
        """Fetch the latest state of all vehicles."""
        if self.rate_limited and self.data is not None:
            # Polling now would only be refused again; keep the last state.
            return self.data
        try:
            await self._async_run(self._update_all)
        except RateLimitingError as err:
            self.rate_limited_on = dt_util.now().date()
            _LOGGER.warning(
                "Bluelink's daily request limit is used up; polling paused until "
                "midnight (%s requests counted today)",
                self.api_counter.count,
            )
            if self.data is not None:
                return self.data
            raise UpdateFailed("Bluelink's daily request limit is used up") from err
        except AuthenticationError as err:
            # Includes AuthenticationOTPRequired; both need user interaction.
            raise ConfigEntryAuthFailed(str(err)) from err
        except HyundaiKiaException as err:
            raise UpdateFailed(f"Error communicating with Bluelink: {err}") from err
        except Exception as err:  # the library leaks requests/JSON errors
            raise UpdateFailed(f"Unexpected Bluelink error: {err}") from err
        return dict(self.vehicle_manager.vehicles)

    async def async_force_refresh(self, vehicle_id: str | None = None) -> None:
        """Wake the car(s) and pull fresh state, bypassing the cloud cache."""
        vm = self.vehicle_manager
        try:
            if vehicle_id is None:
                await self._async_run(vm.force_refresh_all_vehicles_states)
            else:
                await self._async_run(vm.force_refresh_vehicle_state, vehicle_id)
        except RateLimitingError as err:
            self.rate_limited_on = dt_util.now().date()
            raise _command_error("force_refresh_vehicle_state", err) from err
        except AuthenticationError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Bluelink authentication failed: {err}") from err
        except Exception as err:
            raise HomeAssistantError(f"Force refresh failed: {err}") from err
        self.async_set_updated_data(dict(vm.vehicles))

    async def async_send_command(
        self, vehicle_id: str, method: str, *args: Any
    ) -> None:
        """Send a remote command and refresh state once the car has acted."""
        if pending := self._pending.get(vehicle_id):
            raise HomeAssistantError(
                f"The car is still carrying out '{_command_name(pending)}'. "
                "Wait for it to finish, then try again."
            )
        self._pending[vehicle_id] = method
        func = getattr(self.vehicle_manager, method)
        try:
            action_id = await self._async_run(func, vehicle_id, *args)
        except Exception as err:
            self._pending.pop(vehicle_id, None)
            if isinstance(err, AuthenticationError):
                self.config_entry.async_start_reauth(self.hass)
            raise _command_error(method, err) from err
        except BaseException:
            self._pending.pop(vehicle_id, None)
            raise

        self.config_entry.async_create_background_task(
            self.hass,
            self._async_follow_up(vehicle_id, method, action_id),
            f"{DOMAIN}_{method}_follow_up",
        )

    async def _async_follow_up(
        self, vehicle_id: str, method: str, action_id: str | None
    ) -> None:
        """Wait for the command to complete, then refresh the vehicle."""
        status: ORDER_STATUS | None = None
        try:
            if action_id:
                try:
                    # Polls without holding the API lock so other calls aren't
                    # blocked.
                    status = await self.hass.async_add_executor_job(
                        self.vehicle_manager.check_action_status,
                        vehicle_id,
                        action_id,
                        True,
                        ACTION_STATUS_TIMEOUT,
                    )
                except Exception:  # noqa: BLE001 - not every region supports this
                    _LOGGER.debug("Action status unavailable for %s", method)
            if status is None:
                await asyncio.sleep(COMMAND_REFRESH_DELAY)
        finally:
            self._pending.pop(vehicle_id, None)

        if status in (ORDER_STATUS.FAILED, ORDER_STATUS.TIMEOUT):
            _LOGGER.warning(
                "Bluelink command %s finished with %s", method, status.value
            )
        elif status is not None:
            _LOGGER.debug("Bluelink command %s finished with %s", method, status.value)

        try:
            await self._async_run(
                self.vehicle_manager.update_vehicle_with_cached_state, vehicle_id
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Refresh after %s failed: %s", method, err)
            return
        self.async_set_updated_data(dict(self.vehicle_manager.vehicles))


def _command_name(method: str) -> str:
    return COMMAND_NAMES.get(method, method.replace("_", " "))


def _command_error(method: str, err: Exception) -> HomeAssistantError:
    """Turn a library error from a command into a message for the user."""
    name = _command_name(method)
    if isinstance(err, AuthenticationError):
        return HomeAssistantError(f"Bluelink authentication failed: {err}")
    if isinstance(err, NotImplementedError):
        return HomeAssistantError(f"'{name}' is not supported for this region")
    if isinstance(err, RateLimitingError):
        return HomeAssistantError(
            f"Bluelink's daily request limit is used up, so '{name}' was not "
            "sent. It resets at midnight."
        )
    if isinstance(err, DuplicateRequestError):
        return HomeAssistantError(
            f"Bluelink is still processing a previous command, so '{name}' "
            "was not sent. Wait a minute, then try again."
        )
    if "PIN" in str(err):
        return HomeAssistantError(
            "Bluelink rejected your PIN. Update it under Settings → "
            "Devices & services → Moolink → ⋮ → Reconfigure."
        )
    return HomeAssistantError(f"Bluelink command '{name}' failed: {err}")
