"""Principal scoping must be validated before an observation is persisted.

The hidden-information loop read one state observation per seat and wrote all
four straight into the artifact, with nothing checking that each response was
scoped to the seat that asked. The committed XMage run shows what that permits:
all four entries held byte-identical state payloads, including stable object ids
and ordering for every opponent's hand and library. One unscoped view was
presented as four scoped ones.

Masking identifiers at the provider is necessary but not sufficient, because a
provider can return the same unscoped payload to every caller. The observation has
to be checked where it is trusted, which is here.
"""

from __future__ import annotations

from pathlib import Path

from commander_lab.qualification.current_boundary.full107 import validate_principal_scoping

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"
SEATS = ("p1", "p2", "p3", "p4")


def _scoped(actor_seat: int, *, hand: list | None = None) -> dict:
    """A well-formed principal view: counts only, own content only."""
    return {
        "players": [
            {
                "seat": index,
                "is_actor": index == actor_seat,
                "hand_count": 7,  # counts are public, so every seat shows one
                "library_count": 92,
                "hand": hand if index == actor_seat else None,
            }
            for index in range(4)
        ]
    }


def _good() -> dict[str, dict]:
    return {seat: _scoped(index) for index, seat in enumerate(SEATS)}


def test_genuinely_scoped_observations_pass() -> None:
    result = validate_principal_scoping(_good(), requested_seats=SEATS)
    assert result["verdict"] == "PRINCIPAL_SCOPED"
    assert result["credible_as_principal_scoped_evidence"] is True
    assert result["findings"] == []
    assert result["distinct_payloads"] == 4


def test_identical_payloads_for_every_principal_are_rejected() -> None:
    """The exact committed-run failure."""
    shared = _scoped(0)
    observations = {seat: dict(shared) for seat in SEATS}
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["verdict"] == "SCOPING_NOT_ESTABLISHED"
    assert result["credible_as_principal_scoped_evidence"] is False
    assert result["distinct_payloads"] == 1
    assert any("byte-identical" in finding["detail"] for finding in result["findings"]), result[
        "findings"
    ]


def test_opponent_hand_content_is_rejected() -> None:
    """A view that exposes another seat's hand is not principal-scoped."""
    observations = _good()
    observations["p1"]["players"][2]["hand"] = [
        {"object_id": "obj:1", "name": "Black Lotus"},
        {"object_id": "obj:2", "name": "Time Walk"},
    ]
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False
    assert any(finding["check"] == "no_opponent_hidden_content" for finding in result["findings"])


def test_opponent_library_content_is_rejected() -> None:
    observations = _good()
    observations["p2"]["players"][3]["library"] = [{"object_id": "obj:x", "name": "Lotus"}]
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False


def test_actor_must_be_the_requester() -> None:
    """p1 asking and receiving p2's view is a scoping failure."""
    observations = _good()
    observations["p1"] = _scoped(1)  # p1 gets the seat-1 view
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False
    assert any(finding["check"] == "actor_is_the_requester" for finding in result["findings"])


def test_ambiguous_actor_marking_is_rejected() -> None:
    observations = _good()
    observations["p3"]["players"][0]["is_actor"] = True
    observations["p3"]["players"][3]["is_actor"] = True
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False


def test_no_actor_marked_at_all_is_rejected() -> None:
    observations = _good()
    for entry in observations["p2"]["players"]:
        entry["is_actor"] = False
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False


def test_missing_observation_is_rejected() -> None:
    observations = _good()
    del observations["p3"]
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False
    assert any(finding["check"] == "observation_present" for finding in result["findings"])


def test_error_responses_do_not_count_as_observations() -> None:
    observations = _good()
    observations["p4"] = {"error": "no such game"}
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False


def test_players_absent_is_rejected() -> None:
    result = validate_principal_scoping({"p1": {"turn_number": 1}}, requested_seats=("p1",))
    assert result["credible_as_principal_scoped_evidence"] is False


def test_runner_validates_before_persisting() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "validate_principal_scoping" in source
    assert "principal_scoping" in source
    assert "principal_observations_credible" in source
    # Validation must happen before the artifact is written.
    assert source.index("validate_principal_scoping(") < source.index(
        'f"HIDDEN_INFO_{candidate.upper()}.json"'
    )
    # And an unscoped result must be reported, not silently persisted.
    assert "principal scoping not established" in source
