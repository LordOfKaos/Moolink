"""The weekly workflow's library upgrade script."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "bump_library", ROOT / ".github" / "scripts" / "bump_library.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bump_pins_library_and_raises_patch_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "custom_components" / "moolink").mkdir(parents=True)
    shutil.copy(
        ROOT / "custom_components" / "moolink" / "manifest.json",
        tmp_path / "custom_components" / "moolink" / "manifest.json",
    )
    shutil.copy(ROOT / "requirements_test.txt", tmp_path / "requirements_test.txt")
    before = json.loads(
        (tmp_path / "custom_components/moolink/manifest.json").read_text()
    )
    monkeypatch.chdir(tmp_path)

    _load_script().main("9.9.9")

    after = json.loads(
        (tmp_path / "custom_components/moolink/manifest.json").read_text()
    )
    assert after["requirements"] == ["hyundai_kia_connect_api==9.9.9"]
    major, minor, patch = before["version"].split(".")
    assert after["version"] == f"{major}.{minor}.{int(patch) + 1}"
    assert (
        "hyundai_kia_connect_api==9.9.9"
        in (tmp_path / "requirements_test.txt").read_text()
    )
    # Everything else in the manifest is untouched.
    for key in before.keys() - {"requirements", "version"}:
        assert after[key] == before[key]
