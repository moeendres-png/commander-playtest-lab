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

import copy
from pathlib import Path

from commander_lab.qualification.current_boundary.full107 import validate_principal_scoping

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"
SEATS = ("p1", "p2", "p3", "p4")


def _scoped(actor_seat: int, *, hand: list | None = None) -> dict:
    """A well-formed principal view: counts only, own content only.

    This mirrors the real observation shape, which nests the state under
    ``state`` and zone content under ``zones``. Reading the top level instead
    produced a false finding against a correctly shaped response, which is as
    bad as missing a real leak.
    """
    return {
        "state_observation_offset": 1,
        "state": {
            "players": [
                {
                    "seat": index,
                    "is_actor": index == actor_seat,
                    "life": 40,
                    "zones": {
                        "hand": hand if index == actor_seat else [],
                        "library": [],
                    },
                }
                for index in range(4)
            ]
        },
    }


def test_state_nesting_is_read_not_the_envelope() -> None:
    """The state lives under `state`; the envelope must not be mistaken for it."""
    result = validate_principal_scoping(_good(), requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is True, result["findings"]


def test_monotonic_offset_cannot_mask_an_identical_state() -> None:
    """A real trap: the envelope differs by offset while the state is identical.

    Comparing the whole observation made four byte-identical states look like
    four distinct ones, which is precisely the leak this check exists to catch.
    """
    shared = _scoped(0, hand=[{"object_id": "obj:1", "name": "Black Lotus"}])
    observations = {}
    for index, seat in enumerate(SEATS):
        entry = dict(shared)
        entry["state_observation_offset"] = 2 + index
        observations[seat] = entry
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["distinct_state_views"] == 1
    assert result["credible_as_principal_scoped_evidence"] is False
    assert any(
        finding["check"] == "observations_differ_per_principal" for finding in result["findings"]
    )


def test_engine_leak_is_attributed_to_the_candidate() -> None:
    """The Lab must not mask a candidate leak and then award it credit."""
    shared = _scoped(0)
    observations = {seat: dict(shared) for seat in SEATS}
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["attribution"] == "ENGINE_CANDIDATE_DEFECT"


def test_exposed_zones_are_named_in_the_attribution() -> None:
    """A NON-actor's hand is what makes it a leak, and it must be named."""
    # seat 0 is the actor and holds a hand; seat 2 is a non-actor and must not.
    shared = _scoped(0, hand=[{"object_id": "obj:1"}])
    shared["state"]["players"][2]["zones"]["hand"] = [{"object_id": "obj:2"}]
    observations = {seat: dict(shared) for seat in SEATS}
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert "hand" in result["engine_leak_indicators"]
    assert result["attribution"] == "ENGINE_CANDIDATE_DEFECT"


def test_clean_observations_are_attributed_to_nobody() -> None:
    assert validate_principal_scoping(_good(), requested_seats=SEATS)["attribution"] == "NONE"


def _good() -> dict[str, dict]:
    return {seat: _scoped(index) for index, seat in enumerate(SEATS)}


def test_genuinely_scoped_observations_pass() -> None:
    result = validate_principal_scoping(_good(), requested_seats=SEATS)
    assert result["verdict"] == "PRINCIPAL_SCOPED"
    assert result["credible_as_principal_scoped_evidence"] is True
    assert result["findings"] == []
    assert result["distinct_state_views"] == 4


def test_identical_payloads_for_every_principal_are_rejected() -> None:
    """The exact committed-run failure."""
    shared = _scoped(0)
    observations = {seat: dict(shared) for seat in SEATS}
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["verdict"] == "SCOPING_NOT_ESTABLISHED"
    assert result["credible_as_principal_scoped_evidence"] is False
    assert result["distinct_state_views"] == 1
    assert any("byte-identical" in finding["detail"] for finding in result["findings"]), result[
        "findings"
    ]


def test_opponent_hand_content_is_rejected() -> None:
    """A view that exposes another seat's hand is not principal-scoped."""
    observations = _good()
    observations["p1"]["state"]["players"][2]["zones"]["hand"] = [
        {"object_id": "obj:1", "name": "Black Lotus"},
        {"object_id": "obj:2", "name": "Time Walk"},
    ]
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False
    assert any(finding["check"] == "no_opponent_hidden_content" for finding in result["findings"])


def test_opponent_library_content_is_rejected() -> None:
    observations = _good()
    observations["p2"]["state"]["players"][3]["zones"]["library"] = [
        {"object_id": "obj:x", "name": "Lotus"}
    ]
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
    observations["p3"]["state"]["players"][0]["is_actor"] = True
    observations["p3"]["state"]["players"][3]["is_actor"] = True
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False


def test_no_actor_marked_at_all_is_rejected() -> None:
    observations = _good()
    for entry in observations["p2"]["state"]["players"]:
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


def test_binding_metadata_cannot_fabricate_distinct_views() -> None:
    """A provider cannot earn distinctness by varying only the observer marker.

    The marker binds an observation to its requester; it is not observed
    content. If it counted toward distinctness, one identical unscoped payload
    delivered to four requesters would stop looking byte-identical.
    """
    shared = _scoped(0, hand=[{"object_id": "obj:1", "name": "Black Lotus"}])
    observations = {}
    for index, seat in enumerate(SEATS):
        entry = copy.deepcopy(shared)
        entry["state"]["observer_player_id"] = seat
        for player in entry["state"]["players"]:
            player["is_actor"] = player["seat"] == index
        observations[seat] = entry
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["distinct_state_views"] == 1
    assert any(
        finding["check"] == "observations_differ_per_principal" for finding in result["findings"]
    ), result["findings"]
    assert result["attribution"] == "ENGINE_CANDIDATE_DEFECT"


def test_correctly_scoped_views_with_markers_remain_distinct() -> None:
    observations = _good()
    for index, seat in enumerate(SEATS):
        observations[seat]["state"]["observer_player_id"] = seat
        for player in observations[seat]["state"]["players"]:
            player["is_actor"] = player["seat"] == index
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["distinct_state_views"] == 4
    assert result["verdict"] == "PRINCIPAL_SCOPED"


# ---------------------------------------------------------------------------
# DUAL BINDING SHAPES. Providers expose different but equally authoritative
# principal-binding envelopes, and the validator must accept each on its own terms
# while refusing anything that does not actually establish WHO an observation
# belongs to. These run against real validate_principal_scoping, not source text.
# ---------------------------------------------------------------------------


def _live_engine_envelope(index: int, engine_id: str) -> dict:
    """Mechanism A: requested principal resolved to a live engine id and seat."""
    entry = _good()[SEATS[index]]
    entry["observer_player_id"] = SEATS[index]
    entry["observer_engine_player_id"] = engine_id
    entry["observer_seat"] = index
    entry["state"]["players"][index]["player_id"] = engine_id
    return entry


def _authoritative_marker(index: int) -> dict:
    """Mechanism B: named observer plus exactly one is_actor row, no engine id."""
    entry = _good()[SEATS[index]]
    entry["observer_player_id"] = SEATS[index]
    for player in entry["state"]["players"]:
        player["is_actor"] = player["seat"] == index
    return entry


def test_live_engine_envelope_shape_is_accepted() -> None:
    observations = {
        seat: _live_engine_envelope(index, f"live-{index}") for index, seat in enumerate(SEATS)
    }
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["distinct_state_views"] == 4, result["distinct_state_views"]
    assert result["verdict"] == "PRINCIPAL_SCOPED", result["findings"]


def test_authoritative_state_marker_shape_is_accepted() -> None:
    """A provider that exposes no live engine id is not disqualified for it."""
    observations = {seat: _authoritative_marker(index) for index, seat in enumerate(SEATS)}
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["distinct_state_views"] == 4, result["distinct_state_views"]
    assert result["verdict"] == "PRINCIPAL_SCOPED", result["findings"]
    assert not any(finding["check"] == "observer_binding" for finding in result["findings"]), (
        "a provider presenting only the state marker must not be failed for lacking "
        "an envelope field it never claims"
    )


def test_a_claimed_but_unbound_full_envelope_fails_closed() -> None:
    """Presenting the strong envelope and getting it wrong is a real failure.

    This is the mirror of accepting mechanism B: a provider that claims to resolve
    the principal to a live engine id must have that id match the row at the seat.
    Claiming the strong envelope and mismatching it is not a weaker shape, it is a
    contradictory one.
    """
    observations = {}
    for index, seat in enumerate(SEATS):
        entry = _live_engine_envelope(index, f"live-{index}")
        entry["state"]["players"][index]["player_id"] = "someone-else"
        observations[seat] = entry
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["verdict"] != "PRINCIPAL_SCOPED"
    assert any(finding["check"] == "observer_binding" for finding in result["findings"])


def test_distinct_content_without_any_binding_is_not_accepted() -> None:
    """Distinct payloads prove variation, not per-principal scoping."""
    observations = {}
    for index, seat in enumerate(SEATS):
        entry = _scoped(index, hand=[{"object_id": f"obj:{index}", "name": "Card"}])
        entry["state"].pop("observer_player_id", None)
        for player in entry["state"]["players"]:
            player.pop("is_actor", None)
        observations[seat] = entry
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["verdict"] != "PRINCIPAL_SCOPED"
    assert not result["credible_as_principal_scoped_evidence"]


def test_binding_metadata_alone_never_earns_distinctness() -> None:
    """The required negative control, asserted end to end.

    ONE shared state payload, delivered four times, with only requester-binding
    metadata changed. The content is byte-identical, so four distinct views would
    mean the binding marker is being counted as observed game content. It must not
    be, or a provider could hide a single unscoped projection behind four markers.
    """
    shared = _scoped(0, hand=[{"object_id": "obj:1", "name": "Black Lotus"}])
    observations = {}
    for index, seat in enumerate(SEATS):
        entry = copy.deepcopy(shared)
        # ONLY requester-binding metadata varies. The observed state content is
        # byte-identical across all four, including the live player_id rows, so any
        # distinctness the validator reports would have to come from the markers.
        entry["observer_player_id"] = seat
        entry["observer_seat"] = index
        for player in entry["state"]["players"]:
            player["is_actor"] = player["seat"] == index
        observations[seat] = entry
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["distinct_state_views"] == 1, (
        "varying only requester-binding metadata must not fabricate four distinct views"
    )
    assert any(
        finding["check"] == "observations_differ_per_principal" for finding in result["findings"]
    ), result["findings"]
    assert result["attribution"] == "ENGINE_CANDIDATE_DEFECT"


def test_distinct_live_player_rows_are_content_and_do_count() -> None:
    """The converse control, so the exclusion above is not over-broad.

    A provider that genuinely resolves each requester to a different live engine
    principal reports different player_id rows. That IS observed content, so those
    views must remain distinct. Excluding binding metadata must not have gone so
    far as to hide a real difference.
    """
    observations = {}
    for index, seat in enumerate(SEATS):
        entry = _live_engine_envelope(index, f"live-{index}")
        entry["state"]["players"][index]["player_id"] = f"live-{index}"
        observations[seat] = entry
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["distinct_state_views"] == 4, (
        "distinct live player rows are observed content and must remain distinct"
    )
    assert result["verdict"] == "PRINCIPAL_SCOPED", result["findings"]
