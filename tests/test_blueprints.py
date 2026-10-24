"""The automation blueprints shipped in blueprints/ are valid.

Each blueprint is checked against Home Assistant's blueprint schema, then
filled in with sample inputs and validated as a real automation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from homeassistant.components.automation.config import (
    _async_validate_config_item,
)
from homeassistant.components.blueprint import schemas
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as yaml_util

BLUEPRINTS = Path(__file__).parent.parent / "blueprints" / "automation" / "moolink"
NOTIFY = [{"action": "persistent_notification.create", "data": {"message": "hi"}}]

SAMPLE_INPUTS = {
    "left_unlocked.yaml": {
        "car_lock": "lock.kona_doors",
        "lock_again": True,
        "actions": NOTIFY,
    },
    "charging_finished.yaml": {
        "charging_sensor": "binary_sensor.kona_charging",
        "battery_sensor": "sensor.kona_ev_battery",
        "actions": NOTIFY,
    },
    "open_at_night.yaml": {
        "openings": ["binary_sensor.kona_trunk", "binary_sensor.kona_sunroof"],
        "actions": NOTIFY,
    },
    "preheat.yaml": {
        "car_climate": "climate.kona_climate",
        "temperature": 20.5,
    },
}


def test_every_blueprint_has_sample_inputs() -> None:
    assert {p.name for p in BLUEPRINTS.glob("*.yaml")} == set(SAMPLE_INPUTS)


@pytest.mark.parametrize("name", sorted(SAMPLE_INPUTS))
async def test_blueprint_is_valid(hass: HomeAssistant, name: str) -> None:
    await async_setup_component(hass, "homeassistant", {})
    path = BLUEPRINTS / name
    blueprint = Blueprint(
        yaml_util.load_yaml(path),
        path=str(path),
        expected_domain="automation",
        schema=schemas.BLUEPRINT_SCHEMA,
    )
    meta = blueprint.metadata
    assert meta["source_url"].endswith(f"/blueprints/automation/moolink/{name}")
    assert meta["author"] == "Moolink"

    inputs = BlueprintInputs(
        blueprint,
        {
            "alias": name,
            "use_blueprint": {"path": f"moolink/{name}", "input": SAMPLE_INPUTS[name]},
        },
    )
    inputs.validate()
    config = inputs.async_substitute()
    validated = await _async_validate_config_item(hass, config, True, False)
    assert validated is not None
