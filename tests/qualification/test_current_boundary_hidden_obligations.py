"""Per-obligation PB-06 hidden-information disposition.

These tests pin the two properties that matter for evidence integrity:

1. The assessor never credits an obligation the observations do not actually
   support. A correct implementation must FAIL on a leak, on a missing count,
   and on uncredible principal scoping.
2. It never credits an obligation from a different obligation's evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary.full107 import (
    _zone_exposes_content,
)
from commander_lab.qualification.current_boundary.hidden_obligations import (
    NOT_OBSERVABLE,
    SATISFIED,
    assess_hidden_obligations,
    load_catalog,
)

CATALOG = Path("qualification/obligations/QUALIFICATION_OBLIGATION_CATALOG_v1.json")
SEATS = ("p1", "p2", "p3", "p4")


def _observation(
    observer: str,
    *,
    actor_seat: int,
    player_ids: dict[str, str],
    hand_for_actor: list[str] | None = None,
    hand_masked: str = "<hidden>",
    library: list[str] | None = None,
    is_actor_marker: bool = True,
) -> dict[str, Any]:
    """A principal-scoped observation with correct XMage-style scoping."""
    players: list[dict[str, Any]] = []
    for index, seat in enumerate(("p1", "p2", "p3", "p4")):
        entry: dict[str, Any] = {
            "player_id": player_ids[seat],
            "seat": index,
            "zones": {
                "hand": (list(hand_for_actor) if index == actor_seat else [hand_masked] * 7),
                "library": (list(library) if library is not None else ["<hidden>"] * 92),
            },
        }
        if is_actor_marker and index == actor_seat:
            entry["is_actor"] = True
        players.append(entry)
    return {
        "observer_player_id": observer,
        "observer_seat": actor_seat,
        "observer_engine_player_id": player_ids[observer],
        "state": {
            "game_id": "g",
            "players": players,
            "step": "upkeep",
            # Priority is a legitimate per-principal difference, so the four
            # state views are distinct for a reason unrelated to hidden zones.
            # Without it a fully-masked hand would make the views byte-identical
            # and the scoping validator would reject them for a different cause.
            "priority_player_id": player_ids[observer],
        },
    }


@pytest.fixture()
def observations() -> dict[str, Any]:
    ids = {"p1": "id-1", "p2": "id-2", "p3": "id-3", "p4": "id-4"}
    return {
        seat: _observation(seat, actor_seat=index, player_ids=ids, hand_for_actor=["c"] * 7)
        for index, seat in enumerate(SEATS)
    }


@pytest.fixture()
def catalog() -> list[dict[str, Any]]:
    return load_catalog(CATALOG)


def test_catalog_has_the_full_hidden_family(catalog: list[dict[str, Any]]) -> None:
    hidden = [o for o in catalog if str(o.get("obligation_id", "")).startswith("HIDDEN")]
    assert len(hidden) == 20


def test_every_catalogued_obligation_gets_a_disposition(
    observations: dict[str, Any], catalog: list[dict[str, Any]]
) -> None:
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    hidden = {o["obligation_id"] for o in catalog if o["obligation_id"].startswith("HIDDEN")}
    assert set(out["dispositions"]) == hidden
    assert out["counts"]["total"] == 20
    for obligation_id, entry in out["dispositions"].items():
        assert entry["disposition"] in {SATISFIED, NOT_OBSERVABLE}, obligation_id
        assert entry["reason"], obligation_id


def test_correct_scoping_satisfies_the_two_projection_stated_obligations(
    observations: dict[str, Any], catalog: list[dict[str, Any]]
) -> None:
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    dispositions = out["dispositions"]
    assert dispositions["HIDDEN_01"]["disposition"] == SATISFIED
    assert dispositions["HIDDEN_02"]["disposition"] == SATISFIED
    assert out["counts"][SATISFIED] == 2


def test_per_scenario_obligations_are_never_credited_from_generic_scoping(
    observations: dict[str, Any], catalog: list[dict[str, Any]]
) -> None:
    """Correct hand masking must not be treated as proof of other channels.

    HIDDEN_04 (face-down permanent controller sees identity) and HIDDEN_07
    (reveal reaches exactly the legal audience) are different channels from
    opponent-hand masking. Crediting them here would be evidence laundering.
    """
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    for obligation_id in ("HIDDEN_04", "HIDDEN_07", "HIDDEN_18", "HIDDEN_19"):
        assert out["dispositions"][obligation_id]["disposition"] == NOT_OBSERVABLE


def test_an_unmasked_opponent_hand_is_never_a_pass(
    catalog: list[dict[str, Any]],
) -> None:
    ids = {"p1": "id-1", "p2": "id-2", "p3": "id-3", "p4": "id-4"}
    observations = {
        seat: _observation(seat, actor_seat=index, player_ids=ids, hand_for_actor=["c"] * 7)
        for index, seat in enumerate(SEATS)
    }
    # p1 is shown its opponent's real card.
    observations["p1"]["state"]["players"][1]["zones"]["hand"] = ["LEAKED-CARD"]
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    assert out["dispositions"]["HIDDEN_01"]["disposition"] == NOT_OBSERVABLE
    assert "non-actor" in out["dispositions"]["HIDDEN_01"]["reason"]


def test_a_missing_count_is_not_identity_absence(catalog: list[dict[str, Any]]) -> None:
    """HIDDEN_02 requires the count to remain; an empty library proves nothing."""
    ids = {"p1": "id-1", "p2": "id-2", "p3": "id-3", "p4": "id-4"}
    observations = {
        seat: _observation(
            seat, actor_seat=index, player_ids=ids, hand_for_actor=["c"] * 7, library=[]
        )
        for index, seat in enumerate(SEATS)
    }
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    assert out["dispositions"]["HIDDEN_02"]["disposition"] == NOT_OBSERVABLE
    assert "count" in out["dispositions"]["HIDDEN_02"]["reason"]


def test_an_observer_that_cannot_see_its_own_hand_is_not_a_pass(
    catalog: list[dict[str, Any]],
) -> None:
    ids = {"p1": "id-1", "p2": "id-2", "p3": "id-3", "p4": "id-4"}
    observations = {
        seat: _observation(
            seat,
            actor_seat=index,
            player_ids=ids,
            hand_for_actor=["<hidden>"] * 7,
            is_actor_marker=True,
        )
        for index, seat in enumerate(SEATS)
    }
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    assert out["dispositions"]["HIDDEN_01"]["disposition"] == NOT_OBSERVABLE
    assert "own" in out["dispositions"]["HIDDEN_01"]["reason"]


def test_uncredible_scoping_grants_no_credit_anywhere(
    catalog: list[dict[str, Any]],
) -> None:
    """An unscoped projection must credit nothing, not even a true obligation.

    If every requester receives the same view, a single principal's
    hand/library scoping proves nothing about the projection as a whole.
    """
    ids = {"p1": "id-1", "p2": "id-2", "p3": "id-3", "p4": "id-4"}
    shared = _observation("p1", actor_seat=0, player_ids=ids, hand_for_actor=["c"] * 7)
    observations = {seat: json.loads(json.dumps(shared)) for seat in SEATS}
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    assert out["counts"][SATISFIED] == 0
    assert out["counts"][NOT_OBSERVABLE] == 20
    assert out["principal_scoping_credible"] is False


def test_satisfied_disposition_does_not_claim_to_flip_a_row(
    observations: dict[str, Any], catalog: list[dict[str, Any]]
) -> None:
    """A SATISFIED disposition must not be presented as a row promotion."""
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    assert "does not itself flip a FULL107 row" in out["promotion_note"]


def test_partial_masking_is_not_a_pass(catalog: list[dict[str, Any]]) -> None:
    """Five masked entries beside one real one is still a leak."""
    ids = {"p1": "id-1", "p2": "id-2", "p3": "id-3", "p4": "id-4"}
    observations = {
        seat: _observation(seat, actor_seat=index, player_ids=ids, hand_for_actor=["c"] * 7)
        for index, seat in enumerate(SEATS)
    }
    observations["p1"]["state"]["players"][1]["zones"]["hand"] = ["<hidden>"] * 6 + ["REAL"]
    out = assess_hidden_obligations(observations, catalog=catalog, requested_seats=SEATS)
    assert out["dispositions"]["HIDDEN_01"]["disposition"] == NOT_OBSERVABLE


def test_placeholder_handling_matches_the_established_primitive() -> None:
    """The assessor must reuse, not re-derive, redaction semantics."""
    assert _zone_exposes_content(["<hidden>", "<hidden>"]) is False
    assert _zone_exposes_content(["<hidden>", "real-card"]) is True
    assert _zone_exposes_content([]) is False


def test_missing_observations_credit_nothing(catalog: list[dict[str, Any]]) -> None:
    out = assess_hidden_obligations({}, catalog=catalog, requested_seats=SEATS)
    assert out["counts"][SATISFIED] == 0
    assert out["counts"][NOT_OBSERVABLE] == 20


# ---------------------------------------------------------------------------
# The persisted PB-06 evidence artifacts must be internally consistent and
# must never overstate what the observations establish.
# ---------------------------------------------------------------------------

ARTIFACTS = (
    "qualification/final-current-boundary-20260927/PB06_HIDDEN_OBLIGATIONS_XMAGE.json",
    "qualification/final-current-boundary-20260927/PB06_HIDDEN_OBLIGATIONS_FORGE.json",
)


@pytest.mark.parametrize("relative", ARTIFACTS)
def test_persisted_artifact_covers_every_hidden_obligation(relative: str) -> None:
    document = json.loads(Path(relative).read_text(encoding="utf-8"))
    catalog = load_catalog(CATALOG)
    expected = {o["obligation_id"] for o in catalog if o["obligation_id"].startswith("HIDDEN")}
    assert set(document["dispositions"]) == expected
    assert document["counts"]["total"] == 20
    assert (
        document["counts"][SATISFIED] + document["counts"][NOT_OBSERVABLE]
        == document["counts"]["total"]
    )


@pytest.mark.parametrize("relative", ARTIFACTS)
def test_persisted_artifact_claims_no_row_promotion(relative: str) -> None:
    document = json.loads(Path(relative).read_text(encoding="utf-8"))
    assert "does not itself flip a FULL107 row" in document["promotion_note"]
    # A satisfied obligation must be labelled as observed, not merely asserted.
    # An unestablished one may carry evidence_class=UNKNOWN (e.g. a candidate
    # that returns no library count), but must never claim anything stronger.
    allowed = {"DIRECTLY_VERIFIED", "UNKNOWN", "CODE_DERIVED"}
    for obligation_id, entry in document["dispositions"].items():
        if entry["disposition"] == SATISFIED:
            assert entry["evidence_class"] == "DIRECTLY_VERIFIED", obligation_id
        else:
            assert entry.get("evidence_class", "UNKNOWN") in allowed, obligation_id


@pytest.mark.parametrize("relative", ARTIFACTS)
def test_persisted_artifact_only_credits_projection_stated_obligations(
    relative: str,
) -> None:
    """Guard the boundary: only HIDDEN_01/02 may ever be credited this way.

    If a future edit credits a per-scenario channel from generic scoping, that
    is evidence laundering and this test fails.
    """
    document = json.loads(Path(relative).read_text(encoding="utf-8"))
    satisfied = {
        obligation_id
        for obligation_id, entry in document["dispositions"].items()
        if entry["disposition"] == SATISFIED
    }
    assert satisfied <= {"HIDDEN_01", "HIDDEN_02"}, satisfied
