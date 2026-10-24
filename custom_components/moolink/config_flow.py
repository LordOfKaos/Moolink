"""Config flow for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)
from hyundai_kia_connect_api import VehicleManager
from hyundai_kia_connect_api.const import OTP_NOTIFY_TYPE
from hyundai_kia_connect_api.exceptions import AuthenticationError

from .const import (
    BRAND_HYUNDAI,
    BRANDS,
    CONF_BRAND,
    CONF_CHARGING_REFRESH_INTERVAL,
    CONF_CLIMATE_DEFROST,
    CONF_CLIMATE_DURATION,
    CONF_CLIMATE_MAX_TEMPERATURE,
    CONF_CLIMATE_TEMPERATURE,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_MIN_12V_BATTERY,
    CONF_OTP_CODE,
    CONF_OTP_METHOD,
    CONF_PIN,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_CHARGING_REFRESH_INTERVAL,
    DEFAULT_CLIMATE_DEFROST,
    DEFAULT_CLIMATE_DURATION,
    DEFAULT_FORCE_REFRESH_INTERVAL,
    DEFAULT_MIN_12V_BATTERY,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PIN_REQUIRED_REGIONS,
    REGIONS,
    default_climate_temperature,
    default_region,
)
from .coordinator import MoolinkConfigEntry, build_vehicle_manager

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _select(options: dict[int, str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=str(key), label=label)
                for key, label in options.items()
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
        vol.Optional(CONF_PIN, default=""): PASSWORD_SELECTOR,
        vol.Required(CONF_REGION): _select(REGIONS),
        vol.Required(CONF_BRAND, default=str(BRAND_HYUNDAI)): _select(BRANDS),
    }
)
RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PASSWORD, default=""): PASSWORD_SELECTOR,
        vol.Optional(CONF_PIN, default=""): PASSWORD_SELECTOR,
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
        vol.Optional(CONF_PIN, default=""): PASSWORD_SELECTOR,
    }
)
OTP_CODE_SCHEMA = vol.Schema({vol.Required(CONF_OTP_CODE): str})


class MoolinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Bluelink login, including the optional OTP challenge."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}
        self._vm: VehicleManager | None = None

    @staticmethod
    @callback
    def async_get_options_flow(entry: MoolinkConfigEntry) -> MoolinkOptionsFlow:
        """Return the options flow."""
        return MoolinkOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for account credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = {
                CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_PIN: user_input.get(CONF_PIN, ""),
                CONF_REGION: int(user_input[CONF_REGION]),
                CONF_BRAND: int(user_input[CONF_BRAND]),
            }
            await self.async_set_unique_id(
                f"{self._data[CONF_REGION]}_{self._data[CONF_BRAND]}_"
                f"{self._data[CONF_USERNAME].lower()}"
            )
            self._abort_if_unique_id_configured()
            if self._pin_missing():
                errors[CONF_PIN] = "pin_required"
            else:
                result, errors = await self._async_login()
                if result is not None:
                    return result

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA,
                user_input
                or {CONF_REGION: str(default_region(self.hass.config.country))},
            ),
            errors=errors,
        )

    def _pin_missing(self) -> bool:
        return (
            self._data[CONF_REGION] in PIN_REQUIRED_REGIONS
            and not self._data[CONF_PIN].strip()
        )

    async def _async_login(self) -> tuple[ConfigFlowResult | None, dict[str, str]]:
        """Try to log in; returns a flow result to proceed with, or form errors."""
        try:
            self._vm = await self.hass.async_add_executor_job(
                build_vehicle_manager, self._data
            )
            logged_in = await self.hass.async_add_executor_job(self._vm.login)
        except AuthenticationError:
            return None, {"base": "invalid_auth"}
        except Exception:
            _LOGGER.exception("Unexpected error logging in to Bluelink")
            return None, {"base": "cannot_connect"}

        if logged_in is True:
            return await self._async_finish(), {}
        if logged_in:  # an OTPRequest
            return await self.async_step_otp_method(), {}
        return None, {"base": "invalid_auth"}

    async def async_step_otp_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose where the one-time code should be sent."""
        assert self._vm is not None
        otp = self._vm.otp_request
        methods: dict[str, str] = {}
        if otp.has_email:
            methods[OTP_NOTIFY_TYPE.EMAIL.value] = f"Email ({otp.email or ''})".strip()
        if otp.has_sms:
            methods[OTP_NOTIFY_TYPE.SMS.value] = f"SMS ({otp.sms or ''})".strip()
        if not methods:
            methods[OTP_NOTIFY_TYPE.EMAIL.value] = "Email"

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    self._vm.send_otp, OTP_NOTIFY_TYPE(user_input[CONF_OTP_METHOD])
                )
            except Exception:
                _LOGGER.exception("Failed to send Bluelink one-time code")
                errors["base"] = "otp_send_failed"
            else:
                return await self.async_step_otp_code()

        return self.async_show_form(
            step_id="otp_method",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OTP_METHOD, default=next(iter(methods))): vol.In(
                        methods
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_otp_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the one-time code."""
        assert self._vm is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    self._vm.verify_otp_and_complete_login,
                    user_input[CONF_OTP_CODE].strip(),
                )
            except AuthenticationError:
                errors["base"] = "invalid_otp"
            except Exception:
                _LOGGER.exception("Unexpected error verifying Bluelink one-time code")
                errors["base"] = "cannot_connect"
            else:
                return await self._async_finish()

        return self.async_show_form(
            step_id="otp_code", data_schema=OTP_CODE_SCHEMA, errors=errors
        )

    async def _async_finish(self) -> ConfigFlowResult:
        """Create or update the entry with the freshly obtained token."""
        assert self._vm is not None
        data = {**self._data, CONF_TOKEN: self._vm.token.to_dict()}
        if self.source == "reauth":
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        if self.source == "reconfigure":
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        return self.async_create_entry(
            title=f"{BRANDS[data[CONF_BRAND]]} {data[CONF_USERNAME]}", data=data
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication when the stored login stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password again."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = {
                **{k: v for k, v in entry.data.items() if k != CONF_TOKEN},
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_PIN: user_input.get(CONF_PIN, ""),
            }
            if self._pin_missing():
                errors[CONF_PIN] = "pin_required"
            else:
                result, errors = await self._async_login()
                if result is not None:
                    return result

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, {CONF_PIN: entry.data.get(CONF_PIN, "")}
            ),
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the PIN and, optionally, the password."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = {
                **{k: v for k, v in entry.data.items() if k != CONF_TOKEN},
                # A blank password keeps the stored one.
                CONF_PASSWORD: user_input.get(CONF_PASSWORD)
                or entry.data[CONF_PASSWORD],
                CONF_PIN: user_input.get(CONF_PIN, "").strip(),
            }
            if self._pin_missing():
                errors[CONF_PIN] = "pin_required"
            else:
                result, errors = await self._async_login()
                if result is not None:
                    return result

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=RECONFIGURE_SCHEMA,
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )


class MoolinkOptionsFlow(OptionsFlowWithReload):
    """Polling and climate-default options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            temperature = user_input[CONF_CLIMATE_TEMPERATURE]
            maximum = user_input.get(CONF_CLIMATE_MAX_TEMPERATURE)
            try:
                if self.config_entry.state is ConfigEntryState.LOADED:
                    # The maximum is checked below against the value being saved.
                    self.config_entry.runtime_data.validate_temperature_range(
                        temperature
                    )
            except ServiceValidationError:
                errors[CONF_CLIMATE_TEMPERATURE] = "invalid_temperature"
            else:
                if maximum is not None and temperature > maximum:
                    errors[CONF_CLIMATE_TEMPERATURE] = "above_max"
                else:
                    return self.async_create_entry(data=user_input)

        opts = {**self.config_entry.options, **(user_input or {})}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=5,
                            max=1440,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    CONF_FORCE_REFRESH_INTERVAL,
                    default=opts.get(
                        CONF_FORCE_REFRESH_INTERVAL, DEFAULT_FORCE_REFRESH_INTERVAL
                    ),
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=1440,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    CONF_CHARGING_REFRESH_INTERVAL,
                    default=opts.get(
                        CONF_CHARGING_REFRESH_INTERVAL,
                        DEFAULT_CHARGING_REFRESH_INTERVAL,
                    ),
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=1440,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    CONF_MIN_12V_BATTERY,
                    default=opts.get(CONF_MIN_12V_BATTERY, DEFAULT_MIN_12V_BATTERY),
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            unit_of_measurement="%",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    CONF_QUIET_START,
                    default=opts.get(CONF_QUIET_START, DEFAULT_QUIET_START),
                ): TimeSelector(),
                vol.Required(
                    CONF_QUIET_END,
                    default=opts.get(CONF_QUIET_END, DEFAULT_QUIET_END),
                ): TimeSelector(),
                vol.Required(
                    CONF_CLIMATE_TEMPERATURE,
                    default=opts.get(
                        CONF_CLIMATE_TEMPERATURE,
                        default_climate_temperature(
                            self.config_entry.data[CONF_REGION]
                        ),
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=14, max=90, step=0.5, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_CLIMATE_MAX_TEMPERATURE,
                    description={
                        "suggested_value": opts.get(CONF_CLIMATE_MAX_TEMPERATURE)
                    },
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=14, max=90, step=0.5, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_CLIMATE_DURATION,
                    default=opts.get(CONF_CLIMATE_DURATION, DEFAULT_CLIMATE_DURATION),
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=30,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    CONF_CLIMATE_DEFROST,
                    default=opts.get(CONF_CLIMATE_DEFROST, DEFAULT_CLIMATE_DEFROST),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
