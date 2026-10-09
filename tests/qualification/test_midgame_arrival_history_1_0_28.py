"""Contract 1.0.28: the midgame arrival pre-checkpoint history declarations
erratum (#634 Coordinator ruling, 2026-10-09; refs #592, #626).

Every record the midgame lane executes (``midgame_rows.ROWS``) must declare its
game-start arrival history in ``decision_script``: one pregame keep per seat
present in the record (CR 103.5) and a priority pass-through scope (actor ALL)
from game start to the record's own checkpoint, exclusive (CR 117.3d). The
checker below is the acceptance criterion; the red control removes one declared
keep and requires the checker to fail.
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
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_28.json"
)
V127_CONTRACT_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_27.json"
)
MATERIALIZATION_SCHEMA_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_28_SUCCESSOR.json"
)
GENERATOR = REPO_ROOT / "docs/arrival_history_erratum_1_0_28_20261009/generate_contract_1_0_28.py"
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_ARRIVAL_HISTORY_DECLARATIONS"
LEDGER_PATH = (
    REPO_ROOT / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
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
    spec = importlib.util.spec_from_file_location("pre_freeze_resolver_1_0_28", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _midgame_rows():
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from commander_lab.qualification.current_boundary import midgame_rows

    return midgame_rows


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


def test_every_midgame_row_declares_its_arrival_history() -> None:
    """#634: every RowSpec fixture declares a keep per seat and the pass-through."""
    rows = _midgame_rows()
    resolver = _resolver()
    effective = resolver.load_effective_materialization()
    records = {record["fixture_id"]: record for record in effective["records"]}
    assert _missing_arrival_history(records, rows.ROWS) == []

    # The declarations are the 1.0.28 shapes: one keep per seat in record order
    # and exactly one leading pass-through to the record's own checkpoint.
    for fixture_id in rows.ROWS:
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
    rows = _midgame_rows()
    resolver = _resolver()
    effective = resolver.load_effective_materialization()
    base_records = {record["fixture_id"]: record for record in effective["records"]}

    mutated = copy.deepcopy(base_records)
    keep = _keep_step(mutated["MICRO_COMBAT"], "P3")
    assert keep is not None
    mutated["MICRO_COMBAT"]["decision_script"].remove(keep)
    assert _missing_arrival_history(mutated, rows.ROWS) == ["MICRO_COMBAT"]

    mutated = copy.deepcopy(base_records)
    pass_through = _arrival_pass_through(mutated["MICRO_STACK"])
    assert pass_through is not None
    mutated["MICRO_STACK"]["decision_script"].remove(pass_through)
    assert _missing_arrival_history(mutated, rows.ROWS) == ["MICRO_STACK"]


