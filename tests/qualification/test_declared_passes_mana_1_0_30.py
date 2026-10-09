"""Contract 1.0.30: the declared obligation pass-throughs and mana-payment
declarations erratum (#634 step A, 2026-10-09).

The #634 audit found the credited midgame path answering engine frames for
players without a record declaration: the obligation loop's default pass
(``midgame_rows.py:5188-5201``), the RowSpec ``mana_sources`` pick
(``midgame_rows.py:5255-5264``) and the probe's causal construction passes.
Step A declares every one of those decisions in ``decision_script`` so step B
can refuse anything undeclared; this module is the acceptance criterion.

Evidence asserted here:

* every record any arrival-using lane registry executes -- the midgame RowSpec
  registry, the knowledge-projection registry, the midgame replay-twin
  registry, ``run_midgame_capability_probe.PROBE_ROWS`` and
  ``run_midgame_capability_probe.CAUSAL_ROWS`` -- declares its game-start
  arrival history (1.0.28 shape) AND exactly one obligation
  ``priority_pass_through`` scope with ``precedence: SCRIPTED_STEPS_FIRST``
  (CR 117.3d). Red controls remove one declaration at a time.
* every RowSpec row with a non-empty ``mana_sources`` list has a record
  ``mana_payment`` declaration whose source identities are exactly the
  RowSpec's, bound to the record's own semantic objects (CR 601.2g-h). A red
  control per RowSpec breaks the declaration and requires the checker to fail.
* the 1.0.30 diff against 1.0.29 is limited to ``decision_script`` additions
  plus version/accounting: the prior script is a subsequence of the new one,
  only pre-existing ``mana_payment`` steps may gain the ``sources`` key, and
  every obligation/requested-state digest is unchanged.
* the generator is byte-deterministic and never mutates the checkout.
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
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_30.json"
)
V129_CONTRACT_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_29.json"
)
MATERIALIZATION_SCHEMA_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_30_SUCCESSOR.json"
)
V129_MATERIALIZATION_SCHEMA_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_29_SUCCESSOR.json"
)
GENERATOR = (
    REPO_ROOT / "docs/declared_passes_mana_erratum_1_0_30_20261009/generate_contract_1_0_30.py"
)
CORRECTION_CLASS = "FIXTURE_DEFECT_CORRECTION_DECLARED_PASSES_AND_MANA"
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
_TURN_STEP_ORDER = (
    "UNTAP",
    "UPKEEP",
    "DRAW",
    "PRECOMBAT_MAIN",
    "BEGIN_COMBAT",
    "DECLARE_ATTACKERS",
    "DECLARE_BLOCKERS",
    "FIRST_COMBAT_DAMAGE",
    "COMBAT_DAMAGE",
    "END_COMBAT",
    "POSTCOMBAT_MAIN",
    "END_TURN",
    "CLEANUP",
)
_SCOPE_PHASE_STEPS = {
    "beginning": ("UNTAP", "UPKEEP", "DRAW"),
    "precombat_main": ("PRECOMBAT_MAIN",),
    "combat": (
        "BEGIN_COMBAT",
        "DECLARE_ATTACKERS",
        "DECLARE_BLOCKERS",
        "FIRST_COMBAT_DAMAGE",
        "COMBAT_DAMAGE",
        "END_COMBAT",
    ),
    "postcombat_main": ("POSTCOMBAT_MAIN",),
    "ending": ("END_TURN", "CLEANUP"),
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolver():
    path = REPO_ROOT / "scripts/resolve_pre_freeze_contract.py"
    spec = importlib.util.spec_from_file_location("pre_freeze_resolver_1_0_30", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _probe():
    path = REPO_ROOT / "scripts/run_midgame_capability_probe.py"
    spec = importlib.util.spec_from_file_location("probe_1_0_30", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arrival_using_lane_records() -> dict[str, tuple[str, ...]]:
    """The lane registries themselves, never a hand-written list.

    Every record any of these registries executes goes through the same strict
    arrival (``run_midgame_capability_probe.drive_arrival``), so every one of
    them must declare its arrival history and its obligation pass-through.
    """
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from commander_lab.qualification.current_boundary import (
        knowledge_projection,
        midgame_replay_twin,
        midgame_rows,
    )

    probe = _probe()
    return {
        "midgame_rows.ROWS": tuple(midgame_rows.ROWS),
        "knowledge_projection.ROWS": tuple(knowledge_projection.ROWS),
        "midgame_replay_twin.ROWS": tuple(midgame_replay_twin.ROWS),
        "PROBE_ROWS": tuple(probe.PROBE_ROWS),
        "CAUSAL_ROWS": tuple(probe.CAUSAL_ROWS),
    }


def _row_spec_rows_with_mana() -> dict[str, tuple[str, ...]]:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from commander_lab.qualification.current_boundary import midgame_rows

    return {
        fixture_id: tuple(spec.mana_sources)
        for fixture_id, spec in midgame_rows.ROWS.items()
        if spec.mana_sources
    }


def _causal_fixture_ids() -> set[str]:
    """The causal-stack and elimination rows (ruling 3), from the registry."""
    probe = _probe()
    return {
        fixture_id
        for fixture_id, entry in probe.CAUSAL_ROWS.items()
        if str(entry.get("entry_mode")) != "placement"
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
    _ENGINE_STEP_BY_POINT[point]
    for step in record.get("decision_script") or ():
        if not isinstance(step, dict) or step.get("decision_family") != "priority_pass_through":
            continue
        if step.get("actor") != "ALL" or step.get("precedence") is not None:
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


def _scope_position(bound: dict, *, last: bool) -> tuple[int, int] | None:
    turn = bound.get("turn")
    if not isinstance(turn, int) or isinstance(turn, bool):
        return None
    phase = str(bound.get("phase") or "").strip().lower()
    step = str(bound.get("step") or "").strip().lower()
    if step:
        engine_step = _ENGINE_STEP_BY_POINT.get((phase, step))
        if engine_step is None:
            return None
        return turn, _TURN_STEP_ORDER.index(engine_step)
    phase_steps = _SCOPE_PHASE_STEPS.get(phase)
    if not phase_steps:
        return None
    return turn, _TURN_STEP_ORDER.index(phase_steps[-1] if last else phase_steps[0])


def _obligation_pass_through(record: dict, causal: bool) -> dict | None:
    temporal = record["temporal_state"]
    point = (str(temporal["phase"]).lower(), str(temporal["step"]).lower())
    expected_from = (
        {"turn": 1, "phase": "beginning"}
        if causal
        else {"turn": temporal["turn_number"], "phase": point[0], "step": point[1]}
    )
    for step in record.get("decision_script") or ():
        if not isinstance(step, dict) or step.get("decision_family") != "priority_pass_through":
            continue
        if step.get("actor") != "ALL" or step.get("precedence") != "SCRIPTED_STEPS_FIRST":
            continue
        selection = step.get("selection") or {}
        scope = step.get("scope") or {}
        if (
            scope.get("from") == expected_from
            and scope.get("until") == {"event": "OBLIGATION_COMPLETE"}
            and selection.get("selector_kind") == "semantic_action"
            and selection.get("semantic_value") == "pass_priority"
            and selection.get("on_zero_match") == "FAIL_CLOSED"
            and selection.get("on_multiple_match") == "FAIL_CLOSED"
            and selection.get("matches_only_provider_offered_legal_options") is True
        ):
            start = _scope_position(scope["from"], last=False)
            if start is None:
                return None
            return step
    return None


def _missing_declarations(records: dict[str, dict], fixture_ids, causal: set[str]) -> list[str]:
    missing: list[str] = []
    for fixture_id in fixture_ids:
        record = records[fixture_id]
        seats = [str(player["player_id"]) for player in record["players"]]
        if any(_keep_step(record, seat) is None for seat in seats):
            missing.append(fixture_id)
            continue
        if _arrival_pass_through(record) is None:
            missing.append(fixture_id)
            continue
        if _obligation_pass_through(record, fixture_id in causal) is None:
            missing.append(fixture_id)
    return missing


def _declared_mana_sources(record: dict) -> list[str]:
    declared: list[str] = []
    for step in record.get("decision_script") or ():
        if not isinstance(step, dict) or step.get("decision_family") != "mana_payment":
            continue
        selection = step.get("selection") or {}
        value = selection.get("semantic_value")
        if selection.get("selector_kind") != "mana_payment" or not isinstance(value, dict):
            continue
        declared.extend(str(source) for source in value.get("sources") or ())
    return declared


def _mana_declaration_problems(
    records: dict[str, dict], rows: dict[str, tuple[str, ...]]
) -> list[str]:
    problems: list[str] = []
    for fixture_id, mana_sources in sorted(rows.items()):
        record = records[fixture_id]
        declared = _declared_mana_sources(record)
        if declared != list(mana_sources):
            problems.append(fixture_id)
            continue
        object_ids = {
            str(obj.get("semantic_id"))
            for obj in record.get("semantic_objects") or ()
            if isinstance(obj, dict)
        }
        if any(source not in object_ids for source in declared):
            problems.append(fixture_id)
    return problems


def _effective_records() -> dict[str, dict]:
    resolver = _resolver()
    effective = resolver.load_effective_materialization()
    return {record["fixture_id"]: record for record in effective["records"]}


def test_every_arrival_using_lane_record_declares_history_and_obligation_passes() -> None:
    """#634 rulings 1, 3 and 4: the union of every arrival-using lane registry
    declares the arrival history and the obligation pass-through."""
    lanes = _arrival_using_lane_records()
    all_ids = list(dict.fromkeys(fixture for ids in lanes.values() for fixture in ids))
    assert sum(len(ids) for ids in lanes.values()) == 150
    assert len(all_ids) == 105, {k: len(v) for k, v in lanes.items()}
    causal = _causal_fixture_ids()
    records = _effective_records()
    assert _missing_declarations(records, all_ids, causal) == []

    # The obligation declaration is appended after the record's own steps, so
    # the arrival prefix the 1.0.28/1.0.29 tests assert is untouched.
    for fixture_id in all_ids:
        record = records[fixture_id]
        seats = [str(player["player_id"]) for player in record["players"]]
        script = record["decision_script"]
        offset = 1 if script and script[0].get("decision_family") == "starting_player" else 0
        assert [step["decision_family"] for step in script[offset : offset + len(seats)]] == [
            "mulligan"
        ] * len(seats), fixture_id
        assert script[offset + len(seats)]["decision_family"] == "priority_pass_through", fixture_id
        assert script[-1]["causal_step_id"].startswith("priority-pass-obligation-"), fixture_id
        assert script[-1]["precedence"] == "SCRIPTED_STEPS_FIRST", fixture_id


def test_red_control_a_missing_arrival_or_obligation_declaration_fails_the_checker() -> None:
    lanes = _arrival_using_lane_records()
    all_ids = list(dict.fromkeys(fixture for ids in lanes.values() for fixture in ids))
    causal = _causal_fixture_ids()
    base_records = _effective_records()

    # A CARD-only record's keep (the #642 review P2-2 gap).
    mutated = copy.deepcopy(base_records)
    keep = _keep_step(mutated["CARD_07"], "P4")
    assert keep is not None
    mutated["CARD_07"]["decision_script"].remove(keep)
    assert _missing_declarations(mutated, all_ids, causal) == ["CARD_07"]

    # A CARD-only record's arrival pass-through.
    mutated = copy.deepcopy(base_records)
    arrival = _arrival_pass_through(mutated["CARD_13"])
    assert arrival is not None
    mutated["CARD_13"]["decision_script"].remove(arrival)
    assert _missing_declarations(mutated, all_ids, causal) == ["CARD_13"]

    # MICRO_PREVENTION's obligation pass-through covers its checkpoint-step
    # priority (#642 review P2-1): removing it fails the checker.
    mutated = copy.deepcopy(base_records)
    obligation = _obligation_pass_through(mutated["MICRO_PREVENTION"], False)
    assert obligation is not None
    assert obligation["scope"]["from"] == {
        "turn": 1,
        "phase": "combat",
        "step": "declare_attackers",
    }
    mutated["MICRO_PREVENTION"]["decision_script"].remove(obligation)
    assert _missing_declarations(mutated, all_ids, causal) == ["MICRO_PREVENTION"]

    # An elimination row's scope starts at the causal preparation start.
    mutated = copy.deepcopy(base_records)
    obligation = _obligation_pass_through(mutated["WS05-MP-ELIM-5"], True)
    assert obligation is not None
    assert obligation["scope"]["from"] == {"turn": 1, "phase": "beginning"}
    mutated["WS05-MP-ELIM-5"]["decision_script"].remove(obligation)
    assert _missing_declarations(mutated, all_ids, causal) == ["WS05-MP-ELIM-5"]

    # A non-causal record's scope starts at its checkpoint.
    mutated = copy.deepcopy(base_records)
    obligation = _obligation_pass_through(mutated["MICRO_COMBAT"], False)
    assert obligation is not None
    assert obligation["scope"]["from"] == {"turn": 1, "phase": "precombat_main", "step": "main"}
    mutated["MICRO_COMBAT"]["decision_script"].remove(obligation)
    assert _missing_declarations(mutated, all_ids, causal) == ["MICRO_COMBAT"]


def test_every_row_spec_with_mana_sources_has_a_record_bound_declaration() -> None:
    """#634 ruling 2: every RowSpec mana user's record declares exactly the
    RowSpec's sources, bound to the record's own semantic object identities."""
    rows = _row_spec_rows_with_mana()
    records = _effective_records()
    assert len(rows) == 33
    assert _mana_declaration_problems(records, rows) == []
    # The 1.0.29 audit's credited set is inside the patched set and now declares
    # its payment in decision_script.
    for fixture_id in (
        "MICRO_CONTROL",
        "MICRO_COSTS",
        "MICRO_MODES",
        "MICRO_TRIGGERS",
        "PILOT_ANNOUNCE_X",
        "PILOT_CHOOSE_MODE",
        "WS05-CMD-DMG-CONTROL",
        "WS05-CMD-PARTNER-TAX",
        "WS05-CMD-TAX-2",
        "WS05-CMD-TAX-4",
        "WS05-MP-TRIG-3",
        "WS05-MP-TRIG-5",
    ):
        assert _declared_mana_sources(records[fixture_id]) == list(rows[fixture_id]), fixture_id


def test_red_control_each_rows_mana_declaration_is_required() -> None:
    """For every RowSpec mana user, breaking its record declaration fails the
    checker: the RowSpec registry is not authority."""
    rows = _row_spec_rows_with_mana()
    base_records = _effective_records()
    assert _mana_declaration_problems(base_records, rows) == []
    for fixture_id in rows:
        mutated = copy.deepcopy(base_records)
        broken = False
        for step in mutated[fixture_id]["decision_script"]:
            if not isinstance(step, dict) or step.get("decision_family") != "mana_payment":
                continue
            value = step["selection"].get("semantic_value")
            if isinstance(value, dict) and value.get("sources"):
                del value["sources"]
                broken = True
        # The two completion records had a bare mana step; some other records
        # may declare a payment the RowSpec does not name, so remove them too.
        if not broken:
            for step in list(mutated[fixture_id]["decision_script"]):
                if (
                    isinstance(step, dict)
                    and step.get("decision_family") == "mana_payment"
                    and str(step.get("causal_step_id") or "").startswith("mana-payment-")
                ):
                    mutated[fixture_id]["decision_script"].remove(step)
                    broken = True
        assert broken, fixture_id
        assert _mana_declaration_problems(mutated, rows) == [fixture_id], fixture_id


def test_contract_1_0_30_diff_against_1_0_29_is_declarations_only() -> None:
    """Only the ruled ``decision_script`` additions, version fields and
    accounting changed; the prior script is carried byte for byte in order."""
    contract = _json(SUCCESSOR_PATH)
    predecessor = _json(V129_CONTRACT_PATH)
    resolver = _resolver()
    assert contract["contract_id"] == "commander-lab.full107/1.0.30-successor"
    assert contract["predecessor"]["path"].endswith("FULL107_SUCCESSOR_CONTRACT_v1_0_29.json")
    assert (
        contract["predecessor"]["sha256"]
        == hashlib.sha256(V129_CONTRACT_PATH.read_bytes()).hexdigest()
    )
    assert contract["predecessor"]["record_count"] == len(contract["record_successors"])
    for key in ("rules_authority", "evidence_policy", "bounded_secondary_records"):
        assert contract[key] == predecessor[key], key

    old = {patch["fixture_id"]: patch for patch in predecessor["record_successors"]}
    new = {patch["fixture_id"]: patch for patch in contract["record_successors"]}
    assert set(old) <= set(new)
    added = set(new) - set(old)
    assert added == {"CARD_20"}
    extended = {fixture_id for fixture_id in old if old[fixture_id] != new[fixture_id]} | added
    assert extended == {
        patch["fixture_id"]
        for patch in contract["record_successors"]
        if patch["correction_class"] == CORRECTION_CLASS
    }
    # Carried, untouched successors are byte for byte their 1.0.29 selves.
    for fixture_id in old:
        if fixture_id not in extended:
            assert new[fixture_id] == old[fixture_id], fixture_id

    records = _effective_records()
    for fixture_id in extended:
        patch = new[fixture_id]
        prior = old.get(fixture_id)
        effective_1_0_29 = _effective_from_patch(
            resolver, prior if prior is not None else {"fixture_id": fixture_id, "replace": {}}
        )
        prior_script = effective_1_0_29["decision_script"]
        if prior is not None:
            assert set(prior["replace"]) <= set(patch["replace"]), fixture_id
            assert (
                patch["successor_requested_state_digest"]
                == prior["successor_requested_state_digest"]
            ), fixture_id
            assert patch["superseded_successor_patch"]["contract"] == (
                "commander-lab.full107/1.0.29-successor"
            )
        new_steps = patch["replace"]["decision_script"]
        prior_steps_normalized = [_without_mana_sources(step) for step in prior_script]
        carried = _carried_prior_script(prior_script, new_steps)
        # The six causal-only CARD records gain their 1.0.28-shape arrival
        # history in this erratum (their earlier patches never declared it), so
        # a leading declaration that the prior script does not already carry is
        # this erratum's addition, not a lost predecessor step.
        while (
            carried
            and carried[0].get("decision_family") in ("mulligan", "priority_pass_through")
            and carried[0] not in prior_script
        ):
            carried = carried[1:]
        assert carried == prior_steps_normalized, fixture_id
        assert patch["correction_class"] == CORRECTION_CLASS
        effective = records[fixture_id]
        # The stored digest field is refreshed at load; compare the computed
        # obligation the record projects, field for field.
        assert resolver.obligation_digest(effective) == resolver.obligation_digest(effective_1_0_29)
        assert (
            resolver.requested_state_digest(effective) == patch["successor_requested_state_digest"]
        )
        assert resolver.requested_state_digest(effective) == resolver.requested_state_digest(
            effective_1_0_29
        )
        projected = {
            key: effective.get(key) for key in resolver.PROJECTION_KEYS if key in effective
        }
        projected_prior = {
            key: effective_1_0_29.get(key)
            for key in resolver.PROJECTION_KEYS
            if key in effective_1_0_29
        }
        assert projected == projected_prior, fixture_id


def _effective_from_patch(resolver, patch: dict) -> dict:
    """The record this frozen patch produces: base + the earlier patches + it."""
    authority = _json(AUTHORITY_PATH)
    base = {
        record["fixture_id"]: record
        for record in _json(REPO_ROOT / authority["full107"]["historical_base_materialization"])[
            "records"
        ]
    }
    record = copy.deepcopy(base[patch["fixture_id"]])
    chain: list[dict] = []
    current = patch
    while current is not None:
        chain.append(current)
        current = current.get("superseded_successor_patch")
    # The chain runs newest to oldest; the frozen patch's own replace already
    # carries every earlier replace forward, so applying it to the base is
    # exactly the record it materializes.
    for key, value in patch["replace"].items():
        record[key] = copy.deepcopy(value)
    if "knowledge_state_channel_policy" in patch:
        record["knowledge_state"]["channel_policy"] = patch["knowledge_state_channel_policy"]
    return record


def _carried_prior_script(prior_script: list[dict], new_steps: list[dict]) -> list[dict]:
    """The prior steps carried forward in order, ignoring the 1.0.30 additions.

    Inserted declaration steps are dropped; a pre-existing ``mana_payment`` step
    may gain the ruled ``sources`` key, so both sides are compared without it
    (the added declarations themselves are asserted by the dedicated tests).
    """
    carried: list[dict] = []
    for step in new_steps:
        causal_step_id = str(step.get("causal_step_id") or "")
        if causal_step_id.startswith("priority-pass-obligation-"):
            continue
        if causal_step_id.startswith("mana-payment-"):
            continue
        if causal_step_id.startswith("declare-attackers-") and step not in prior_script:
            # ruling 5 (step A2): the knowledge window's declared empty attack
            # set, inserted before the obligation pass-through. A record whose
            # 1.0.29 script already carried its own declare_attackers step
            # (NEGATIVE_PARENT_CLASS_FALLBACK) keeps that step carried.
            continue
        carried.append(_without_mana_sources(step))
    return carried


def _without_mana_sources(step: dict) -> dict:
    normalized = copy.deepcopy(step)
    if normalized.get("decision_family") == "mana_payment":
        semantic_value = (normalized.get("selection") or {}).get("semantic_value")
        if isinstance(semantic_value, dict):
            semantic_value.pop("sources", None)
    return normalized


def test_contract_1_0_30_authority_and_ledger_name_the_correction() -> None:
    authority = _json(AUTHORITY_PATH)["full107"]
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
    assert set(_arrival_using_lane_records()["midgame_rows.ROWS"]) <= patch_ids
    assert patch_ids <= set(authority["changed_fixture_ids"])
    for fixture_id in (
        "MICRO_CONTROL",
        "MICRO_PREVENTION",
        "CARD_07",
        "WS05-MP-ELIM-5",
        "RNG_RULES_TAPE",
    ):
        assert authority["evidence_survival"][fixture_id] == (
            "REQUALIFICATION_REQUIRED_" + CORRECTION_CLASS
        )
        (ledger_entry,) = [
            entry for entry in _json(LEDGER_PATH)["records"] if entry["fixture_id"] == fixture_id
        ]
        assert ledger_entry["correction_class"] == CORRECTION_CLASS
        assert ledger_entry["denominator_effect"] == "NONE"
        assert ledger_entry["successor_contract"].endswith(
            "FULL107_SUCCESSOR_CONTRACT_v1_0_30.json"
        )
    assert authority["denominator_count"] == 107


def test_red_control_the_generator_refuses_a_missing_record_object(tmp_path: Path) -> None:
    """A RowSpec source with no record object is refused, never invented."""
    root = _temp_repo(tmp_path)
    authority = _json(AUTHORITY_PATH)
    base_path = root / authority["full107"]["historical_base_materialization"]
    bundle = json.loads(base_path.read_text(encoding="utf-8"))
    record = next(item for item in bundle["records"] if item["fixture_id"] == "MICRO_CONTROL")
    record["semantic_objects"] = [
        obj
        for obj in record["semantic_objects"]
        if obj.get("semantic_id") != "obj:control-island-0"
    ]
    base_path.write_text(json.dumps(bundle, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    # A later errata patch may carry the effective semantic_objects forward, so
    # the same object is removed there too: the generator must then refuse.
    predecessor_path = (
        root / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_29.json"
    )
    predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
    patch = next(
        item for item in predecessor["record_successors"] if item["fixture_id"] == "MICRO_CONTROL"
    )
    if "semantic_objects" in patch["replace"]:
        patch["replace"]["semantic_objects"] = [
            obj
            for obj in patch["replace"]["semantic_objects"]
            if obj.get("semantic_id") != "obj:control-island-0"
        ]
    predecessor_path.write_text(
        json.dumps(predecessor, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, str(GENERATOR), str(root)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "obj:control-island-0" in (result.stderr + result.stdout)


def _temp_repo(tmp_path: Path) -> Path:
    authority = _json(AUTHORITY_PATH)
    files = {
        "scripts/resolve_pre_freeze_contract.py": REPO_ROOT
        / "scripts/resolve_pre_freeze_contract.py",
        "qualification/CURRENT_PRE_FREEZE_CONTRACT.json": AUTHORITY_PATH,
        "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_29.json": (
            V129_CONTRACT_PATH
        ),
        "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_29_SUCCESSOR.json": (
            V129_MATERIALIZATION_SCHEMA_PATH
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
    root = _temp_repo(tmp_path)
    targets = (
        "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_30.json",
        "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_30_SUCCESSOR.json",
        "qualification/CURRENT_PRE_FREEZE_CONTRACT.json",
        "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json",
    )
    before = {relative: (REPO_ROOT / relative).read_bytes() for relative in targets}
    subprocess.run(
        [sys.executable, str(GENERATOR), str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    first = {relative: (root / relative).read_bytes() for relative in targets}
    for relative in targets:
        assert first[relative] == before[relative], relative
    subprocess.run(
        [sys.executable, str(GENERATOR), str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    for relative in targets:
        assert (root / relative).read_bytes() == first[relative], relative
    for relative in targets:
        assert (REPO_ROOT / relative).read_bytes() == before[relative], (
            f"REPO_ROOT was mutated: {relative}"
        )
