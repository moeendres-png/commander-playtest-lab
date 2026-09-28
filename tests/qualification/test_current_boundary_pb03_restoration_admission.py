"""PB-03: a frozen mid-game obligation is admitted from the ENGINE's manifest.

The two properties that matter here are that the mapping is anchored to the
engine's own wording (so it fails closed when that wording moves) and that it
decides admissibility only, never an outcome.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import materialization as M
from commander_lab.qualification.current_boundary import restoration_admission as RA

REPO = Path(__file__).resolve().parents[2]

# The manifest exactly as the pinned bridge publishes it. Copied verbatim so a
# test failure means the ENGINE changed, not that a fixture drifted.
LIVE_MANIFEST = {
    "schema_version": "native-state-restoration-dimensions-1.1.0",
    "starting_state_injection_supported": False,
    "supported_dimensions": [
        "commanders with prior cast counts (native game-load restore path)",
        "commander damage matrices through exact live CommanderInfoWatcher bindings "
        "(native game-load restore; no synthetic damage events)",
        "battlefield/graveyard/exile placement of real cards (silent setup primitive)",
        "hand identity via the same setup primitive (principal-scoped; pilot observation "
        "stays counts-only through the redactor; honeycard non-leakage proven per fixture)",
        "owner-equals-controller attribution with 1:1 readback",
        "life totals (pre-start assembly; state-based actions stay authoritative)",
        "qualified turn-1 temporal targets: upkeep, draw, precombat main, declare attackers, "
        "declare blockers, combat damage, postcombat main; arrival requires "
        "XmageTemporalProgressionDriver native progression",
        "explicit Rules-seed binding with replay determinism",
        "strict native readback with field-level compare and digests",
        "explicit L7 lossless hidden-state requests: complete live-library identity order plus "
        "one explicitly typed face-down battlefield object; delegated to native RG-06A "
        "game-load APIs",
        "frozen requested_state_digest equality for constructed states in the v1 subset "
        "(canonical projection per the recovered spec, verified per fixture; see "
        "requestedDigest/constructedDigest)",
    ],
    "unsupported_dimensions": [
        "stack spells (casting requires real costs/timing: executor scope)",
        "legacy/frozen partial library identity: no complete permutation, fail closed",
        "legacy/frozen face_down=true without explicit native type: fail closed",
        "revealed-zone restoration",
        "controller/owner divergence (engine layers re-derive control)",
        "attachments and counters",
        "tapped permanents (unqualified dimension)",
        "commander relations other than validated Partner linkage",
        "poison counters",
        "temporal points outside the qualified RG-03 turn-1 checkpoint allow-list",
        "frozen requested_state_digest reproduction (no canonicalization spec in repo)",
    ],
}


def _payload() -> dict:
    """A fresh deep copy each call.

    Several tests below mutate the payload to prove fail-closed behaviour. If
    this returned the shared LIVE_MANIFEST, the first mutation would poison every
    later test in the module.
    """
    return copy.deepcopy({"full_game_lane": {"state_restoration_dimensions": LIVE_MANIFEST}})


def test_manifest_parses_from_the_live_capability_payload() -> None:
    manifest = RA.parse_manifest(_payload())
    assert manifest.schema_version == RA.RESTORATION_MANIFEST_SCHEMA
    assert len(manifest.supported) == 11
    assert len(manifest.unsupported) == 11


def test_absent_manifest_fails_closed_instead_of_claiming_no_capability() -> None:
    """A missing manifest must not degrade into "engine supports nothing".

    That would read as an engine incapability nobody observed.
    """
    with pytest.raises(RA.ManifestUnavailableError):
        RA.parse_manifest({})
    with pytest.raises(RA.ManifestUnavailableError):
        RA.parse_manifest({"full_game_lane": {}})
    with pytest.raises(RA.ManifestUnavailableError):
        RA.parse_manifest(None)


def test_unexpected_manifest_schema_fails_closed() -> None:
    payload = _payload()
    payload["full_game_lane"]["state_restoration_dimensions"]["schema_version"] = "something-else"
    with pytest.raises(RA.ManifestUnavailableError, match="unexpected restoration manifest schema"):
        RA.parse_manifest(payload)


def test_malformed_dimension_lists_fail_closed() -> None:
    payload = _payload()
    del payload["full_game_lane"]["state_restoration_dimensions"]["supported_dimensions"]
    with pytest.raises(RA.ManifestUnavailableError):
        RA.parse_manifest(payload)


@pytest.mark.parametrize(
    ("family", "expected"),
    [
        ("live_priority_ring", "SUPPORTED"),
        ("combat_declaration", "SUPPORTED"),
        ("commander_damage_accounting", "SUPPORTED"),
        ("zone_manipulation", "SUPPORTED"),
        ("stack_response", "UNSUPPORTED"),
        ("turn_transition", "UNSUPPORTED"),
    ],
)
def test_every_mapped_family_is_anchored_to_engine_wording(family: str, expected: str) -> None:
    manifest = RA.parse_manifest(_payload())
    verdict = RA.classify_family(manifest, family)
    assert verdict.state == expected, verdict.detail
    # A SUPPORTED or UNSUPPORTED verdict must quote the engine's own text.
    assert verdict.engine_text, "a mapped verdict must cite the engine's manifest entry"
    assert any(
        text in LIVE_MANIFEST["supported_dimensions"] + LIVE_MANIFEST["unsupported_dimensions"]
        for text in verdict.engine_text
    )


def test_unmapped_mechanism_family_fails_closed() -> None:
    """multiplayer_lifecycle has no honest dimension mapping and must not be admitted."""
    manifest = RA.parse_manifest(_payload())
    assert "multiplayer_lifecycle" not in RA.MECHANISM_DIMENSION_REQUIREMENTS
    verdict = RA.classify_family(manifest, "multiplayer_lifecycle")
    assert verdict.state == "NOT_DECLARED"
    assert verdict.admissible is False
    assert "no declared engine-dimension requirement" in verdict.detail


def test_engine_wording_change_degrades_to_not_declared_rather_than_guessing() -> None:
    """If the engine renames a dimension, the family must stop being admitted."""
    payload = _payload()
    dims = payload["full_game_lane"]["state_restoration_dimensions"]
    dims["supported_dimensions"] = [
        text
        for text in dims["supported_dimensions"]
        if "qualified turn-1 temporal targets" not in text
    ]
    manifest = RA.parse_manifest(payload)
    verdict = RA.classify_family(manifest, "combat_declaration")
    assert verdict.state == "NOT_DECLARED"
    assert verdict.admissible is False
    assert "Engine wording may have moved" in verdict.detail


def test_admission_requires_every_family_to_be_supported() -> None:
    manifest = RA.parse_manifest(_payload())
    admitted = RA.admit(
        manifest, {"fixture_id": "X"}, families=("combat_declaration", "zone_manipulation")
    )
    assert admitted.admitted is True
    mixed = RA.admit(
        manifest, {"fixture_id": "Y"}, families=("combat_declaration", "stack_response")
    )
    assert mixed.admitted is False
    unmapped = RA.admit(manifest, {"fixture_id": "Z"}, families=("multiplayer_lifecycle",))
    assert unmapped.admitted is False


def test_admission_never_manufactures_an_outcome() -> None:
    """Admissible means "may be attempted", never PASS."""
    manifest = RA.parse_manifest(_payload())
    verdict = RA.admit(manifest, {"fixture_id": "X"}, families=("combat_declaration",))
    blob = json.dumps(verdict.__dict__, default=str)
    for forbidden in ("PASS", "pass", "FAIL", "fail"):
        assert forbidden not in blob, f"admission leaked an outcome token: {forbidden}"


def test_admission_reports_the_transport_seam_rather_than_claiming_execution() -> None:
    """The engine can restore the dimension, but the lane cannot reach it yet."""
    manifest = RA.parse_manifest(_payload())
    verdict = RA.admit(manifest, {"fixture_id": "X"}, families=("combat_declaration",))
    assert verdict.admitted is True
    assert RA.TRANSPORT_SEAM_AVAILABLE is False
    assert "no protocol message that reaches the native restoration path" in verdict.reason
    assert "not an engine limitation" in verdict.reason


def test_every_requirement_marker_matches_a_real_manifest_entry() -> None:
    """No mapping may cite a dimension the engine never published."""
    manifest = RA.parse_manifest(_payload())
    for family, requirements in RA.MECHANISM_DIMENSION_REQUIREMENTS.items():
        for requirement in requirements:
            state, _text = manifest.locate(requirement.marker)
            assert state != "NOT_DECLARED", (
                f"{family} cites marker {requirement.marker!r} which the pinned engine does "
                "not publish; the mapping must be re-derived from the live manifest"
            )


def test_every_mid_game_mechanism_family_is_either_mapped_or_fails_closed() -> None:
    """No family may exist without a decision: mapped, or explicitly not declared."""
    for family in M.MID_GAME_MECHANISM_FAMILIES:
        manifest = RA.parse_manifest(_payload())
        verdict = RA.classify_family(manifest, family)
        assert verdict.state in {"SUPPORTED", "UNSUPPORTED", "NOT_DECLARED"}
        if family not in RA.MECHANISM_DIMENSION_REQUIREMENTS:
            assert verdict.state == "NOT_DECLARED"
            assert verdict.admissible is False


def test_starting_state_rows_split_into_engine_supported_and_engine_declared_refusals() -> None:
    """The headline PB-03 reclassification, measured on the real denominator."""
    materialization = M.load_effective_materialization()
    denominator = (
        materialization.denominator_records()
        if hasattr(materialization, "denominator_records")
        else materialization
    )
    manifest = RA.parse_manifest(_payload())
    supported: list[str] = []
    refused: list[str] = []
    for record in denominator:
        families = tuple(sorted(M.mid_game_mechanisms(record)))
        if not families:
            continue
        verdict = RA.admit(manifest, record, families=families)
        (supported if verdict.admitted else refused).append(record["fixture_id"])
    # The engine declares placement and turn-1 combat/timing/damage supported.
    assert set(supported) >= {
        "PILOT_DECLARE_ATTACKER",
        "PILOT_DECLARE_BLOCKER",
        "WS05-MP-COMBAT-4",
        "WS05-MP-BLOCK-4",
        "WS05-CMD-ZONE-HAND-YES",
    }
    # The engine itself refuses stack spells and out-of-allow-list temporal points.
    assert "WS05-CMD-DMG-SPLIT" not in refused, "commander damage is engine-supported"
    assert len(supported) + len(refused) == 30


# --- PB-04: seed support is LANE-scoped and must be read, not assumed ---------


def test_create_request_omits_seed_on_a_lane_that_declares_no_seed_support() -> None:
    """The generic lane refuses any seed option; sending one fails game creation.

    That failure is unrelated to Rules behaviour, so it must not be shaped into
    the request. PB-04: the capability is lane-scoped and has to be read.
    """
    from commander_lab.qualification.current_boundary.game_driver import _create_request

    request = _create_request("g1", ["h1"], 20260923, lane_seed_supported=False)
    assert "seed" not in request
    assert "rules_seed" not in request
    assert "options" not in request
    # external_control stays: without it the lane exposes no external decision
    # surface and the engine would self-play (PB-01).
    assert request["external_control"] is True


def test_create_request_carries_the_seed_on_a_lane_that_declares_seed_support() -> None:
    from commander_lab.qualification.current_boundary.game_driver import _create_request

    request = _create_request("g1", ["h1"], 20260923, lane_seed_supported=True)
    assert request["seed"] == 20260923
    assert request["rules_seed"] == 20260923
    assert request["options"] == {"seed": 20260923, "rules_seed": 20260923}
