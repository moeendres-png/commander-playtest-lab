"""AF05-AF09 gate derivations: hard-coded literals replaced by measurement.

The assembler previously wrote UNKNOWN for these gates as a literal, so no
amount of real evidence could ever promote them and no contradiction could ever
be reported. These tests prove the derivation is real in both directions: every
gate can reach PASS from complete evidence, and every mutation of that evidence
produces the failure class the contract names.
"""

from __future__ import annotations

from typing import Any

from commander_lab.qualification.current_boundary import gate_derivations as g


def _row(state: str = "PASS") -> dict[str, Any]:
    return {"fixture_id": "X", "exit_state": state, "reason": None}


def _rows(states: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {fixture: _row(state) for fixture, state in states.items()}


def _counts(rows: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows.values():
        counts[row["exit_state"]] = counts.get(row["exit_state"], 0) + 1
    return counts


ALL_PASS_ROWS = _rows(
    {
        "HIDDEN_01": "PASS",
        "HIDDEN_02": "PASS",
        "CARD_01": "PASS",
        "WS05-CMD-TAX-2": "PASS",
        "REPLAY_CLEAN_PROCESS": "PASS",
        "MICRO_TRIGGERS": "PASS",
    }
)
CREDIBLE_SCOPING = {
    "attribution": "NONE",
    "engine_leak_indicators": [],
    "credible_as_principal_scoped_evidence": True,
    "findings": [],
}
COMPLETE_CORPUS = {
    "required_29_card_corpus": {
        "complete": True,
        "required_count": 29,
        "behaviorally_executed_count": 29,
        "missing_identities": [],
    }
}


def _complete_lifecycle(count: int) -> dict[str, Any]:
    return {
        "player_count": count,
        "failure": None,
        "steps_completed": [
            "handshake",
            "import_deck",
            "create_commander_game",
            "start_game",
            "decision_drive",
        ],
        "terminal_facts": {"priority_reached": True},
        "decision_tape": [
            {
                "kind": "PRIORITY",
                "actor": "p1",
                "revision": 4,
                "policy": "pass_when_offered",
                "chosen_option_id": "opt-pass",
                "offered_option_ids": ["opt-pass"],
                "note": "external priority pass",
            }
        ],
    }


COMPLETE_CARDINALITY = {
    "results": {f"{count}P": _complete_lifecycle(count) for count in (2, 3, 4, 5)}
}
TWIN = {"clean_process_twin": {"verified": True}}
ACK_SEED = {
    "rules_rng_binding": {
        "classification": "ACKNOWLEDGED_ENGINE_SEED",
        "requested_seed": 424242,
        "acknowledged_seed": 424242,
    },
    "semantic_replay": {},
}


# --------------------------------------------------------------------------- #
# AF05
# --------------------------------------------------------------------------- #


def test_af05_passes_only_with_scoped_observations_and_all_hidden_rows() -> None:
    gate = g.af05_hidden_information(
        "forge", ALL_PASS_ROWS, {"principal_scoping": CREDIBLE_SCOPING}
    )
    assert gate["verdict"] == "PASS"


def test_af05_unscoped_observations_are_not_evidence() -> None:
    scoping = {**CREDIBLE_SCOPING, "credible_as_principal_scoped_evidence": False}
    gate = g.af05_hidden_information("forge", ALL_PASS_ROWS, {"principal_scoping": scoping})
    assert gate["verdict"] == "UNKNOWN"
    assert any("not established" in item for item in gate["nonblocking_limitations"])


def test_af05_demonstrated_leak_is_fail() -> None:
    scoping = {
        **CREDIBLE_SCOPING,
        "attribution": "ENGINE_CANDIDATE_DEFECT",
        "engine_leak_indicators": ["hand"],
    }
    gate = g.af05_hidden_information("forge", ALL_PASS_ROWS, {"principal_scoping": scoping})
    assert gate["verdict"] == "FAIL"
    assert gate["blocking_rows"]


def test_af05_residual_rows_keep_it_unknown() -> None:
    rows = _rows({"HIDDEN_01": "PASS", "HIDDEN_02": "UNKNOWN"})
    gate = g.af05_hidden_information("forge", rows, {"principal_scoping": CREDIBLE_SCOPING})
    assert gate["verdict"] == "UNKNOWN"
    assert gate["blocking_rows"] == ["HIDDEN_02"]


# --------------------------------------------------------------------------- #
# AF06
# --------------------------------------------------------------------------- #


def test_af06_passes_only_when_every_row_passes() -> None:
    gate = g.af06_general_rules("forge", ALL_PASS_ROWS, _counts(ALL_PASS_ROWS))
    assert gate["verdict"] == "PASS"
    rows = _rows({"MICRO_TRIGGERS": "PASS", "MICRO_COSTS": "BLOCKED"})
    gate = g.af06_general_rules("forge", rows, _counts(rows))
    assert gate["verdict"] == "UNKNOWN"
    assert gate["blocking_rows"] == ["MICRO_COSTS"]


def test_af06_a_current_boundary_failure_is_fail() -> None:
    rows = _rows({"MICRO_TRIGGERS": "PASS", "MICRO_COSTS": "FAIL"})
    gate = g.af06_general_rules("forge", rows, _counts(rows))
    assert gate["verdict"] == "FAIL"


# --------------------------------------------------------------------------- #
# AF07
# --------------------------------------------------------------------------- #


def test_af07_passes_only_with_the_complete_corpus() -> None:
    gate = g.af07_actual_card("forge", ALL_PASS_ROWS, COMPLETE_CORPUS)
    assert gate["verdict"] == "PASS"


def test_af07_incomplete_corpus_is_unknown_and_names_the_missing_identities() -> None:
    document = {
        "required_29_card_corpus": {
            "complete": False,
            "required_count": 29,
            "behaviorally_executed_count": 1,
            "missing_identities": ["Hex", "Opt"],
        }
    }
    gate = g.af07_actual_card("forge", ALL_PASS_ROWS, document)
    assert gate["verdict"] == "UNKNOWN"
    assert any("Hex" in item for item in gate["nonblocking_limitations"])


def test_af07_a_failed_mandatory_card_row_is_fail() -> None:
    rows = {**ALL_PASS_ROWS, "CARD_02": _row("FAIL")}
    gate = g.af07_actual_card("forge", rows, COMPLETE_CORPUS)
    assert gate["verdict"] == "FAIL"
    assert gate["blocking_rows"] == ["CARD_02"]


# --------------------------------------------------------------------------- #
# AF08
# --------------------------------------------------------------------------- #


def test_af08_passes_with_all_ws05_rows_and_complete_lifecycles() -> None:
    gate = g.af08_multiplayer("forge", ALL_PASS_ROWS, COMPLETE_CARDINALITY)
    assert gate["verdict"] == "PASS"


def test_af08_incomplete_lifecycles_keep_it_unknown() -> None:
    document = {"results": {"2P": {"player_count": 2, "failure": None, "steps_completed": ["a"]}}}
    gate = g.af08_multiplayer("forge", ALL_PASS_ROWS, document)
    assert gate["verdict"] == "UNKNOWN"


def test_af08_a_failed_ws05_row_is_fail() -> None:
    rows = {**ALL_PASS_ROWS, "WS05-CMD-TAX-2": _row("FAIL")}
    gate = g.af08_multiplayer("forge", rows, COMPLETE_CARDINALITY)
    assert gate["verdict"] == "FAIL"


# --------------------------------------------------------------------------- #
# AF09
# --------------------------------------------------------------------------- #


def test_af09_seed_acknowledgement_alone_is_not_replay_proof() -> None:
    gate = g.af09_rng_replay("forge", ALL_PASS_ROWS, ACK_SEED)
    assert gate["verdict"] == "UNKNOWN"
    assert any("clean-process" in item for item in gate["nonblocking_limitations"])


def test_af09_a_verified_clean_process_twin_can_pass() -> None:
    document = {**ACK_SEED, **TWIN}
    gate = g.af09_rng_replay("forge", ALL_PASS_ROWS, document)
    assert gate["verdict"] == "PASS"


def test_af09_a_refused_export_never_passes_even_with_all_rows_green() -> None:
    document = {
        "rules_rng_binding": {"classification": "UNCONTROLLED_ENGINE_RNG"},
        "semantic_replay": {"error": [{"code": "unsupported_message"}]},
        **TWIN,
    }
    gate = g.af09_rng_replay("forge", ALL_PASS_ROWS, document)
    assert gate["verdict"] == "UNKNOWN"
    assert any("absent capability" in item for item in gate["nonblocking_limitations"])


def test_af09_a_failed_replay_row_is_fail() -> None:
    rows = {**ALL_PASS_ROWS, "REPLAY_CLEAN_PROCESS": _row("FAIL")}
    gate = g.af09_rng_replay("forge", rows, {**ACK_SEED, **TWIN})
    assert gate["verdict"] == "FAIL"


def test_af09_carries_the_established_refusal_and_seed_wording() -> None:
    described = {
        "evidence": ["replay export attempted in a live game and refused by the engine"],
        "limitations": ["deterministic setup alone is not semantic replay proof"],
    }
    gate = g.af09_rng_replay("forge", ALL_PASS_ROWS, ACK_SEED, described=described)
    assert any("refused by the engine" in item for item in gate["evidence"])
    assert any("not semantic replay proof" in item for item in gate["nonblocking_limitations"])
