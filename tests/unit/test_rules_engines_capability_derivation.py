"""#662 / SLOT-06 §(b)2: rules_engines.json missing capabilities follow from evidence.

The engine list (``primary_engine``) must equal what the freeze-record assembler derives
for the production lane from the newest sealed epoch bound to the current pin; the
runtime list (``current_runtime``) must equal what the launched runtime
(``production_bridge``; since D5 the full-game lane) reports in the same epoch's AF01.
A ready or selected provider requires both lists to derive empty. A hand edit of either list, in either
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


def _signed_epoch() -> tuple[Path, str]:
    """The sealed epoch and engine commit the manifest's derived lists were signed on.

    ``--check`` derives from the live pin, so it can only run once PB-03 has sealed an
    epoch on that pin. These tests address the signed epoch explicitly instead; the
    live refusal is asserted separately, never papered over.
    """
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    freeze = config["architecture_freeze"]
    return REPO_ROOT / freeze["evidence_epoch"], str(freeze["engine_commit"])


def test_rules_engines_missing_capabilities_are_derived_from_newest_epoch() -> None:
    module = _derive_module()
    epoch, pin = _signed_epoch()
    chosen, engine, runtime = module.derive(epoch, pin)
    assert chosen == epoch
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    assert engine == config["primary_engine"]["missing_required_capabilities"] == []
    assert runtime == config["current_runtime"]["required_missing_capabilities"] == []


def test_check_refuses_while_no_sealed_epoch_is_bound_to_the_live_pin() -> None:
    """A repin moves the pin before PB-03 reruns: --check must not pass on the old epoch."""
    module = _derive_module()
    live = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    _, pin = _signed_epoch()
    if live["primary_engine"]["commit"] == pin:
        pytest.skip("the live pin is the signed one; --check is already covered above")
    with pytest.raises(SystemExit, match="no sealed epoch is bound to the XMage pin"):
        module.main(["--check"])


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
    _, pin = _signed_epoch()
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
        # --check derives from the manifest's own pin, so address the sealed epoch.
        changed["primary_engine"]["commit"] = pin
        fake = tmp_path / "rules_engines.json"
        fake.write_text(json.dumps(changed), encoding="utf-8")
        monkeypatch.setattr(module, "CONFIG", fake)
        assert module.main(["--check"]) == 1


def test_runtime_list_fails_closed_without_its_evidence(tmp_path: Path) -> None:
    module = _derive_module()
    everything = sorted(module.REQUIRED_CAPABILITIES)
    pin = "b" * 40
    bridge = "b4d_event_log_lifecycle_bridge"
    path = tmp_path / "AF01_XMAGE_COMPATIBILITY_SUPPORT.json"

    def missing_with(**changes: object) -> list[str]:
        report: dict[str, object] = {
            "verdict": "PASS",
            "lane": "compatibility",
            "engine_commit_reported": pin,
            "capabilities_provider_reported": {name: True for name in everything},
        }
        report.update(changes)
        path.write_text(json.dumps(report), encoding="utf-8")
        return list(module.runtime_missing(tmp_path, bridge, pin))

    # No compatibility-lane AF01 in the epoch: every required capability is missing.
    assert module.runtime_missing(tmp_path, bridge, pin) == everything
    assert missing_with() == []
    assert missing_with(verdict="FAIL") == everything
    assert missing_with(lane="full-game") == everything
    assert missing_with(engine_commit_reported="c" * 40) == everything
    assert missing_with(capabilities_provider_reported=["legal_actions_supported"]) == everything
    truthy = {name: True for name in everything}
    truthy["replay_supported"] = "true"
    assert missing_with(capabilities_provider_reported=truthy) == ["replay_supported"]
    with pytest.raises(SystemExit):
        module.runtime_missing(tmp_path, "an_unmapped_bridge", pin)


def test_no_sealed_epoch_is_bound_to_the_live_pin_until_pb03_reruns_on_it() -> None:
    """A repin moves the pin before PB-03 reruns: the derivation must refuse, not reuse."""
    module = _derive_module()
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    pin = config["primary_engine"]["commit"]
    with pytest.raises(SystemExit, match="no sealed epoch is bound to the XMage pin"):
        module.newest_epoch_for_pin(pin)
    # The newest sealed epoch is still the one the Freeze was signed against, on the
    # prior pin: no epoch evidence is transferred to the newer pin.
    prior = config["architecture_freeze"]["engine_commit"]
    epoch = module.newest_epoch_for_pin(prior)
    assert epoch == REPO_ROOT / config["architecture_freeze"]["evidence_epoch"]
    runtime = json.loads((epoch / "PB03_RUNTIME_EXECUTION.json").read_text(encoding="utf-8"))
    assert runtime["candidate_commit"] == prior
    assert (epoch / "CURRENT_BOUNDARY_SHA256SUMS").is_file()


def test_the_live_pin_derivation_fails_closed_rather_than_borrowing_the_prior_epoch() -> None:
    module = _derive_module()
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    with pytest.raises(SystemExit, match="no sealed epoch is bound to the XMage pin"):
        module.derive()
    # The same derivation over the Freeze epoch is reproducible and still empty.
    epoch, pin = _signed_epoch()
    _, engine, runtime = module.derive(epoch, pin)
    assert engine == config["primary_engine"]["missing_required_capabilities"] == []
    assert runtime == config["current_runtime"]["required_missing_capabilities"] == []


def test_unknown_pin_has_no_epoch() -> None:
    module = _derive_module()
    with pytest.raises(SystemExit):
        module.newest_epoch_for_pin("0" * 40)


@pytest.mark.parametrize("which", ["engine", "runtime"])
def test_ready_provider_with_a_reopened_capability_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, which: str
) -> None:
    """D5: production_ready/XMAGE_SELECTED cannot survive a non-empty derived list."""
    module = _derive_module()
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    assert config["primary_engine"]["production_ready"] is True
    reopened = ["replay_supported"]
    engine = reopened if which == "engine" else []
    runtime = reopened if which == "runtime" else []
    # The file matches the derivation exactly, so only the readiness gate can fail it.
    config["primary_engine"]["missing_required_capabilities"] = engine
    config["current_runtime"]["required_missing_capabilities"] = runtime
    fake = tmp_path / "rules_engines.json"
    fake.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(module, "CONFIG", fake)
    monkeypatch.setattr(module, "derive", lambda epoch=None: (REPO_ROOT, engine, runtime))
    assert module.main(["--check"]) == 1
    assert module.main(["--write"]) == 1
