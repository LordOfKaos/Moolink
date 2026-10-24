"""Repairs for the Moolink (Hyundai Bluelink) integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant

from .const import CONF_PIN


class PinRepairFlow(RepairsFlow):
    """Ask for the Bluelink PIN again after Bluelink rejected it."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the flow."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Show the PIN form, then save the PIN and reload."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_removed")
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_PIN: user_input[CONF_PIN].strip()}
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_PIN): str}),
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the flow that fixes an issue."""
    assert data is not None
    return PinRepairFlow(data["entry_id"])
