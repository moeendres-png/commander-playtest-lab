"""A redaction placeholder is the absence of content, not leaked content.

The Forge bridge returns "<hidden>" for every opponent card and the real names
only for the requesting seat, which is correct redaction. The validator treated
any non-empty opponent zone array as exposed content, so it assigned
ENGINE_CANDIDATE_DEFECT to a provider that was redacting correctly and reported a
confirmed engine failure that AF05 does not support. A false accusation is as
wrong as a false credit.

Two distinctions matter and are pinned here:

1. A placeholder array is not content. An empty list, a null, or a list of
   placeholders discloses nothing.
2. Content on a non-actor seat is a DEMONSTRATED leak only when the provider
   marked the observing principal. Without that marker the content may be the
   requester's own, and attributing a leak would be unsupported. One shared state
   view across different requesters is conclusive on its own, because the
   requester differs while the payload does not.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from commander_lab.qualification.current_boundary.full107 import (
    _zone_exposes_content,
    validate_principal_scoping,
)

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "qualification/final-current-boundary-20260927"
SEATS = ("p1", "p2", "p3", "p4")


def _observation(actor_seat: int, *, redact: bool = True) -> dict:
    seats = []
    for index in range(4):
        if index == actor_seat:
            hand = ["Plains", "Plains"]
        else:
            hand = ["<hidden>", "<hidden>"] if redact else ["Suntail Hawk", "Time Walk"]
        seats.append(
            {
                "seat": index,
                "is_actor": index == actor_seat,
                "zones": {"hand": hand, "library": []},
            }
        )
    return {"state_observation_offset": 1, "state": {"players": seats}}


def _correctly_scoped() -> dict[str, dict]:
    return {seat: _observation(index) for index, seat in enumerate(SEATS)}


def _unmarked_actor() -> dict[str, dict]:
    observations = _correctly_scoped()
    for payload in observations.values():
        for entry in payload["state"]["players"]:
            entry["is_actor"] = False
    return observations


def _envelope_scoped() -> dict[str, dict]:
    observations = _correctly_scoped()
    for actor_index, seat in enumerate(SEATS):
        payload = observations[seat]
        engine_id = f"engine-{seat}"
        payload["observer_player_id"] = seat
        payload["observer_engine_player_id"] = engine_id
        payload["observer_seat"] = actor_index
        for index, entry in enumerate(payload["state"]["players"]):
            entry.pop("is_actor", None)
            entry["player_id"] = engine_id if index == actor_index else f"op-{index}"
    return observations


def _identical_views_with_real_content() -> dict[str, dict]:
    shared = _observation(0, redact=False)
    shared["state"]["players"][1]["is_actor"] = False
    return {seat: dict(shared) for seat in SEATS}


# --- placeholders are not content ----------------------------------------- #


def test_placeholder_arrays_disclose_nothing() -> None:
    assert _zone_exposes_content(["<hidden>", "<hidden>"]) is False
    assert _zone_exposes_content(["REDACTED", "***"]) is False
    assert _zone_exposes_content([]) is False
    assert _zone_exposes_content(None) is False


def test_real_content_is_detected() -> None:
    assert _zone_exposes_content(["Plains"]) is True
    assert _zone_exposes_content(["<hidden>", "Suntail Hawk"]) is True
    assert _zone_exposes_content([{"name": "Time Walk"}]) is True


def test_correct_redaction_is_principal_scoped() -> None:
    result = validate_principal_scoping(_correctly_scoped(), requested_seats=SEATS)
    assert result["verdict"] == "PRINCIPAL_SCOPED", result["findings"]
    assert result["attribution"] == "NONE"


def test_unmarked_actor_is_unestablished_not_defective() -> None:
    """Content may be the requester's own when no principal binding is available."""
    result = validate_principal_scoping(_unmarked_actor(), requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False
    assert result["attribution"] == "SCOPING_NOT_ESTABLISHED_ACTOR_MARKING_ABSENT"
    assert result["engine_leak_indicators"] == []


def test_exact_observer_envelope_establishes_requester_without_state_schema_change() -> None:
    result = validate_principal_scoping(_envelope_scoped(), requested_seats=SEATS)
    assert result["verdict"] == "PRINCIPAL_SCOPED", result["findings"]
    assert result["observations_with_established_requester"] == list(SEATS)
    assert result["attribution"] == "NONE"


def test_mismatched_observer_envelope_fails_closed() -> None:
    observations = _envelope_scoped()
    observations["p1"]["observer_player_id"] = "p2"
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False
    assert any(
        finding["check"] == "observer_binding" and finding.get("seat") == "p1"
        for finding in result["findings"]
    )


def test_conflicting_actor_marker_cannot_be_hidden_by_valid_envelope() -> None:
    observations = _envelope_scoped()
    observations["p1"]["state"]["players"][1]["is_actor"] = True
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["credible_as_principal_scoped_evidence"] is False
    assert any(
        finding["check"] == "actor_binding_conflict" and finding.get("seat") == "p1"
        for finding in result["findings"]
    )


def _dual_shape_scoped() -> dict[str, dict]:
    """Each observation carries BOTH authoritative mechanisms, consistently."""
    observations = _envelope_scoped()
    for index, seat in enumerate(SEATS):
        observations[seat]["state"]["players"][index]["is_actor"] = True
    return observations


def _mixed_shape_scoped() -> dict[str, dict]:
    """Alternate mechanisms per observation; each is authoritative on its own."""
    envelope = _envelope_scoped()
    marker = _correctly_scoped()
    return {
        seat: (envelope if index % 2 == 0 else marker)[seat] for index, seat in enumerate(SEATS)
    }


def test_both_authoritative_binding_shapes_are_accepted() -> None:
    """Provider-neutral: the envelope and the state marker are both valid bindings."""
    both = validate_principal_scoping(_dual_shape_scoped(), requested_seats=SEATS)
    assert both["verdict"] == "PRINCIPAL_SCOPED", both["findings"]
    assert both["observations_with_established_requester"] == list(SEATS)

    mixed = validate_principal_scoping(_mixed_shape_scoped(), requested_seats=SEATS)
    assert mixed["verdict"] == "PRINCIPAL_SCOPED", mixed["findings"]
    assert mixed["observations_with_established_requester"] == list(SEATS)


def test_binding_metadata_alone_cannot_fabricate_distinct_views() -> None:
    """One identical content view stays identical however the binding is marked.

    Every binding field the providers emit is varied per requester: requested id,
    resolved engine id, seat, in-state actor marker and the monotonic envelope
    offset. The observed rows themselves (seat, live player id, zones) are
    identical across the four responses. Binding metadata is not observed game
    content, so the four views must still count as one shared view and must not
    earn principal-scoped credit.
    """
    shared = _observation(0)
    for entry in shared["state"]["players"]:
        entry["zones"]["hand"] = ["<hidden>", "<hidden>"]
    observations = {}
    for index, seat in enumerate(SEATS):
        entry = copy.deepcopy(shared)
        entry["state_observation_offset"] = 1 + index
        entry["observer_player_id"] = seat
        entry["observer_seat"] = index
        entry["observer_engine_player_id"] = f"engine-{seat}"
        for row_index, row in enumerate(entry["state"]["players"]):
            row["player_id"] = f"engine-{row_index}"
            row["is_actor"] = row_index == index
        observations[seat] = entry
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["distinct_state_views"] == 1, result
    assert result["credible_as_principal_scoped_evidence"] is False
    assert any(
        finding["check"] == "observations_differ_per_principal" for finding in result["findings"]
    )


def test_one_shared_view_is_a_demonstrated_defect() -> None:
    """Different requester, identical payload, therefore each sees the others."""
    result = validate_principal_scoping(_identical_views_with_real_content(), requested_seats=SEATS)
    assert result["attribution"] == "ENGINE_CANDIDATE_DEFECT"
    assert result["distinct_state_views"] == 1
    assert "hand" in result["engine_leak_indicators"]


def test_real_content_for_a_known_non_actor_is_a_defect() -> None:
    observations = _correctly_scoped()
    observations["p1"]["state"]["players"][2]["zones"]["hand"] = ["Time Walk"]
    result = validate_principal_scoping(observations, requested_seats=SEATS)
    assert result["attribution"] == "ENGINE_CANDIDATE_DEFECT"


def test_attribution_rule_is_stated() -> None:
    observations = _unmarked_actor()
    rule = validate_principal_scoping(observations, requested_seats=SEATS)["attribution_rule"]
    assert "conclusive candidate defect" in rule
    assert "must never be asserted" in rule


# --- against the committed artifacts --------------------------------------- #


def test_committed_xmage_evidence_is_a_demonstrated_defect() -> None:
    document = json.loads((OUT / "HIDDEN_INFO_XMAGE.json").read_text(encoding="utf-8"))
    result = validate_principal_scoping(document["principal_observations"], requested_seats=SEATS)
    assert result["distinct_state_views"] == 1, "XMage returns one shared view"
    assert result["attribution"] == "ENGINE_CANDIDATE_DEFECT"


def test_committed_forge_evidence_is_not_a_demonstrated_defect() -> None:
    """Forge redacts opponents with placeholders and varies per requester."""
    document = json.loads((OUT / "HIDDEN_INFO_FORGE.json").read_text(encoding="utf-8"))
    result = validate_principal_scoping(document["principal_observations"], requested_seats=SEATS)
    assert result["distinct_state_views"] == 4, "Forge varies the view per requester"
    assert result["attribution"] != "ENGINE_CANDIDATE_DEFECT", (
        "Forge redacts correctly; accusing it of a content leak is unsupported"
    )
