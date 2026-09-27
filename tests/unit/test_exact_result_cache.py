from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from commander_lab.storage import (
    ExactResultCache,
    ResultCacheCorruptionError,
    build_exact_result_identity,
)


def _identity(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "engine_version": "structural-test-v1",
        "deck_hashes": ["baseline-hash", "variant-hash"],
        "opponent_hashes": ["opp-a", "opp-b", "opp-c"],
        "pilot_hashes": ["pilot-strong"],
        "canonical_context_snapshot": "context-a",
        "scenario": {"pod": "primary_4p_rogshai", "starting_player_seat": None},
        "simulation_config": {"iterations": 8, "max_turns": 14, "pair_id": "pair-a"},
        "exact_seed_set": [11, 12, 13, 14, 15, 16, 17, 18],
        "policy_config_hashes": {"pilot": "pilot-strong", "optimizer": "optimizer-a"},
    }
    payload.update(overrides)
    return build_exact_result_identity(**payload)  # type: ignore[arg-type]


def test_identical_request_is_a_read_through_cache_hit(tmp_path: Path) -> None:
    cache = ExactResultCache(tmp_path / "lab.sqlite3", root=tmp_path)
    calls = 0

    def compute() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"paired": {"placement_improvement": 0.25}, "pair_count": 8}

    first = cache.get_or_compute(
        _identity(), evidence_class="structural_model_estimates", compute=compute
    )
    second = cache.get_or_compute(
        _identity(), evidence_class="structural_model_estimates", compute=compute
    )
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls == 1
    assert second.result == first.result
    assert second.evidence_class == "structural_model_estimates"


@pytest.mark.parametrize(
    "changed",
    [
        {"deck_hashes": ["baseline-hash", "changed-variant"]},
        {"pilot_hashes": ["changed-pilot"]},
        {"opponent_hashes": ["opp-a", "changed-opp", "opp-c"]},
        {"exact_seed_set": [21, 22, 23, 24, 25, 26, 27, 28]},
        {"engine_version": "structural-test-v2"},
        {"canonical_context_snapshot": "context-b"},
        {"policy_config_hashes": {"pilot": "pilot-strong", "optimizer": "optimizer-b"}},
    ],
)
def test_any_material_identity_change_is_a_cache_miss(
    tmp_path: Path, changed: dict[str, object]
) -> None:
    cache = ExactResultCache(tmp_path / "lab.sqlite3", root=tmp_path)
    cache.put(
        _identity(),
        {"paired": {"placement_improvement": 0.25}},
        evidence_class="structural_model_estimates",
    )
    assert cache.get(_identity(**changed)) is None


def test_corrupted_cached_result_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "lab.sqlite3"
    cache = ExactResultCache(database, root=tmp_path)
    identity = _identity()
    stored = cache.put(
        identity,
        {"paired": {"placement_improvement": 0.25}},
        evidence_class="structural_model_estimates",
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE result_cache SET result_hash='corrupt' WHERE cache_key=?",
            (stored.cache_key,),
        )
        connection.commit()
    with pytest.raises(ResultCacheCorruptionError, match="result hash mismatch"):
        cache.get(identity)


def test_evidence_class_cannot_change_on_cache_hit(tmp_path: Path) -> None:
    cache = ExactResultCache(tmp_path / "lab.sqlite3", root=tmp_path)
    identity = _identity()
    cache.put(
        identity,
        {"paired": {"placement_improvement": 0.25}},
        evidence_class="structural_model_estimates",
    )
    with pytest.raises(ResultCacheCorruptionError, match="evidence class differs"):
        cache.get_or_compute(
            identity,
            evidence_class="external_rules_engine_results",
            compute=lambda: {"should_not": "run"},
        )
