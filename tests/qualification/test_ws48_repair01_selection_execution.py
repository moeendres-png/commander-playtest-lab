"""WS48-R1f Repair-01 regression: selection->execution index integrity.

Focused WS48 tests for ws48_behavior_provider_overlay.py. All tests operate
on live R1e source (overlay + base generator); none touch pinned Forge
source, WS47, WS50, or another workstream's surface.

Pre-fix state: the gate tests FAIL (double-add present).
Post-fix state: all tests PASS.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIR = (
    REPO_ROOT / "candidate-qualification" / "ws48-forge-v1.0.5"
)
OVERLAY_PATH = CANDIDATE_DIR / "ws48_behavior_provider_overlay.py"
GATE_PATH = CANDIDATE_DIR / "ws48_r1f_selection_execution_gate.py"
GENERATOR_PATH = (
    REPO_ROOT / "scripts" / "ws23_generate_forge_vertical_provider.py"
)


def load_overlay_module():
    spec = importlib.util.spec_from_file_location(
        "ws48_behavior_provider_overlay", OVERLAY_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_gate(*argv: str) -> tuple[int, dict]:
    p = subprocess.run(
        [sys.executable, str(GATE_PATH), *argv],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    try:
        payload = json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        payload = {"stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:]}
    return p.returncode, payload


def test_overlay_adds_no_native_option_per_label():
    """Repair-01 core: overlay label patch must not populate nativeOptions."""
    src = OVERLAY_PATH.read_text(encoding="utf-8")
    mod = load_overlay_module()
    assert mod.PRIORITY_LABEL_ANCHOR in src
    assert "nativeOptions.add(sa);" not in mod.PRIORITY_LABEL_NEW
    assert 'labels.add("WS48:ACT:' in mod.PRIORITY_LABEL_NEW


def test_base_generator_adds_exactly_once():
    src = GENERATOR_PATH.read_text(encoding="utf-8")
    idx = src.find("if (seen.add(sa)) {")
    assert idx >= 0
    block = src[idx : src.find("\n                        }", idx)]
    assert block.count("nativeOptions.add(sa);") == 1
    assert block.count('labels.add("FORGE_LEGAL_ACTION");') == 1


def test_gate_passes_on_live_source_with_negative_control():
    rc, payload = run_gate("--mutate-check")
    assert rc == 0, payload.get("reason")
    assert payload["verdict"] == "PASS"
    assert payload["selection_execution_integrity"] == "PASS"
    assert payload["mutate_check"]["synthesized_double_add_flagged"] is True


def test_gate_detects_synthesized_double_add_provider():
    evil = (
        "if (seen.add(sa)) {\n"
        "    nativeOptions.add(sa);\n"
        "    nativeOptions.add(sa);\n"
        '    labels.add("WS48:ACT");\n'
        "}\n"
        "WS48_SELECTION_EXECUTION_CARDINALITY_MISMATCH"
    )
    tmp = Path("/tmp/ws48-r1f-evil-provider.java")
    tmp.write_text(evil, encoding="utf-8")
    rc, payload = run_gate("--provider", str(tmp))
    assert rc == 2
    assert payload["verdict"] == "FAIL"
    assert payload["provider_native_adds"] == 2


def test_fixed_mapping_binds_every_selection_exactly():
    rc, payload = run_gate()
    assert rc == 0
    fixed = payload["mechanism"]["fixed"]
    assert fixed["native_count"] == fixed["n"]
    assert fixed["label_count"] == fixed["n"] + 1
    assert fixed["all_bind_exactly"] is True
    broken = payload["mechanism"]["broken"]
    assert broken["rows"][0]["binds_exactly"] is True
    assert not any(r["binds_exactly"] for r in broken["rows"][1:])


def test_first_act_still_binds_post_fix():
    rc, payload = run_gate()
    assert rc == 0
    first = payload["mechanism"]["fixed"]["rows"][0]
    assert first["selected_idx"] == 1
    assert first["binds_exactly"] is True


def test_parallel_structure_audit_fully_resolved():
    rc, payload = run_gate()
    assert rc == 0
    totals = payload["parallel_structure_totals"]
    assert totals.get("UNKNOWN", 0) == 0
    assert totals.get("TARGETED_REPAIR_REQUIRED", 0) == 0
    # Sentinel/offset transports keep their guards.
    by_name = {t["transport"]: t for t in payload["parallel_structure_audit"]}
    for name in (
        "chooseTargetsFor",
        "chooseSingleEntityForEffect",
        "chooseCardsForEffect",
        "chooseEntitiesForEffect",
        "chooseCardsForZoneChange",
        "declareAttackers/declareBlockers",
    ):
        assert by_name[name]["status"] == "INVARIANT_PROVEN", name


def test_runtime_cardinality_guard_present_in_overlay():
    src = OVERLAY_PATH.read_text(encoding="utf-8")
    assert "WS48_SELECTION_EXECUTION_CARDINALITY_MISMATCH" in src
    assert "WS48_SELECTION_EXECUTION_INDEX_OUT_OF_RANGE" in src
    assert "priority_binding" in src


def test_fail_closed_safeguards_intact():
    src = OVERLAY_PATH.read_text(encoding="utf-8")
    for marker in (
        "throw failClosed(",
        "WS48_UNSUPPORTED_DISCRETIONARY_DECISION",
        "SINGLE_NATIVE_OPTION",
        "STALE_OPTION",
        "ZERO_OR_ONE",
    ):
        assert marker in src, marker


def test_no_internal_ai_default_or_random_fallback():
    src = OVERLAY_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "import forge.ai",
        "import forge.gui",
        "PlayerControllerAi",
        "ComputerUtilMana",
        "candidates.get(0)",
        "new java.util.Random",
        "Math.random",
    ):
        assert forbidden not in src, forbidden


def test_overlay_priority_patch_idempotent():
    """Applying the label replacement twice must not duplicate content."""
    mod = load_overlay_module()
    base = (
        "                        if (seen.add(sa)) {\n"
        "                            nativeOptions.add(sa);\n"
        '                            labels.add("FORGE_LEGAL_ACTION");\n'
        "                        }\n"
    )
    once_applied = mod.once(
        base, mod.PRIORITY_LABEL_ANCHOR, mod.PRIORITY_LABEL_NEW, "probe"
    )
    twice_applied = mod.once(
        once_applied,
        mod.PRIORITY_LABEL_ANCHOR,
        mod.PRIORITY_LABEL_NEW,
        "probe",
    )
    assert once_applied == twice_applied
    assert once_applied.count("nativeOptions.add(sa);") == 1
    assert once_applied.count('labels.add("WS48:ACT:') == 1


def load_probe_module():
    import importlib.util

    path = (
        REPO_ROOT
        / "candidate-qualification"
        / "ws48-forge-v1.0.5"
        / "run_behavior_transcript_probe.py"
    )
    spec = importlib.util.spec_from_file_location(
        "ws48_probe_under_test", path
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _priority_frame(option_kinds: list[str]) -> tuple[list[dict], list[dict]]:
    probe = load_probe_module()
    opts = [{"option_id": f"o{i}", "kind": k} for i, k in enumerate(option_kinds)]
    labels = [probe.dec_label(k) for k in option_kinds]
    return probe, opts, labels


def _driver_with_priority_script(probe, want_host: str):
    record = {
        "fixture_id": "UNIT",
        "execution_entry_mode": "NATIVE_STATE_LOAD",
        "decision_script": [
            {"decision_family": "priority", "actor": "P1",
             "selection": {"selector_kind": "semantic_action",
                           "semantic_value": {"action": "cast",
                                              "object": want_host}}},
        ],
    }
    return probe.Driver(record)


def test_zero_match_fails_closed():
    probe, opts, labels = _priority_frame(
        ["PASS", "WS48:ACT:host=obj%3Aa:cmd=null:card=X:sa=cast"]
    )
    drv = _driver_with_priority_script(probe, "obj:missing")
    with pytest.raises(probe.Blocked):
        probe.answer_priority(drv, "P1", opts, labels)
    assert drv.consumed == []


def test_ambiguous_match_fails_closed():
    probe, opts, labels = _priority_frame(
        ["PASS",
         "WS48:ACT:host=obj%3Aa:cmd=null:card=X:sa=cast",
         "WS48:ACT:host=obj%3Aa:cmd=null:card=X:sa=cast"]
    )
    drv = _driver_with_priority_script(probe, "obj:a")
    with pytest.raises(probe.Blocked):
        probe.answer_priority(drv, "P1", opts, labels)
    assert drv.consumed == []


def test_unsupported_kind_fails_closed():
    probe = load_probe_module()
    drv = probe.Driver({"fixture_id": "UNIT",
                        "execution_entry_mode": "NATIVE_STATE_LOAD",
                        "decision_script": []})
    with pytest.raises(probe.Blocked):
        probe.answer_frame(drv, "choose_unsupported_kind_xyz", "P1",
                           [{"option_id": "o0", "kind": "PASS"}],
                           [{"_kind": "PASS"}], {"fixture_id": "UNIT",
                                                 "execution_entry_mode": "NATIVE_STATE_LOAD"})
