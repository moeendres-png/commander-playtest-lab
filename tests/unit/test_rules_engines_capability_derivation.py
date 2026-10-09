"""#662 / SLOT-06 §(b)2: rules_engines.json missing capabilities follow from evidence.

The two XMage ``missing_required_capabilities`` lists must equal what the freeze-record
assembler derives from the newest sealed epoch bound to the current pin. A hand edit,
in either direction, fails here (quality job).
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


def test_hand_edited_missing_list_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _derive_module()
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    for edited in ([], ["legal_actions_supported", "action_submission_supported"]):
        config["primary_engine"]["missing_required_capabilities"] = edited
        config["current_runtime"]["required_missing_capabilities"] = edited
        fake = tmp_path / "rules_engines.json"
        fake.write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.setattr(module, "CONFIG", fake)
        assert module.main(["--check"]) == 1


def test_newest_epoch_is_bound_to_the_current_pin() -> None:
    module = _derive_module()
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    pin = config["primary_engine"]["commit"]
    epoch = module.newest_epoch_for_pin(pin)
    af01 = json.loads((epoch / "AF01_XMAGE.json").read_text(encoding="utf-8"))
    assert af01["engine_commit_reported"] == pin


def test_unknown_pin_has_no_epoch() -> None:
    module = _derive_module()
    with pytest.raises(SystemExit):
        module.newest_epoch_for_pin("0" * 40)
