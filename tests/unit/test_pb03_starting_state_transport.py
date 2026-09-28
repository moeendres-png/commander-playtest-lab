"""PB-03: the Lab half of the starting-state transport contract.

The engine-side transport is qualified in the bridge module. These tests qualify
the Lab half, and they are deliberately about the CONTRACT rather than about Magic
semantics: the Lab forwards a frozen semantic record the fixture already owns, the
engine interprets and materialises it, and the Lab verifies only the facts the
engine reports.

The assertions that matter most are the fail-closed ones. A requested state the
engine silently ignored would be the worst possible outcome, because the fixture
would then claim a starting state it never got.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    verify_starting_state_binding,
)

XMAGE_COMMIT = "b19596980f2734496ea1896504253e1bdd2756dd"
EVIDENCE_CLASS = "xmage_full_game_technical_conformance"
PLAN_ID = "pb03-lab-transport"


def _deck(index: int) -> object:
    class _Deck:
        deck_id = f"deck-{index}"
        deck_hash = f"{index:064x}"

    return _Deck()


def _scenario(player_count: int = 2, starting_state: dict | None = None) -> FutureXmageScenario:
    decks = [_deck(index) for index in range(1, player_count + 1)]
    return FutureXmageScenario(
        candidate_id="deck-1",  # type: ignore[arg-type]
        deck_hash="0" * 64,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),  # type: ignore[attr-defined]
        player_count=player_count,  # type: ignore[arg-type]
        seat=1,
        scenario_id="pb03-lab-transport",
        seed=424242,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
        starting_state=starting_state,
    )


def _create_response(
    *,
    requested: bool = False,
    request_digest: str | None = None,
    observed_digest: str | None = None,
) -> dict:
    return {
        "player_count": 2,
        "seed": 424242,
        "evidence_class": EVIDENCE_CLASS,
        "holdout_consumed": False,
        "starting_state_requested": requested,
        "requested_starting_state_digest": request_digest,
        "observed_starting_state_digest": observed_digest,
        "starting_state_readback_observed": observed_digest is not None,
    }


def _guard(requested: bool, create_response: dict) -> None:
    """Call the PRODUCTION guard, not a copy of it.

    An earlier version of this file re-implemented the checks, which meant it was
    testing its own transcription rather than the code that ships. These tests
    exercise the real function so a change to the guard cannot leave them green.
    """
    verify_starting_state_binding(requested, create_response)


def test_scenario_defaults_to_requesting_no_starting_state() -> None:
    scenario = _scenario()
    assert scenario.starting_state is None, (
        "absence must be the default; an implicit starting state would let a "
        "fixture claim a state it never asked for"
    )


def test_scenario_carries_an_explicit_requested_starting_state() -> None:
    record = {"plan_id": PLAN_ID, "player_count": 2, "players": []}
    scenario = _scenario(starting_state=record)
    assert scenario.starting_state == record
    assert scenario.starting_state["plan_id"] == PLAN_ID


def test_scenario_rejects_a_non_object_starting_state() -> None:
    with pytest.raises(ValidationError):
        _scenario(starting_state=["not", "an", "object"])  # type: ignore[arg-type]


def test_a_honoured_request_is_accepted() -> None:
    _guard(
        True,
        _create_response(requested=True, request_digest="a" * 64, observed_digest="b" * 64),
    )


def test_a_silently_ignored_request_fails_closed() -> None:
    """The worst case: the engine accepts the request and quietly does nothing."""
    with pytest.raises(FullGameConformanceError, match="did not report restoring"):
        _guard(True, _create_response(requested=False, observed_digest="b" * 64))


def test_a_request_with_no_readback_fails_closed() -> None:
    with pytest.raises(FullGameConformanceError, match="authoritative readback"):
        _guard(True, _create_response(requested=True, request_digest="a" * 64))


def test_a_readback_with_no_request_digest_fails_closed() -> None:
    """A readback that cannot be tied to what was asked verifies nothing."""
    with pytest.raises(FullGameConformanceError, match="request digest"):
        _guard(True, _create_response(requested=True, observed_digest="b" * 64))


def test_an_unrequested_restoration_fails_closed() -> None:
    """No state was asked for, so the engine must report restoring none."""
    with pytest.raises(FullGameConformanceError, match="never requested"):
        _guard(False, _create_response(requested=True, request_digest="a" * 64))


def test_lab_sends_the_starting_state_verbatim_and_never_interprets_it() -> None:
    """The Lab forwards the record; it does not build or edit engine state."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "src/commander_lab/engine/rules/full_game.py"
    ).read_text(encoding="utf-8")

    # The record is passed straight through, so the Lab cannot be shaping it.
    assert 'create_payload["starting_state"] = scenario.starting_state' in source
    # The Lab asserts engine-reported facts only. If it ever computed a zone, a
    # count or a digest of its own, that would be a second state model.
    assert "observed_starting_state_digest" in source
    assert "requested_starting_state_digest" in source
    for forbidden in ("zones", "hand_count", "library_count", "permutation"):
        assert forbidden not in source.split("PB-03: request the starting state")[1][:2000], (
            f"the Lab must not interpret Magic state; found {forbidden!r} near the "
            "starting-state request"
        )
