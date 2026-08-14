from __future__ import annotations

import json

from commander_lab.repositories.opponents import CurrentOpponentRepository


def test_current_opponent_repository_is_single_registry_projection(repo_root) -> None:
    registry = json.loads(
        (repo_root / "data/opponents/opponent_registry.json").read_text(encoding="utf-8")
    )
    repository = CurrentOpponentRepository(repo_root)

    assert set(repository.current_deck_ids()) == set(registry["current"].values())
    assert len(repository.current_deck_ids()) == 8
    assert "opponent/lorehold-spirit-precon" in repository.current_deck_ids()
    assert "kaervek/current" in repository.current_deck_ids()
    assert set(repository.profiles()) == set(repository.current_deck_ids())


def test_opponent_evidence_and_frozen_kaervek_are_preserved(repo_root) -> None:
    repository = CurrentOpponentRepository(repo_root)
    records = {record.deck_id: record for record in repository.records()}

    assert records["kaervek/current"].frozen is True
    assert "verified_full_deck" in {
        kind.value for kind in records["kaervek/current"].evidence_kinds
    }
    assert records["opponent/lorehold-spirit-precon"].frozen is False
    assert "official_precon" in {
        kind.value for kind in records["opponent/lorehold-spirit-precon"].evidence_kinds
    }
    assert "partially_observed" in {
        kind.value for kind in records["opponent/morcant-elves"].evidence_kinds
    }


def test_service_robustness_fallback_uses_repository_before_synthetic(repo_root) -> None:
    from commander_lab.tools import CommanderToolService

    service = CommanderToolService(repo_root)
    current = CurrentOpponentRepository(repo_root).current_deck_ids()
    pod = service._opponent_pod_for_size((), 8)

    assert len(pod) == 7
    assert set(pod) <= set(current)
    assert "opponent/lorehold-spirit-precon" in pod
    assert not any(deck_id.startswith("synthetic/") for deck_id in pod)


def test_default_pilot_reference_pod_is_balanced_scheduler_output(repo_root) -> None:
    from commander_lab.tools import CommanderToolService

    service = CommanderToolService(repo_root)
    first = service._balanced_reference_opponents((), seed=20260814)
    second = service._balanced_reference_opponents((), seed=20260814)
    current = set(CurrentOpponentRepository(repo_root).current_deck_ids())

    assert first == second
    assert len(first) == 3
    assert len(set(first)) == 3
    assert set(first) <= current
