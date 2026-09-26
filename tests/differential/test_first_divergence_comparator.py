"""DR-CLOSURE-01 Phase 5: first-semantic-divergence comparator tests.

Method verification only (no donor code): equal traces MATCH; each mismatch
class fires exactly once at the right record; irrelevant differences
normalize; meaningful identity differences never normalize. A real frozen
XMage same-seed tape pair (WS218 4P, 257 steps) runs through the comparator
for MATCH plus targeted first-divergence detection. MATCH is trace agreement
only, never a Rules PASS.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from commander_lab.semantic_replay.comparator import (
    DivergenceKind,
    compare_tapes,
)


def _source_lock() -> dict:
    return {
        "lab_repository": "moeendres-png/commander-playtest-lab",
        "lab_commit": "a" * 40,
        "lab_tree": "b" * 40,
        "provider_identity": "xmage",
        "engine_repository": "moeendres-png/mage",
        "engine_commit": "c" * 40,
        "engine_tree": "d" * 40,
        "engine_version": "1.4.61",
        "adapter_identity": "test-adapter",
        "protocol_version": "2.0.0",
        "decision_protocol_version": "1.0.0",
        "protocol_schema_digest": "e" * 64,
        "rules_authority_identity": "xmage",
    }


def _manifest(**overrides) -> dict:
    base = {
        "format": "commander-ffa",
        "player_count": 2,
        "seat_principals": [
            {
                "seat": 1,
                "deck_id": "deck-1",
                "pilot_identity": "pilot-a",
                "pilot_version": "1",
                "decision_policy_version": "1",
            },
            {
                "seat": 2,
                "deck_id": "deck-2",
                "pilot_identity": "pilot-b",
                "pilot_version": "1",
                "decision_policy_version": "1",
            },
        ],
        "decks": [
            {
                "deck_id": "deck-1",
                "deck_hash": "1" * 64,
                "commander_names": ["Rograkh, Son of Rohgahh"],
                "mainboard": ["Mountain"],
            },
            {
                "deck_id": "deck-2",
                "deck_hash": "2" * 64,
                "commander_names": ["Rograkh, Son of Rohgahh"],
                "mainboard": ["Mountain"],
            },
        ],
        "commander_identities": [
            "Rograkh, Son of Rohgahh",
            "Rograkh, Son of Rohgahh",
        ],
        "starting_life": 40,
        "starting_player_selection_contract": "seat-1",
        "mulligan_contract": "london",
        "rules_seed": 424242,
        "rules_seed_explicit_required": True,
        "pilot_seed_derivation": "rules-seed-plus-seat",
        "process_isolation_contract": "fresh-process-per-game",
    }
    base.update(overrides)
    return base


def _rng_contract(**overrides) -> dict:
    base = {
        "root_rules_seed": 424242,
        "rules_seed_explicit": True,
        "require_explicit_seed": True,
        "attribution_model": "calls-coordinate-plus-state-transition",
    }
    base.update(overrides)
    return base


def _checkpoint(**overrides) -> dict:
    base = {
        "rules_seed": 424242,
        "rules_random_calls": 10,
        "turn_number": 1,
        "phase": "precombat_main",
        "step": "main",
        "decision_sequence": 3,
        "event_offset": 5,
        "semantic_state_digest": "a" * 64,
        "public_state_digest": "b" * 64,
        "principal_digests": {"1": "c" * 64, "2": "d" * 64},
    }
    base.update(overrides)
    return base


def _step(sequence: int, **overrides) -> dict:
    base = {
        "sequence": sequence,
        "step_kind": "decision",
        "decision_class": "priority",
        "actor_principal": 1,
        "decision_revision": sequence,
        "principal_observation_digest": "f" * 64,
        "legal_set_digest": "d" * 64,
        "legal_set_size": 1,
        "selected_fingerprints": ["fp-pass"],
        "selected_labels": ["Pass priority"],
        "numeric_choice": None,
        "numeric_min": None,
        "numeric_max": None,
        "numeric_choices": None,
        "numeric_legs_min": None,
        "numeric_legs_max": None,
        "numeric_total_min": None,
        "numeric_total_max": None,
        "rng_calls_before": 10,
        "rng_calls_after": 10,
        "event_offset_before": sequence - 1,
        "event_offset_after": sequence,
        "event_digest": "e" * 64,
        "post_checkpoint_digest": "9" * 64,
    }
    base.update(overrides)
    return base


def _terminal(**overrides) -> dict:
    base = {
        "terminal": True,
        "turn_number": 6,
        "rules_random_calls": 20,
        "outcomes": [
            {"seat": 1, "won": True, "lost": False, "left": False, "life": 20},
            {"seat": 2, "won": False, "lost": True, "left": True, "life": 0},
        ],
        "semantic_state_digest": "7" * 64,
        "public_state_digest": "8" * 64,
    }
    base.update(overrides)
    return base


def _tape(steps: int = 3, **overrides) -> dict:
    base = {
        "schema_version": "semantic-replay-tape/1.0.0",
        "tape_id": "1" * 64,
        "source_lock": _source_lock(),
        "game_manifest": _manifest(),
        "rng_contract": _rng_contract(),
        "initial_checkpoint": _checkpoint(),
        "steps": [_step(index + 1) for index in range(steps)],
        "terminal_checkpoint": _terminal(),
        "seal": {"canonicalization": "semantic-canonical-1.0.0"},
    }
    base.update(overrides)
    return base


def test_equal_traces_match():
    result = compare_tapes(_tape(), _tape())
    assert result.match is True
    assert result.divergence is None
    assert result.compared_steps == 3


def test_event_mismatch_classified():
    actual = _tape()
    actual["steps"][1]["event_digest"] = "0" * 64
    result = compare_tapes(_tape(), actual)
    assert result.match is False
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.EVENT_MISMATCH
    assert result.divergence.record_index == 1
    assert result.divergence.decision_offset == 2
    assert result.divergence.actor_principal == 1
    assert len(result.divergence.context_window) == 1


def test_legal_action_set_mismatch_classified():
    actual = _tape()
    actual["steps"][0]["legal_set_digest"] = "0" * 64
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.LEGAL_ACTION_SET_MISMATCH
    assert result.divergence.record_index == 0


def test_numeric_domain_mismatch_classified_as_legal_set():
    expected = _tape()
    actual = _tape()
    for tape, upper in ((expected, 5), (actual, 6)):
        tape["steps"][0].update(
            {
                "decision_class": "announce_x",
                "selected_fingerprints": [],
                "numeric_choice": 3,
                "numeric_min": 0,
                "numeric_max": upper,
            }
        )
    result = compare_tapes(expected, actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.LEGAL_ACTION_SET_MISMATCH


def test_rng_mismatch_classified():
    actual = _tape()
    actual["steps"][2]["rng_calls_after"] = 11
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.RULES_RNG_MISMATCH
    assert result.divergence.record_index == 2


def test_rng_contract_mismatch_classified():
    actual = _tape()
    actual["rng_contract"]["root_rules_seed"] = 999
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.RULES_RNG_MISMATCH
    assert result.divergence.record_index == -1


def test_public_state_mismatch_classified():
    actual = _tape()
    actual["steps"][0]["principal_observation_digest"] = "0" * 64
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.PUBLIC_STATE_MISMATCH


def test_terminal_mismatch_classified():
    actual = _tape()
    actual["terminal_checkpoint"] = _terminal(public_state_digest="0" * 64)
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.TERMINAL_OUTCOME_MISMATCH
    assert result.divergence.record_index == 3


def test_terminal_outcome_mismatch_classified():
    actual = _tape()
    actual["terminal_checkpoint"]["outcomes"][0]["won"] = False
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.TERMINAL_OUTCOME_MISMATCH


def test_initial_state_mismatch_classified():
    actual = _tape()
    actual["game_manifest"]["rules_seed"] = 999
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.INITIAL_STATE_MISMATCH
    assert result.divergence.record_index == -1


def test_full_manifest_mismatch_classified():
    actual = _tape()
    actual["game_manifest"]["seat_principals"][0]["pilot_identity"] = "other-pilot"
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.INITIAL_STATE_MISMATCH


def test_early_termination_classified():
    actual = _tape(steps=2)
    result = compare_tapes(_tape(steps=3), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.EARLY_TERMINATION
    assert result.divergence.record_index == 2


def test_decision_identity_mismatch_classified():
    actual = _tape()
    actual["steps"][1]["actor_principal"] = 2
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.DECISION_IDENTITY_MISMATCH


def test_irrelevant_label_difference_normalizes_to_match():
    expected = _tape()
    actual = _tape()
    actual["steps"][0]["selected_labels"] = ["Different display-only label"]
    result = compare_tapes(expected, actual)
    assert result.match is True


def test_meaningful_digest_difference_must_not_normalize():
    actual = _tape()
    actual["steps"][0]["legal_set_digest"] = actual["steps"][0]["principal_observation_digest"]
    result = compare_tapes(_tape(), actual)
    assert result.match is False
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.LEGAL_ACTION_SET_MISMATCH


def test_provider_failure_on_malformed_tape():
    actual = _tape()
    del actual["tape_id"]
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.PROVIDER_FAILURE


def test_provider_failure_on_unsupported_schema():
    actual = _tape()
    actual["schema_version"] = "semantic-replay-tape/9.9.9"
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.PROVIDER_FAILURE


def test_real_xmage_same_seed_tape_pair(repo_root: Path):
    tape_path = repo_root / "qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-4p.json"
    tape = json.loads(tape_path.read_text())
    assert len(tape["steps"]) > 100
    matched = compare_tapes(copy.deepcopy(tape), copy.deepcopy(tape))
    assert matched.match is True
    assert matched.compared_steps == len(tape["steps"])

    mutated = copy.deepcopy(tape)
    target = 40
    mutated["steps"][target]["event_digest"] = "0" * 64
    diverged = compare_tapes(tape, mutated)
    assert diverged.match is False
    assert diverged.divergence is not None
    assert diverged.divergence.kind == DivergenceKind.EVENT_MISMATCH
    assert diverged.divergence.record_index == target
    assert diverged.divergence.decision_offset == tape["steps"][target]["decision_revision"]
    assert diverged.divergence.actor_principal == tape["steps"][target]["actor_principal"]
    assert diverged.divergence.expected_provider == "xmage"
    assert len(diverged.divergence.context_window) == 3
