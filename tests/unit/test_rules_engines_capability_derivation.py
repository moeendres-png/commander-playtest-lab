"""#662 / SLOT-06 §(b)2: rules_engines.json missing capabilities follow from evidence.

The engine list (``primary_engine``) must equal what the freeze-record assembler derives
for the production lane from the newest sealed epoch bound to the current pin; the
runtime list (``current_runtime``) must equal what the launched B4-D bridge reports in
the same epoch's compatibility-lane AF01. A hand edit of either list, in either
direction, fails here (quality job).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _derive_module() -> ModuleType:
    path = REPO_ROOT / "scripts" / "derive_rules_engines_capabilities.py"
    spec = importlib.util.spec_from_file_location("derive_rules_engines_capabilities", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rules_engines_missing_capabilities_are_derived_from_newest_epoch() -> None:
    module = _derive_module()
    assert module.main(["--check"]) == 0


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("primary_engine", "missing_required_capabilities"),
        ("current_runtime", "required_missing_capabilities"),
    ],
)
def test_hand_edited_missing_list_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, section: str, field: str
) -> None:
    module = _derive_module()
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    derived = config[section][field]
    # Any list other than the derived one is a hand edit: removing entries, adding
    # a credited capability back, or clearing a non-empty list.
    candidates = (
        [],
        ["legal_actions_supported", "action_submission_supported"],
        sorted(set(derived) | {"seed_supported"}),
    )
    edits = [edited for edited in candidates if sorted(edited) != sorted(derived)]
    assert len(edits) >= 2
    for edited in edits:
        changed = json.loads(json.dumps(config))
        changed[section][field] = edited
        fake = tmp_path / "rules_engines.json"
        fake.write_text(json.dumps(changed), encoding="utf-8")
        monkeypatch.setattr(module, "CONFIG", fake)
        assert module.main(["--check"]) == 1


def test_runtime_list_fails_closed_without_its_evidence(tmp_path: Path) -> None:
    module = _derive_module()
    everything = sorted(module.REQUIRED_CAPABILITIES)
    # No compatibility-lane AF01 in the epoch: every required capability is missing.
    assert module.runtime_missing(tmp_path, "b4d_event_log_lifecycle_bridge") == everything
    report = {
        "verdict": "FAIL",
        "lane": "compatibility",
        "capabilities_provider_reported": {name: True for name in everything},
    }
    (tmp_path / "AF01_XMAGE_COMPATIBILITY_SUPPORT.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    assert module.runtime_missing(tmp_path, "b4d_event_log_lifecycle_bridge") == everything
    report["verdict"] = "PASS"
    report["lane"] = "full-game"
    (tmp_path / "AF01_XMAGE_COMPATIBILITY_SUPPORT.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    assert module.runtime_missing(tmp_path, "b4d_event_log_lifecycle_bridge") == everything
    report["lane"] = "compatibility"
    (tmp_path / "AF01_XMAGE_COMPATIBILITY_SUPPORT.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    assert module.runtime_missing(tmp_path, "b4d_event_log_lifecycle_bridge") == []
    with pytest.raises(SystemExit):
        module.runtime_missing(tmp_path, "an_unmapped_bridge")


def test_newest_epoch_is_bound_to_the_current_pin() -> None:
    module = _derive_module()
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    pin = config["primary_engine"]["commit"]
    epoch = module.newest_epoch_for_pin(pin)
    runtime = json.loads((epoch / "PB03_RUNTIME_EXECUTION.json").read_text(encoding="utf-8"))
    assert runtime["candidate_commit"] == pin
    assert (epoch / "CURRENT_BOUNDARY_SHA256SUMS").is_file()


def test_unknown_pin_has_no_epoch() -> None:
    module = _derive_module()
    with pytest.raises(SystemExit):
        module.newest_epoch_for_pin("0" * 40)
