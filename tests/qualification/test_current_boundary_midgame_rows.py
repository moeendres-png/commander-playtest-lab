"""The PB-03 chain's last links: verified placement obligation -> positive receipt -> credit.

``midgame_rows`` executes exactly constructed placement rows on the production
midgame lane and verifies each required event against the engine's public
event tape. These tests pin the verification rules and the receipt chain
without a live engine: a receipt exists only for a verified row, it loads only
intact, and it is credited only for the bound candidate, runner and
denominator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary import receipts as R

COMMIT = "9" * 40
RUNNER = "r" * 64


def _record(required: list[str]) -> dict[str, Any]:
    return {
        "fixture_id": "MICRO_TRIGGERS",
        "expected_events": {"required_events": required},
        "terminal_postconditions": ["P2 is at 38 life."],
        "requested_state_digest": "a" * 64,
        "obligation_digest": "b" * 64,
    }


TAPE: list[dict[str, Any]] = [
    {
        "sequence": 7,
        "type": "ZONE_CHANGE",
        "from": "HAND",
        "to": "STACK",
        "target_object": "obj:bears",
    },
    {"sequence": 8, "type": "SPELL_CAST", "source_object": "obj:bears", "player_player": "P1"},
    {
        "sequence": 9,
        "type": "ZONE_CHANGE",
        "from": "STACK",
        "to": "BATTLEFIELD",
        "target_object": "obj:bears",
    },
    {
        "sequence": 10,
        "type": "TRIGGERED_ABILITY",
        "source_name": "Warstorm Surge",
        "source_object": "obj:surge",
    },
    {"sequence": 11, "type": "DAMAGED_PLAYER", "target_player": "P2", "amount": 2, "combat": False},
    {
        "sequence": 12,
        "type": "ATTACKER_DECLARED",
        "source_object": "obj:mp-attacker-0",
        "target_player": "P2",
    },
    {
        "sequence": 13,
        "type": "ZONE_CHANGE",
        "from": "COMMAND",
        "to": "STACK",
        "public_identity": True,
    },
]

TRACE = [
    mr.Frame("priority", "P1", ["Cast Grizzly Bears"], "Cast Grizzly Bears", scripted=True),
    mr.Frame("mana_payment", "P1", ["Forest"], "Forest", selected_option_type="mana_ability"),
    mr.Frame(
        "target", "P1", ["Full Game Seat 2", "Full Game Seat 3"], "Full Game Seat 2", scripted=True
    ),
]


@pytest.mark.parametrize(
    "token",
    [
        "creature_enters",
        "creature_enters:obj:bears",
        "creature_entered",
        "trigger:Warstorm_Surge",
        "Warstorm_trigger",
        "damage:P2:2",
        "entering_creature_damage:P2:2",
        "noncombat_damage:P2:2",
        "spell_cast:obj:bears",
        "attacker_declared:obj:mp-attacker-0->P2",
        "commander_cast_from_command",
        "spell_resolved",
        "priority_decision_frame:P1",
        "target_decision_frame:P1",
        "target_selected:P2",
        "legal_targets_exposed",
        "mana_paid:1",
    ],
)
def test_an_observed_token_has_positive_evidence(token: str) -> None:
    assert mr.verify_token(token, TAPE, TRACE, set()) is not None


@pytest.mark.parametrize(
    "token",
    [
        "creature_enters:obj:other",
        "trigger:Soul_Warden",
        "damage:P2:3",
        "damage:P3:2",
        "spell_cast:obj:other",
        "attacker_declared:obj:mp-attacker-0->P3",
        "target_selected:P3",
        "declare_attacker_frame:P1",
        "mana_paid:2",
        "commander_tax:+4_generic",
        "state_based_actions",
        "layer7b_set_pt:1/1",
    ],
)
def test_an_unobserved_or_unknown_token_is_never_assumed(token: str) -> None:
    assert mr.verify_token(token, TAPE, TRACE, set()) is None


def test_commander_tax_is_paid_mana_minus_the_declared_printed_value() -> None:
    trace = [
        mr.Frame("mana_payment", "P1", [], "Mountain", selected_option_type="mana_ability")
        for _ in range(4)
    ]
    assert mr.verify_token("commander_tax:+4_generic", [], trace, set(), 0) is not None
    assert mr.verify_token("commander_tax:+4_generic", [], trace, set(), 1) is None


def test_terminal_checks_read_the_engine_observation() -> None:
    observation = {
        "seats": [
            {
                "player_id": "P1",
                "life": 40,
                "commanders": [{"prior_casts": 3}],
                "battlefield": [{"card_identity": "Grizzly Bears", "tapped": True}],
            },
            {"player_id": "P2", "life": 38, "commanders": [], "battlefield": []},
        ]
    }
    assert mr.check_terminal(
        mr.TerminalCheck("life", principal="P2", value=38), observation, TAPE, TRACE
    )
    assert not mr.check_terminal(
        mr.TerminalCheck("life", principal="P2", value=18), observation, TAPE, TRACE
    )
    assert mr.check_terminal(
        mr.TerminalCheck("trigger_count", source_name="Warstorm Surge", value=1),
        observation,
        TAPE,
        TRACE,
    )
    assert mr.check_terminal(
        mr.TerminalCheck("commander_prior_casts", principal="P1", value=3), observation, TAPE, TRACE
    )
    assert mr.check_terminal(
        mr.TerminalCheck("tapped", principal="P1", card_identity="Grizzly Bears", value=True),
        observation,
        TAPE,
        TRACE,
    )
    assert not mr.check_terminal(mr.TerminalCheck("no_mana_payment"), observation, TAPE, TRACE)


def _verified() -> mr.RowExecution:
    return mr.RowExecution(
        "MICRO_TRIGGERS",
        True,
        "EXACT",
        "obligation observed",
        token_evidence={"damage:P2:2": {"events": [11]}},
        terminal_facts={"P2 is at 38 life": True},
        tape=TAPE,
    )


def test_an_unverified_row_gets_no_receipt() -> None:
    execution = _verified()
    execution.verified = False
    with pytest.raises(ValueError):
        mr.positive_receipt(
            execution, _record(["damage:P2:2"]), candidate_commit=COMMIT, runner_digest=RUNNER
        )


def _persist(tmp_path: Path, receipt: dict[str, Any]) -> Path:
    directory = tmp_path / R.POSITIVE_RECEIPT_SUBDIR
    R.persist(directory / "MICRO_TRIGGERS.json", receipt)
    return directory


def test_a_verified_receipt_loads_and_is_credited(tmp_path: Path) -> None:
    receipt = mr.positive_receipt(
        _verified(), _record(["damage:P2:2"]), candidate_commit=COMMIT, runner_digest=RUNNER
    )
    directory = _persist(tmp_path, receipt)
    loaded, rejected = R.collect_positive_fixture_receipts(directory)
    assert rejected == []
    credit = R.positive_fixture_credit(
        loaded,
        candidate="xmage",
        expected_commit=COMMIT,
        denominator={"MICRO_TRIGGERS"},
        expected_runner_digest=RUNNER,
    )
    assert credit == {"MICRO_TRIGGERS": [mr.TEST_IDENTITY_PREFIX + "MICRO_TRIGGERS"]}
    # The native-suite loader reads only the top level and never sees it.
    assert R.collect_receipts(tmp_path) == ([], [])


@pytest.mark.parametrize(
    ("commit", "runner", "denominator"),
    [
        ("8" * 40, RUNNER, {"MICRO_TRIGGERS"}),
        (COMMIT, "s" * 64, {"MICRO_TRIGGERS"}),
        (COMMIT, RUNNER, {"CARD_02"}),
    ],
)
def test_a_receipt_is_credited_only_for_its_candidate_runner_and_denominator(
    tmp_path: Path, commit: str, runner: str, denominator: set[str]
) -> None:
    receipt = mr.positive_receipt(
        _verified(), _record(["damage:P2:2"]), candidate_commit=COMMIT, runner_digest=RUNNER
    )
    loaded, _ = R.collect_positive_fixture_receipts(_persist(tmp_path, receipt))
    assert (
        R.positive_fixture_credit(
            loaded,
            candidate="xmage",
            expected_commit=commit,
            denominator=denominator,
            expected_runner_digest=runner,
        )
        == {}
    )


@pytest.mark.parametrize("defect", ["tampered", "missing_field", "wrong_schema"])
def test_a_defective_receipt_is_rejected(tmp_path: Path, defect: str) -> None:
    receipt = mr.positive_receipt(
        _verified(), _record(["damage:P2:2"]), candidate_commit=COMMIT, runner_digest=RUNNER
    )
    if defect == "tampered":
        receipt["fixture_id"] = "CARD_02"
    elif defect == "missing_field":
        del receipt["observed_assertion"]
        receipt["receipt_digest"] = R._digest(
            {k: v for k, v in receipt.items() if k != "receipt_digest"}
        )
    else:
        receipt["schema_version"] = R.NATIVE_SUITE_RECEIPT_SCHEMA
    loaded, rejected = R.collect_positive_fixture_receipts(_persist(tmp_path, receipt))
    assert loaded == []
    assert len(rejected) == 1


def test_execute_and_persist_clears_stale_receipts_first(tmp_path: Path) -> None:
    directory = tmp_path / R.POSITIVE_RECEIPT_SUBDIR
    directory.mkdir()
    (directory / "OLD.json").write_text(json.dumps({"schema_version": "stale"}), encoding="utf-8")
    summary = mr.execute_and_persist(
        workspace=tmp_path,
        records={},
        candidate_commit=COMMIT,
        runner_digest=RUNNER,
        out_dir=directory,
        fixtures=(),
    )
    assert list(directory.glob("*.json")) == []
    assert summary["rows_verified"] == 0
