"""AF05-AF09 gate derivations: hard-coded literals replaced by measurement.

The assembler previously wrote UNKNOWN for these gates as a literal, so no
amount of real evidence could ever promote them and no contradiction could ever
be reported. These tests prove the derivation is real in both directions: every
gate can reach PASS from complete evidence, and every mutation of that evidence
produces the failure class the contract names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import gate_derivations as g
from commander_lab.qualification.current_boundary import receipts as receipt_mod

REPO = Path(__file__).resolve().parents[2]


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
TWIN = {
    "clean_process_twin": {
        "verified": True,
        "fixture_identity": "REPLAY_CLEAN_PROCESS",
        "process_identity": "clean-process-2",
        "decisions": ["priority:cast", "mode:create_devils"],
        "rules_rng": {"seed": 424242, "library_shuffle": "recorded"},
        "semantic_events": ["SPELL_CAST", "CREATED_TOKEN"],
        "checkpoint_state_hashes": {"arrival": "a" * 64, "terminal": "b" * 64},
        "terminal_outcome": "three Devil tokens under P1",
    }
}
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


def test_af05_without_a_denominator_is_unknown_not_pass() -> None:
    gate = g.af05_hidden_information("forge", {}, {"principal_scoping": CREDIBLE_SCOPING})
    assert gate["verdict"] == "UNKNOWN"


def test_af05_residual_rows_keep_it_unknown() -> None:
    rows = _rows({"HIDDEN_01": "PASS", "HIDDEN_02": "UNKNOWN"})
    gate = g.af05_hidden_information("forge", rows, {"principal_scoping": CREDIBLE_SCOPING})
    assert gate["verdict"] == "UNKNOWN"
    assert gate["blocking_rows"] == ["HIDDEN_02"]


def test_af05_a_failed_hidden_row_fails_the_gate_rather_than_staying_unknown() -> None:
    """A demonstrated row failure is a violated boundary, not an unproven one."""
    rows = _rows({"HIDDEN_01": "FAIL", "HIDDEN_02": "UNKNOWN", "HIDDEN_03": "PASS"})
    gate = g.af05_hidden_information("xmage", rows, {"principal_scoping": CREDIBLE_SCOPING})
    assert gate["verdict"] == "FAIL"
    assert gate["blocking_rows"] == ["HIDDEN_01"]
    # Fail-before: the same rows without the failure are only UNKNOWN.
    rows["HIDDEN_01"] = _row("UNKNOWN")
    gate = g.af05_hidden_information("xmage", rows, {"principal_scoping": CREDIBLE_SCOPING})
    assert gate["verdict"] == "UNKNOWN"


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


def test_af06_without_rows_is_unknown_not_pass() -> None:
    assert g.af06_general_rules("forge", {}, {})["verdict"] == "UNKNOWN"


def test_af06_a_current_boundary_failure_is_fail() -> None:
    rows = _rows({"MICRO_TRIGGERS": "PASS", "MICRO_COSTS": "FAIL"})
    gate = g.af06_general_rules("forge", rows, _counts(rows))
    assert gate["verdict"] == "FAIL"


# --------------------------------------------------------------------------- #
# AF07
# --------------------------------------------------------------------------- #


def test_af07_passes_only_with_the_complete_corpus() -> None:
    # The corpus is derived from the frozen manifests; build one all-PASS row per
    # mandatory CARD_ fixture so the PASS is earned from real coverage.
    identities, corpus = g.actual_card_corpus(REPO)
    assert len(corpus) == 29
    rows = {fixture_id: _row("PASS") for fixture_id in identities}
    gate = g.af07_actual_card("forge", rows, COMPLETE_CORPUS)
    assert gate["verdict"] == "PASS"


def test_af07_a_self_reported_complete_flag_without_rows_cannot_pass() -> None:
    """The runner writes its summary before the lane runs; the row states win."""

    identities, _corpus = g.actual_card_corpus(REPO)
    partial = {next(iter(identities)): _row("PASS")}
    gate = g.af07_actual_card("forge", partial, COMPLETE_CORPUS)
    assert gate["verdict"] == "UNKNOWN", gate
    assert any("unexecuted" in item for item in gate["nonblocking_limitations"])


def test_af07_without_card_rows_is_unknown_not_pass() -> None:
    assert g.af07_actual_card("forge", {}, COMPLETE_CORPUS)["verdict"] == "UNKNOWN"


def test_af07_incomplete_corpus_is_unknown_and_names_the_missing_identities() -> None:
    identities, corpus = g.actual_card_corpus(REPO)
    first_fixture = sorted(identities)[0]
    rows = {first_fixture: _row("PASS")}
    gate = g.af07_actual_card("forge", rows, COMPLETE_CORPUS)
    assert gate["verdict"] == "UNKNOWN"
    missing_line = next(item for item in gate["nonblocking_limitations"] if "unexecuted" in item)
    # The named identities come from the frozen corpus, not from the artifact.
    assert any(identity in missing_line for identity in corpus)


def test_af07_a_failed_mandatory_card_row_is_fail() -> None:
    rows = {**ALL_PASS_ROWS, "CARD_02": _row("FAIL")}
    gate = g.af07_actual_card("forge", rows, COMPLETE_CORPUS)
    assert gate["verdict"] == "FAIL"
    assert gate["blocking_rows"] == ["CARD_02"]


# --------------------------------------------------------------------------- #
# AF07 same-epoch campaign credit
# --------------------------------------------------------------------------- #

_PIN = "f" * 40
_RUNNER = "d" * 64
_PREFIX = "af07-actual-card-campaign#"


def _card_records() -> dict[str, dict[str, Any]]:
    identities, _corpus = g.actual_card_corpus(REPO)
    return {
        fixture: {"requested_state_digest": f"{index:064x}", "obligation_digest": "b" * 64}
        for index, fixture in enumerate(sorted(identities))
    }


def _campaign_receipt(fixture: str, records: dict[str, dict[str, Any]], **over: Any) -> dict:
    receipt: dict[str, Any] = {
        "schema_version": receipt_mod.POSITIVE_FIXTURE_RECEIPT_SCHEMA,
        "candidate": "xmage",
        "candidate_commit": _PIN,
        "runner_digest": _RUNNER,
        "fixture_id": fixture,
        "test_identity": _PREFIX + fixture,
        "obligation_exercised": {
            "requested_state_digest": records[fixture]["requested_state_digest"],
            "obligation_digest": records[fixture]["obligation_digest"],
        },
        "observed_assertion": {"terminal_facts": {"held": True}},
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "outcome": "PASS",
    }
    receipt.update(over)
    return receipt


def _campaign_states(receipts: list[dict], records: dict, **over: Any) -> dict[str, str]:
    arguments: dict[str, Any] = {
        "candidate": "xmage",
        "candidate_commit": _PIN,
        "runner_digest": _RUNNER,
        "records": records,
        "test_identity_prefix": _PREFIX,
    }
    arguments.update(over)
    return g.actual_card_campaign_states(receipts, **arguments)


def test_af07_campaign_receipts_complete_the_corpus_outside_the_denominator() -> None:
    records = _card_records()
    states = _campaign_states([_campaign_receipt(fixture, records) for fixture in records], records)
    assert set(states.values()) == {"PASS"}
    # Only CARD_02 is a denominator row; the campaign supplies the other 28.
    rows = {"CARD_02": _row("PASS")}
    gate = g.af07_actual_card("xmage", rows, COMPLETE_CORPUS, campaign_states=states)
    assert gate["verdict"] == "PASS", gate
    assert any("credited from same-epoch" in line for line in gate["evidence"])


def test_af07_the_denominator_row_wins_over_a_campaign_receipt_for_its_own_fixture() -> None:
    records = _card_records()
    states = _campaign_states([_campaign_receipt(fixture, records) for fixture in records], records)
    rows = {"CARD_02": _row("UNKNOWN")}
    gate = g.af07_actual_card("xmage", rows, COMPLETE_CORPUS, campaign_states=states)
    assert gate["verdict"] == "UNKNOWN"
    assert "CARD_02" in gate["blocking_rows"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"runner_digest": "0" * 64},
        {"candidate_commit": "0" * 40},
        {"candidate": "forge"},
        {"test_identity": "midgame-row#CARD_05"},
        {"outcome": "FAIL"},
        {"assertion_kind": "NEGATIVE_CONTROL"},
        {"observed_assertion": {}},
    ],
)
def test_af07_a_campaign_receipt_bound_to_anything_else_earns_nothing(
    mutation: dict[str, Any],
) -> None:
    records = _card_records()
    states = _campaign_states([_campaign_receipt("CARD_05", records, **mutation)], records)
    assert states == {}


def test_af07_a_campaign_receipt_for_a_drifted_record_earns_nothing() -> None:
    records = _card_records()
    receipt = _campaign_receipt("CARD_05", records)
    drifted = {**records, "CARD_05": {**records["CARD_05"], "obligation_digest": "c" * 64}}
    assert _campaign_states([receipt], drifted) == {}


def test_af07_the_campaign_documents_own_pass_label_promotes_nothing() -> None:
    records = _card_records()
    document = {
        "campaign": {"candidate": "xmage", "candidate_commit": _PIN, "runner_digest": _RUNNER},
        "rows": [{"fixture_id": "CARD_05", "verdict": {"outcome": "DIRECT_PASS"}}],
    }
    assert _campaign_states([], records, campaign_document=document) == {}


def test_af07_a_bound_campaign_fail_is_fail_and_is_never_masked() -> None:
    records = _card_records()
    document = {
        "campaign": {"candidate": "xmage", "candidate_commit": _PIN, "runner_digest": _RUNNER},
        "rows": [{"fixture_id": "CARD_02", "verdict": {"outcome": "FAIL"}}],
    }
    states = _campaign_states([], records, campaign_document=document)
    assert states == {"CARD_02": "FAIL"}
    gate = g.af07_actual_card(
        "xmage", {"CARD_02": _row("PASS")}, COMPLETE_CORPUS, campaign_states=states
    )
    assert gate["verdict"] == "FAIL"
    assert gate["blocking_rows"] == ["CARD_02"]


def test_af07_a_receipt_the_epoch_document_did_not_record_earns_nothing() -> None:
    records = _card_records()
    receipt = _campaign_receipt("CARD_05", records, receipt_digest="a" * 64)
    bound = {"candidate": "xmage", "candidate_commit": _PIN, "runner_digest": _RUNNER}
    recorded = {"campaign": bound, "rows": [{"fixture_id": "CARD_05", "receipt_digest": "a" * 64}]}
    assert _campaign_states([receipt], records, campaign_document=recorded) == {"CARD_05": "PASS"}
    other = {"campaign": bound, "rows": [{"fixture_id": "CARD_05", "receipt_digest": "b" * 64}]}
    assert _campaign_states([receipt], records, campaign_document=other) == {}
    blocked = {"campaign": bound, "rows": [{"fixture_id": "CARD_05", "receipt_digest": None}]}
    assert _campaign_states([receipt], records, campaign_document=blocked) == {}


def test_af07_an_unbound_campaign_fail_is_not_evidence() -> None:
    records = _card_records()
    document = {
        "campaign": {"candidate": "xmage", "candidate_commit": _PIN, "runner_digest": "0" * 64},
        "rows": [{"fixture_id": "CARD_02", "verdict": {"outcome": "FAIL"}}],
    }
    assert _campaign_states([], records, campaign_document=document) == {}


def test_af07_without_campaign_credit_says_so() -> None:
    gate = g.af07_actual_card("forge", {"CARD_02": _row("PASS")}, COMPLETE_CORPUS)
    assert gate["verdict"] == "UNKNOWN"
    assert "no same-epoch actual-card campaign credit was supplied" in gate["evidence"]


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


def test_af08_without_ws05_rows_is_unknown_not_pass() -> None:
    gate = g.af08_multiplayer("forge", {}, COMPLETE_CARDINALITY)
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


def test_af09_a_bare_verified_flag_is_not_twin_evidence() -> None:
    document = {**ACK_SEED, "clean_process_twin": {"verified": True}}
    gate = g.af09_rng_replay("forge", ALL_PASS_ROWS, document)
    assert gate["verdict"] == "UNKNOWN"
    assert any(
        "does not carry the required twin evidence" in item
        for item in gate["nonblocking_limitations"]
    )


@pytest.mark.parametrize(
    "missing",
    [
        "fixture_identity",
        "process_identity",
        "decisions",
        "rules_rng",
        "semantic_events",
        "checkpoint_state_hashes",
        "terminal_outcome",
    ],
)
def test_af09_every_named_twin_element_is_required(missing: str) -> None:
    twin = dict(TWIN["clean_process_twin"])
    twin.pop(missing)
    document = {**ACK_SEED, "clean_process_twin": twin}
    assert g.af09_rng_replay("forge", ALL_PASS_ROWS, document)["verdict"] == "UNKNOWN"


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