def test_contract_1_0_28_diff_against_1_0_27_is_arrival_history_only() -> None:
    """Only the rule-declared prepends, version fields and accounting changed."""
    contract = _json(SUCCESSOR_PATH)
    predecessor = _json(V127_CONTRACT_PATH)
    resolver = _resolver()
    assert contract["contract_id"] == "commander-lab.full107/1.0.28-successor"
    assert contract["predecessor"]["path"].endswith("FULL107_SUCCESSOR_CONTRACT_v1_0_27.json")
    assert (
        contract["predecessor"]["sha256"]
        == hashlib.sha256(V127_CONTRACT_PATH.read_bytes()).hexdigest()
    )
    assert contract["predecessor"]["record_count"] == len(contract["record_successors"])
    # Everything but the version/accounting/note/predecessor is carried byte for
    # byte; the bounded-secondary section is untouched.
    for key in ("rules_authority", "evidence_policy", "bounded_secondary_records"):
        assert contract[key] == predecessor[key], key
    assert contract["schema_version"] == predecessor["schema_version"]
    assert contract["bounded_secondary_records"] == predecessor["bounded_secondary_records"]

    old = {patch["fixture_id"]: patch for patch in predecessor["record_successors"]}
    new = {patch["fixture_id"]: patch for patch in contract["record_successors"]}
    assert set(old) <= set(new)
    new_entries = set(new) - set(old)
    patch_ids = {
        fixture_id
        for fixture_id, patch in new.items()
        if patch["correction_class"] == CORRECTION_CLASS
    }
    extended = {fixture_id for fixture_id in old if old[fixture_id] != new[fixture_id]}
    changed = new_entries | extended
    assert changed == patch_ids
    # Carried, untouched successors are byte for byte their 1.0.27 selves.
    for fixture_id in old:
        if fixture_id not in extended:
            assert new[fixture_id] == old[fixture_id], fixture_id
    assert new_entries

    base_records = {
        record["fixture_id"]: record
        for record in json.loads(
            (
                REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
            ).read_text()
        )["records"]
    }
    # Every changed record: the prior replace is a subset, the prior script is
    # carried byte for byte after the inserted arrival-history prefix, and the
    # requested-state and obligation digests are unchanged.
    for fixture_id in changed:
        patch = new[fixture_id]
        prior = old.get(fixture_id)
        # The 1.0.27 effective record: the base overlaid with the prior patch
        # (a record's script may come from the base, not from the patch).
        effective_1_0_27 = copy.deepcopy(base_records[fixture_id])
        if prior is not None:
            for key, value in prior["replace"].items():
                effective_1_0_27[key] = copy.deepcopy(value)
            effective_1_0_27["knowledge_state"]["channel_policy"] = prior[
                "knowledge_state_channel_policy"
            ]
        prior_script = effective_1_0_27["decision_script"]
        if prior is not None:
            assert set(prior["replace"]) <= set(patch["replace"]), fixture_id
            assert (
                patch["successor_requested_state_digest"]
                == prior["successor_requested_state_digest"]
            ), fixture_id
            prior_prefix_end = 0
            while prior_prefix_end < len(prior_script) and prior_script[prior_prefix_end].get(
                "decision_family"
            ) in ("mulligan", "priority_pass_through"):
                prior_prefix_end += 1
            prior_tail = prior_script[prior_prefix_end:]
            new_script = patch["replace"]["decision_script"]
            if prior_tail:
                assert new_script[-len(prior_tail) :] == prior_tail
            assert patch["superseded_successor_patch"]["contract"] == (
                "commander-lab.full107/1.0.27-successor"
            )
        effective_current = resolver.effective_record(fixture_id)
        assert effective_current["obligation_digest"] == resolver.obligation_digest(
            effective_1_0_27
        )
        assert (
            resolver.requested_state_digest(effective_current)
            == (patch["successor_requested_state_digest"])
        )
        projected = {
            key: effective_current.get(key)
            for key in resolver.PROJECTION_KEYS
            if key in effective_current
        }
        projected_1_0_27 = {
            key: effective_1_0_27.get(key)
            for key in resolver.PROJECTION_KEYS
            if key in effective_1_0_27
        }
        assert projected == projected_1_0_27, fixture_id
        # The historical 1.0.28 effective record, rebuilt from the frozen bytes:
        # later errata (1.0.29, 1.0.30) re-open some of these records, so the
        # arrival-prefix diff must be read against the 1.0.28 patch itself.
        effective = copy.deepcopy(base_records[fixture_id])
        if prior is not None:
            for key, value in prior["replace"].items():
                effective[key] = copy.deepcopy(value)
        for key, value in patch["replace"].items():
            effective[key] = copy.deepcopy(value)
        effective["knowledge_state"]["channel_policy"] = patch["knowledge_state_channel_policy"]
        # The arrival prefix is exactly the record's seats' keeps then one
        # ALL-actor pass-through, and nothing else was inserted.
        seats = [str(player["player_id"]) for player in effective["players"]]
        script = effective["decision_script"]
        offset = 1 if script and script[0].get("decision_family") == "starting_player" else 0
        assert [step["decision_family"] for step in script[offset : offset + len(seats)]] == [
            "mulligan"
        ] * len(seats), fixture_id
        assert script[offset + len(seats)]["decision_family"] == "priority_pass_through", fixture_id
        assert _arrival_pass_through(effective) is not None, fixture_id
        assert all(_keep_step(effective, seat) is not None for seat in seats)
        tail = [
            step
            for step in script[offset + len(seats) + 1 :]
            if step["decision_family"] not in ("mulligan", "priority_pass_through")
        ]
        prior_tail = [
            step
            for step in prior_script
            if step.get("decision_family") not in ("mulligan", "priority_pass_through")
        ]
        assert tail == prior_tail, fixture_id


