"""Contract 1.0.31: the actual-card campaign's arrival histories and the
campaign/replay-twin mana declarations (#634).

* the generator is deterministic and never mutates the checkout;
* the 1.0.31 diff against 1.0.30 is ``decision_script`` additions only, on
  exactly the 29 named records: every 1.0.30 step is carried in order, and
  the added steps are keeps, pass-throughs and mana payments;
* every added payment is bound to the record's own declared sources;
* the measured placements hold: the payment precedes the steps the engine
  answers after it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE = REPO_ROOT / "qualification/pre-freeze-successor"
AUTHORITY_PATH = REPO_ROOT / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
CONTRACT = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_31.json"
SCHEMA = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_31_SUCCESSOR.json"
PREDECESSOR = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_30.json"
PREDECESSOR_SCHEMA = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_30_SUCCESSOR.json"
LEDGER_PATH = (
    REPO_ROOT / "docs/final_prefreeze_evidence_closure_20261001/FIXTURE_ERRATA_LEDGER.json"
)
GENERATOR = (
    REPO_ROOT / "docs/campaign_replay_mana_erratum_1_0_31_20261009/generate_contract_1_0_31.py"
)
ADDED_FAMILIES = {"mulligan", "priority_pass_through", "mana_payment"}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _patches(path: Path) -> dict[str, dict]:
    return {patch["fixture_id"]: patch for patch in _json(path)["record_successors"]}


def _changed() -> set[str]:
    old, new = _patches(PREDECESSOR), _patches(CONTRACT)
    return {
        fixture_id
        for fixture_id, patch in new.items()
        if (old.get(fixture_id) or {}).get("replace", {}).get("decision_script")
        != patch["replace"].get("decision_script")
    }


def test_the_current_authority_names_1_0_31() -> None:
    authority = _json(AUTHORITY_PATH)["full107"]
    assert authority["successor_contract"].endswith(CONTRACT.name)
    assert authority["effective_materialization_schema"].endswith(SCHEMA.name)
    assert authority["denominator_count"] == 107
    assert _json(CONTRACT)["contract_id"] == "commander-lab.full107/1.0.31-successor"


def test_the_diff_is_declarations_only_on_the_named_records() -> None:
    changed = _changed()
    assert len(changed) == 29
    assert {f"CARD_{index:02d}" for index in (1, 3, 8, 14, 23, 27, 29)} <= changed
    assert {"RNG_RULES_TAPE", "REPLAY_CLEAN_PROCESS"} <= changed
    old, new = _patches(PREDECESSOR), _patches(CONTRACT)
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    for fixture_id in changed:
        prior = (old.get(fixture_id) or {}).get("replace", {}).get("decision_script")
        if prior is None:
            prior = base[fixture_id].get("decision_script") or []
        script = new[fixture_id]["replace"]["decision_script"]
        # Every predecessor step is carried in order; only declarations are added.
        cursor = iter(script)
        assert all(any(step == kept for kept in cursor) for step in prior), fixture_id
        added = [step for step in script if step not in prior]
        assert added, fixture_id
        assert {step["decision_family"] for step in added} <= ADDED_FAMILIES, fixture_id
        assert new[fixture_id]["successor_requested_state_digest"] == (
            (old.get(fixture_id) or {}).get("successor_requested_state_digest")
            or base[fixture_id]["requested_state_digest"]
        ), fixture_id


def test_every_added_payment_is_bound_to_the_records_own_sources() -> None:
    materialization = load_effective_materialization(REPO_ROOT)
    for fixture_id in _changed():
        record = dict(materialization.record(fixture_id))
        declared = [
            list(cost.get("explicit_payment_sources") or ())
            for cost in record.get("action_cost_state") or ()
        ]
        for step in record["decision_script"]:
            if step["decision_family"] != "mana_payment":
                continue
            value = step["selection"]["semantic_value"]
            assert value["sources"] in declared, fixture_id
            assert step["selection"]["selector_kind"] == "mana_payment"
            assert step["selection"]["on_zero_match"] == "FAIL_CLOSED"


def test_the_measured_payment_positions_hold() -> None:
    materialization = load_effective_materialization(REPO_ROOT)

    def own(fixture_id: str) -> list[str]:
        script = materialization.record(fixture_id)["decision_script"]
        return [
            step["decision_family"]
            for step in script
            if step["decision_family"] not in ("mulligan", "priority_pass_through")
        ]

    # Dig Through Time: paid (with delve) before its look-and-choose.
    assert own("CARD_12")[:3] == ["priority", "mana_payment", "target"]
    # Finale of Revelation: X is announced, then paid, then the choice.
    assert own("CARD_15")[:4] == ["priority", "announce_x", "mana_payment", "choose_object"]
    # Bolt Bend: its target, then payment, then the redirected target.
    assert own("CARD_22")[:4] == ["priority", "target", "mana_payment", "target"]
    # Makeshift Mannequin then Lightning Bolt: each paid after its own target,
    # with the colours actually spent.
    script = materialization.record("CARD_23")["decision_script"]
    spent = [
        step["selection"]["semantic_value"]["mana"]
        for step in script
        if step["decision_family"] == "mana_payment"
    ]
    assert spent == [["R", "R", "R", "B"], ["R"]]
    # RNG_RULES_TAPE keeps its single Chaos Warp payment and gains the Burn one.
    payments = [
        step
        for step in materialization.record("RNG_RULES_TAPE")["decision_script"]
        if step["decision_family"] == "mana_payment"
    ]
    assert len(payments) == 2


def _temp_repo(tmp_path: Path) -> Path:
    authority = _json(AUTHORITY_PATH)
    files = {
        "scripts/resolve_pre_freeze_contract.py": REPO_ROOT
        / "scripts/resolve_pre_freeze_contract.py",
        "qualification/CURRENT_PRE_FREEZE_CONTRACT.json": AUTHORITY_PATH,
        str(PREDECESSOR.relative_to(REPO_ROOT)): PREDECESSOR,
        str(PREDECESSOR_SCHEMA.relative_to(REPO_ROOT)): PREDECESSOR_SCHEMA,
        "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json": (
            REPO_ROOT / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json"
        ),
        authority["full107"]["historical_base_materialization"]: (
            REPO_ROOT / authority["full107"]["historical_base_materialization"]
        ),
        str(LEDGER_PATH.relative_to(REPO_ROOT)): LEDGER_PATH,
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
        str(CONTRACT.relative_to(REPO_ROOT)),
        str(SCHEMA.relative_to(REPO_ROOT)),
        "qualification/CURRENT_PRE_FREEZE_CONTRACT.json",
        str(LEDGER_PATH.relative_to(REPO_ROOT)),
    )
    before = {relative: (REPO_ROOT / relative).read_bytes() for relative in targets}
    for _ in range(2):
        subprocess.run(
            [sys.executable, str(GENERATOR), str(root)], check=True, capture_output=True, text=True
        )
        for relative in targets:
            assert (root / relative).read_bytes() == before[relative], relative
    for relative in targets:
        assert (REPO_ROOT / relative).read_bytes() == before[relative], relative
