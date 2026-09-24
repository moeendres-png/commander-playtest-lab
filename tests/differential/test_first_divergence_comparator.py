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


def _manifest(**overrides):
    base = {"player_count": 4, "rules_seed": 424242, "starting_life": 40}
    base.update(overrides)
    return base


def _checkpoint(**overrides):
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
        "principal_digests": {"1": "c" * 64},
    }
    base.update(overrides)
    return base


def _step(sequence, **overrides):
    base = {
        "sequence": sequence,
        "decision_class": "priority",
        "actor_principal": 1,
        "decision_revision": sequence,
        "legal_set_digest": "d" * 64,
        "legal_set_size": 1,
        "selected_fingerprints": ["fp-pass"],
        "rng_calls_before": 10,
        "rng_calls_after": 10,
        "event_digest": "e" * 64,
        "principal_observation_digest": "f" * 64,
    }
    base.update(overrides)
    return base


def _tape(steps=3, **overrides):
    base = {
        "tape_id": "tape-test",
        "schema_version": "semantic-replay-tape/1.0.0",
        "source_lock": {"provider_identity": "xmage"},
        "game_manifest": _manifest(),
        "initial_checkpoint": _checkpoint(),
        "steps": [_step(i + 1) for i in range(steps)],
        "terminal_checkpoint": _checkpoint(decision_sequence=3 + steps),
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


def test_rng_mismatch_classified():
    actual = _tape()
    actual["steps"][2]["rng_calls_after"] = 11
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.RULES_RNG_MISMATCH
    assert result.divergence.record_index == 2


def test_public_state_mismatch_classified():
    actual = _tape()
    actual["steps"][0]["principal_observation_digest"] = "0" * 64
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.PUBLIC_STATE_MISMATCH


def test_terminal_mismatch_classified():
    actual = _tape()
    actual["terminal_checkpoint"] = _checkpoint(public_state_digest="0" * 64)
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.TERMINAL_OUTCOME_MISMATCH
    assert result.divergence.record_index == 3


def test_initial_state_mismatch_classified():
    actual = _tape()
    actual["game_manifest"] = _manifest(rules_seed=999)
    result = compare_tapes(_tape(), actual)
    assert result.divergence is not None
    assert result.divergence.kind == DivergenceKind.INITIAL_STATE_MISMATCH
    assert result.divergence.record_index == -1


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
    actual["steps"][0]["selected_labels"] = ["Pass priority"]
    actual["seal"] = {"different": "process-local-metadata"}
    result = compare_tapes(expected, actual)
    assert result.match is True


def test_meaningful_digest_difference_must_not_normalize():
    actual = _tape()
    actual["steps"][0]["legal_set_digest"] = actual["steps"][0][
        "principal_observation_digest"
    ]
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


def test_real_xmage_same_seed_tape_pair(repo_root: Path):
    tape_path = (
        repo_root / "qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-4p.json"
    )
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
    assert diverged.divergence.decision_offset == tape["steps"][target][
        "decision_revision"
    ]
    assert diverged.divergence.actor_principal == tape["steps"][target][
        "actor_principal"
    ]
    assert diverged.divergence.expected_provider == "xmage"
    assert len(diverged.divergence.context_window) == 3
