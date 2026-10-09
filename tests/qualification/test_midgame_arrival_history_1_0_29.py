"""Contract 1.0.29: the arrival pre-checkpoint history declarations erratum for
every remaining arrival-using lane (#634 / #592, 2026-10-09).

PB-03 run 37860773242 on the #637 head (contract 1.0.28) gave XMage 80 PASS; the
remaining arrival-side failures were the 25 records other lanes execute through
the same strict arrival: the 20 knowledge-projection rows
(``knowledge_projection.ROWS``) and the 5 midgame replay/RNG twin rows
(``midgame_replay_twin.ROWS``). The acceptance criterion is that EVERY record
any arrival-using lane registry executes declares its game-start arrival history
in ``decision_script``: one pregame keep per seat present in the record
(CR 103.5) and a priority pass-through scope (actor ALL) from game start to the
record's own checkpoint, exclusive (CR 117.3d). The red controls remove one
declaration at a time and require the checker to fail.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATH = REPO_ROOT / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
SUCCESSOR_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_29.json"
)
V128_CONTRACT_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_28.json"
)
MATERIALIZATION_SCHEMA_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_29_SUCCESSOR.json"
)
V128_MATERIALIZATION_SCHEMA_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_28_SUCCESSOR.json"
)
GENERATOR = REPO_ROOT / "docs/arrival_history_erratum_1_0_29_20261009/generate_contract_1_0_29.py"
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_ARRIVAL_HISTORY_DECLARATIONS"
LEDGER_PATH = (
    REPO_ROOT / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
)
# The 25 records this erratum declares, in generator order (the task's ruling
# order): the 20 knowledge-projection rows then the 5 replay/RNG twin rows.
ARRIVAL_HISTORY_ERRATA_1_0_29_IDS = (
    [f"HIDDEN_{index:02d}" for index in range(1, 20)]
    + ["HIDDEN_HONEYCARD_SENTINEL"]
    + [
        "REPLAY_CLEAN_PROCESS",
        "REPLAY_DECISION_TAPE",
        "REPLAY_EVENT_TAPE",
        "REPLAY_STATE_HASHES",
        "RNG_RULES_TAPE",
    ]
)
_ENGINE_STEP_BY_POINT = {
    ("beginning", "upkeep"): "UPKEEP",
    ("beginning", "draw"): "DRAW",
    ("precombat_main", "main"): "PRECOMBAT_MAIN",
    ("combat", "declare_attackers"): "DECLARE_ATTACKERS",
    ("combat", "declare_blockers"): "DECLARE_BLOCKERS",
    ("combat", "combat_damage"): "COMBAT_DAMAGE",
    ("postcombat_main", "main"): "POSTCOMBAT_MAIN",
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolver():
    path = REPO_ROOT / "scripts/resolve_pre_freeze_contract.py"
    spec = importlib.util.spec_from_file_location("pre_freeze_resolver_1_0_29", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arrival_using_lane_records() -> dict[str, tuple[str, ...]]:
    """The lane registries themselves, never a hand-written list.

    Every record any of these registries executes goes through the same strict
    arrival (``run_midgame_capability_probe.drive_arrival``), so every one of
    them must declare its arrival history.
    """
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from commander_lab.qualification.current_boundary import (
        knowledge_projection,
        midgame_replay_twin,
        midgame_rows,
    )

    return {
        "midgame_rows.ROWS": tuple(midgame_rows.ROWS),
        "knowledge_projection.ROWS": tuple(knowledge_projection.ROWS),
        "midgame_replay_twin.ROWS": tuple(midgame_replay_twin.ROWS),
    }


def _keep_step(record: dict, seat: str) -> dict | None:
    for step in record.get("decision_script") or ():
        if not isinstance(step, dict) or step.get("decision_family") != "mulligan":
            continue
        if step.get("actor") != seat:
            continue
        selection = step.get("selection") or {}
        if (
            selection.get("selector_kind") == "semantic_action"
            and selection.get("semantic_value") == "keep_opening_hand"
            and selection.get("on_zero_match") == "FAIL_CLOSED"
            and selection.get("on_multiple_match") == "FAIL_CLOSED"
            and selection.get("matches_only_provider_offered_legal_options") is True
        ):
            return step
    return None


def _arrival_pass_through(record: dict) -> dict | None:
    temporal = record["temporal_state"]
    point = (str(temporal["phase"]).lower(), str(temporal["step"]).lower())
    # The checkpoint must be addressable by the arrival transport's own mapping.
    _ENGINE_STEP_BY_POINT[point]
    for step in record.get("decision_script") or ():
        if not isinstance(step, dict) or step.get("decision_family") != "priority_pass_through":
            continue
        if step.get("actor") != "ALL":
            continue
        selection = step.get("selection") or {}
        scope = step.get("scope") or {}
        if (
            scope.get("from") == {"turn": 1, "phase": "beginning"}
            and scope.get("until")
            == {
                "turn": temporal["turn_number"],
                "phase": point[0],
                "step": point[1],
            }
            and selection.get("selector_kind") == "semantic_action"
            and selection.get("semantic_value") == "pass_priority"
            and selection.get("on_zero_match") == "FAIL_CLOSED"
            and selection.get("on_multiple_match") == "FAIL_CLOSED"
        ):
            return step
    return None


def _missing_arrival_history(records: dict[str, dict], fixture_ids) -> list[str]:
    """The fixtures whose record lacks a keep per seat or the scoped pass-through."""
    missing: list[str] = []
    for fixture_id in fixture_ids:
        record = records[fixture_id]
        seats = [str(player["player_id"]) for player in record["players"]]
        if any(_keep_step(record, seat) is None for seat in seats):
            missing.append(fixture_id)
            continue
        if _arrival_pass_through(record) is None:
            missing.append(fixture_id)
    return missing


def test_every_arrival_using_lane_record_declares_its_arrival_history() -> None:
    """#634 / #592: the union of every arrival-using lane registry declares the
    history; the registries themselves are the denominator, not a hand list."""
    lanes = _arrival_using_lane_records()
    all_ids = [fixture for ids in lanes.values() for fixture in ids]
    assert len(all_ids) == len(set(all_ids)) == 99, {k: len(v) for k, v in lanes.items()}
    resolver = _resolver()
    effective = resolver.load_effective_materialization()
    records = {record["fixture_id"]: record for record in effective["records"]}
    assert _missing_arrival_history(records, all_ids) == []

    # The declarations are the 1.0.28 shapes: one keep per seat in record order
    # and exactly one leading pass-through to the record's own checkpoint.
    for fixture_id in all_ids:
        record = records[fixture_id]
        seats = [str(player["player_id"]) for player in record["players"]]
        script = record["decision_script"]
        offset = 1 if script and script[0].get("decision_family") == "starting_player" else 0
        assert [step["decision_family"] for step in script[offset : offset + len(seats)]] == [
            "mulligan"
        ] * len(seats), fixture_id
        assert [step["actor"] for step in script[offset : offset + len(seats)]] == seats, fixture_id
        assert script[offset + len(seats)]["decision_family"] == "priority_pass_through", fixture_id
        assert script[offset + len(seats)]["actor"] == "ALL", fixture_id


def test_red_control_a_missing_keep_or_pass_through_fails_the_checker() -> None:
    """The checker is the acceptance criterion: removing one declaration fails it."""
    lanes = _arrival_using_lane_records()
    all_ids = [fixture for ids in lanes.values() for fixture in ids]
    resolver = _resolver()
    effective = resolver.load_effective_materialization()
    base_records = {record["fixture_id"]: record for record in effective["records"]}

    # A knowledge-projection record's keep.
    mutated = copy.deepcopy(base_records)
    keep = _keep_step(mutated["HIDDEN_01"], "P3")
    assert keep is not None
    mutated["HIDDEN_01"]["decision_script"].remove(keep)
    assert _missing_arrival_history(mutated, all_ids) == ["HIDDEN_01"]

    # A replay/RNG twin record's pass-through.
    mutated = copy.deepcopy(base_records)
    pass_through = _arrival_pass_through(mutated["RNG_RULES_TAPE"])
    assert pass_through is not None
    mutated["RNG_RULES_TAPE"]["decision_script"].remove(pass_through)
    assert _missing_arrival_history(mutated, all_ids) == ["RNG_RULES_TAPE"]


def test_contract_1_0_29_diff_against_1_0_28_is_arrival_history_only() -> None:
    """Only the rule-declared prepends, version fields and accounting changed."""
    contract = _json(SUCCESSOR_PATH)
    predecessor = _json(V128_CONTRACT_PATH)
    resolver = _resolver()
    assert contract["contract_id"] == "commander-lab.full107/1.0.29-successor"
    assert contract["predecessor"]["path"].endswith("FULL107_SUCCESSOR_CONTRACT_v1_0_28.json")
    assert (
        contract["predecessor"]["sha256"]
        == hashlib.sha256(V128_CONTRACT_PATH.read_bytes()).hexdigest()
    )
    assert contract["predecessor"]["record_count"] == len(contract["record_successors"])
    for key in ("rules_authority", "evidence_policy", "bounded_secondary_records"):
        assert contract[key] == predecessor[key], key

    old = {patch["fixture_id"]: patch for patch in predecessor["record_successors"]}
    new = {patch["fixture_id"]: patch for patch in contract["record_successors"]}
    assert set(old) == set(new)
    extended = {fixture_id for fixture_id in old if old[fixture_id] != new[fixture_id]}
    assert extended == set(ARRIVAL_HISTORY_ERRATA_1_0_29_IDS), sorted(extended)
    # Carried, untouched successors are byte for byte their 1.0.28 selves.
    for fixture_id in old:
        if fixture_id not in extended:
            assert new[fixture_id] == old[fixture_id], fixture_id

    base_records = {
        record["fixture_id"]: record
        for record in json.loads(
            (
                REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
            ).read_text()
        )["records"]
    }
    for fixture_id in extended:
        patch = new[fixture_id]
        prior = old[fixture_id]
        effective_1_0_28 = copy.deepcopy(base_records[fixture_id])
        for key, value in prior["replace"].items():
            effective_1_0_28[key] = copy.deepcopy(value)
        effective_1_0_28["knowledge_state"]["channel_policy"] = prior[
            "knowledge_state_channel_policy"
        ]
        prior_script = effective_1_0_28["decision_script"]
        assert set(prior["replace"]) <= set(patch["replace"]), fixture_id
        assert (
            patch["successor_requested_state_digest"] == prior["successor_requested_state_digest"]
        ), fixture_id
        new_script = patch["replace"]["decision_script"]
        if prior_script:
            assert new_script[-len(prior_script) :] == prior_script, fixture_id
        assert patch["superseded_successor_patch"]["contract"] == (
            "commander-lab.full107/1.0.28-successor"
        )
        assert patch["correction_class"] == CORRECTION_CLASS
        effective = resolver.effective_record(fixture_id)
        assert effective["obligation_digest"] == resolver.obligation_digest(effective_1_0_28)
        assert (
            resolver.requested_state_digest(effective) == patch["successor_requested_state_digest"]
        )
        projected = {
            key: effective.get(key) for key in resolver.PROJECTION_KEYS if key in effective
        }
        projected_1_0_28 = {
            key: effective_1_0_28.get(key)
            for key in resolver.PROJECTION_KEYS
            if key in effective_1_0_28
        }
        assert projected == projected_1_0_28, fixture_id


def test_contract_1_0_29_authority_and_ledger_name_the_correction() -> None:
    authority = _json(AUTHORITY_PATH)["full107"]
    # 1.0.30 is the current successor and re-opens every one of these records
    # for the declared passes/mana; the frozen 1.0.29 bytes above keep the
    # 1.0.29 class, and the current authority/ledger name the 1.0.30 one.
    assert authority["successor_contract"].endswith("FULL107_SUCCESSOR_CONTRACT_v1_0_30.json")
    assert authority["effective_materialization_schema"].endswith(
        "SEMANTIC_FIXTURE_SCHEMA_v1_0_30_SUCCESSOR.json"
    )
    assert authority["denominator_count"] == 107
    contract = _json(SUCCESSOR_PATH)
    patch_ids = {
        patch["fixture_id"]
        for patch in contract["record_successors"]
        if patch["correction_class"] == CORRECTION_CLASS
    }
    assert set(ARRIVAL_HISTORY_ERRATA_1_0_29_IDS) <= patch_ids
    assert patch_ids == set(authority["changed_fixture_ids"]) & patch_ids
    for fixture_id in ARRIVAL_HISTORY_ERRATA_1_0_29_IDS:
        assert authority["evidence_survival"][fixture_id] == (
            "REQUALIFICATION_REQUIRED_FIXTURE_DEFECT_CORRECTION_DECLARED_PASSES_AND_MANA"
        )
        (ledger_entry,) = [
            entry for entry in _json(LEDGER_PATH)["records"] if entry["fixture_id"] == fixture_id
        ]
        assert (
            ledger_entry["correction_class"] == "FIXTURE_DEFECT_CORRECTION_DECLARED_PASSES_AND_MANA"
        )
        assert ledger_entry["denominator_effect"] == "NONE"
        assert ledger_entry["successor_contract"].endswith(
            "FULL107_SUCCESSOR_CONTRACT_v1_0_30.json"
        )


def _temp_repo(tmp_path: Path) -> Path:
    authority = _json(AUTHORITY_PATH)
    files = {
        "scripts/resolve_pre_freeze_contract.py": REPO_ROOT
        / "scripts/resolve_pre_freeze_contract.py",
        "qualification/CURRENT_PRE_FREEZE_CONTRACT.json": AUTHORITY_PATH,
        "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_28.json": (
            V128_CONTRACT_PATH
        ),
        "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_28_SUCCESSOR.json": (
            V128_MATERIALIZATION_SCHEMA_PATH
        ),
        "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json": (
            REPO_ROOT / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json"
        ),
        authority["full107"]["historical_base_materialization"]: (
            REPO_ROOT / authority["full107"]["historical_base_materialization"]
        ),
        "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json": (LEDGER_PATH),
    }
    root = tmp_path / "repo"
    for relative, source in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return root


def test_generator_is_deterministic_and_never_mutates_the_checkout(tmp_path: Path) -> None:
    """Evidence (a): the 1.0.29 contract and schema are always regenerated from
    the 1.0.28 bytes; a fresh run against a disposable copy of the inputs
    reproduces the committed bytes and a second run is byte-identical. After
    1.0.30 the historical generator no longer reproduces the current pointer or
    ledger (they name 1.0.30), so only the contract and schema bytes are
    asserted; REPO_ROOT is never mutated."""
    root = _temp_repo(tmp_path)
    targets = {
        "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_29.json": (
            SUCCESSOR_PATH
        ),
        "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_29_SUCCESSOR.json": (
            MATERIALIZATION_SCHEMA_PATH
        ),
    }
    before = {relative: target.read_bytes() for relative, target in targets.items()}
    generated = (
        "qualification/CURRENT_PRE_FREEZE_CONTRACT.json",
        "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json",
    )
    generated_before = {relative: (REPO_ROOT / relative).read_bytes() for relative in generated}
    all_paths = (*targets, *generated)
    subprocess.run(
        [sys.executable, str(GENERATOR), str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    first = {relative: (root / relative).read_bytes() for relative in all_paths}
    subprocess.run(
        [sys.executable, str(GENERATOR), str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    for relative in all_paths:
        assert (root / relative).read_bytes() == first[relative], relative
    for relative, target in targets.items():
        assert first[relative] == before[relative], relative
        assert target.read_bytes() == before[relative], f"REPO_ROOT was mutated: {relative}"
    # The historical generator's tamper-target outputs are still deterministic
    # run to run, even though they no longer name the current contract.
    for relative in generated:
        assert (root / relative).read_bytes() != (REPO_ROOT / relative).read_bytes(), relative
        assert (REPO_ROOT / relative).read_bytes() == generated_before[relative], (
            f"REPO_ROOT was mutated: {relative}"
        )