def test_contract_1_0_28_authority_and_ledger_name_the_correction() -> None:
    """Historical 1.0.28 test: the 1.0.28 bytes and its ledger entries.

    The current pointer now names 1.0.29 (asserted by
    ``test_midgame_arrival_history_1_0_29.py``); the 25 records 1.0.29 re-opens
    name the 1.0.29 successor in the ledger, so this historical assertion holds
    for the class and the denominator effect of every 1.0.28 entry.
    """
    contract = _json(SUCCESSOR_PATH)
    assert contract["contract_id"] == "commander-lab.full107/1.0.28-successor"
    patch_ids = {
        patch["fixture_id"]
        for patch in contract["record_successors"]
        if patch["correction_class"] == CORRECTION_CLASS
    }
    authority = _json(AUTHORITY_PATH)["full107"]
    assert authority["denominator_count"] == 107
    assert set(authority["changed_fixture_ids"]) & patch_ids == patch_ids
    for fixture_id in patch_ids:
        assert authority["evidence_survival"][fixture_id].startswith("REQUALIFICATION_REQUIRED")
        (ledger_entry,) = [
            entry for entry in _json(LEDGER_PATH)["records"] if entry["fixture_id"] == fixture_id
        ]
        # 1.0.29 / 1.0.30 re-open these records again, so the current ledger
        # entry carries the latest class and contract; the frozen 1.0.28 bytes
        # above keep the 1.0.28 class for every patch id.
        assert ledger_entry["correction_class"] in {
            CORRECTION_CLASS,
            "FIXTURE_DEFECT_CORRECTION_ARRIVAL_HISTORY_DECLARATIONS",
            "FIXTURE_DEFECT_CORRECTION_DECLARED_PASSES_AND_MANA",
        }
        assert ledger_entry["denominator_effect"] == "NONE"
        assert ledger_entry["successor_contract"].endswith(
            (
                "FULL107_SUCCESSOR_CONTRACT_v1_0_28.json",
                "FULL107_SUCCESSOR_CONTRACT_v1_0_29.json",
                "FULL107_SUCCESSOR_CONTRACT_v1_0_30.json",
            )
        )


def _temp_repo(tmp_path: Path) -> Path:
    authority = _json(AUTHORITY_PATH)
    files = {
        "scripts/resolve_pre_freeze_contract.py": REPO_ROOT
        / "scripts/resolve_pre_freeze_contract.py",
        "qualification/CURRENT_PRE_FREEZE_CONTRACT.json": AUTHORITY_PATH,
        "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_27.json": (
            V127_CONTRACT_PATH
        ),
        "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_27_SUCCESSOR.json": (
            REPO_ROOT
            / "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_27_SUCCESSOR.json"
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
    """Evidence (a): the 1.0.28 contract and schema are always regenerated from
    the 1.0.27 bytes; a fresh run against a disposable copy of the inputs
    reproduces the committed bytes and a second run is byte-identical. After
    1.0.29 the historical generator no longer reproduces the current pointer or
    ledger (they name 1.0.29), so only the contract and schema bytes are
    asserted; REPO_ROOT is never mutated."""
    root = _temp_repo(tmp_path)
    targets = {
        "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_28.json": (
            SUCCESSOR_PATH
        ),
        "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_28_SUCCESSOR.json": (
            MATERIALIZATION_SCHEMA_PATH
        ),
    }
    before = {relative: target.read_bytes() for relative, target in targets.items()}
    for _ in range(2):
        subprocess.run(
            [sys.executable, str(GENERATOR), str(root)],
            check=True,
            capture_output=True,
            text=True,
        )
    first = {relative: (root / relative).read_bytes() for relative in targets}
    for relative, target in targets.items():
        assert first[relative] == before[relative], relative
        assert target.read_bytes() == before[relative], f"REPO_ROOT was mutated: {relative}"
