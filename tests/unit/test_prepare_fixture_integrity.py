"""Owned fixture-integrity gates (workstream prepare-behavior-qualification).

Hermetic (no JVM): the 11-card SOS prepare fixture must keep its honest
shape — 10 required rule paths each, pinned engine, UNKNOWN/NOT_RUN verdicts,
no name-inferred UUIDs — so the Java construction gate verdicts can be joined
to exactly this fixture without drift.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "physical_pool_prepare_sos.json"
)

EXPECTED_ORACLE_NAMES = [
    "Biblioplex Tomekeeper",
    "Blazing Firesinger // Seething Song",
    "Cheerful Osteomancer // Raise Dead",
    "Dirgur Focusmage // Braingeyser",
    "Goblin Glasswright // Craft with Pride",
    "Inspired Skypainter // Maestro's Gift",
    "Sanar, Unfinished Genius // Wild Idea",
    "Skycoach Waypoint",
    "Spellbook Seeker // Careful Study",
    "Studious First-Year // Rampant Growth",
    "Tam, Observant Sequencer // Deep Sight",
]

CONSTRUCTIBLE_ON_PINNED_1461 = {
    "Biblioplex Tomekeeper",
    "Skycoach Waypoint",
}


def _load() -> dict:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_fixture_lists_exactly_eleven_prepare_identities():
    payload = _load()
    assert payload["engine_pin"] == "xmage-1.4.61"
    assert payload["production_provider"] == "NOT_SELECTED"
    names = [card["oracle_name"] for card in payload["cards"]]
    assert names == EXPECTED_ORACLE_NAMES


def test_every_card_carries_ten_required_rule_paths_and_unknown_verdict():
    payload = _load()
    for card in payload["cards"]:
        assert len(card["required_rule_paths"]) == 10, card["oracle_name"]
        assert card["verdict"] == "UNKNOWN", card["oracle_name"]
        assert card["observed_output"] == "NOT_RUN", card["oracle_name"]
        assert card["commander_legal"] is True, card["oracle_name"]


def test_no_name_inferred_uuids():
    payload = _load()
    for card in payload["cards"]:
        status = card["oracle_id_status"]
        assert "inferred" not in status.lower() or "not inferred" in status.lower(), (
            card["oracle_name"],
            status,
        )


def test_constructible_subset_matches_pinned_engine_gate():
    """Join point: the Java PrepareConstructionGateTest proves exactly these
    two fixture identities resolve on pinned xmage-1.4.61; the other nine
    stay construction-UNKNOWN/BLOCKED there. This test pins the subset so a
    fixture edit cannot silently change the gate denominator."""
    payload = _load()
    names = {card["oracle_name"] for card in payload["cards"]}
    assert names >= CONSTRUCTIBLE_ON_PINNED_1461
    assert len(CONSTRUCTIBLE_ON_PINNED_1461) == 2
    blocked = names - CONSTRUCTIBLE_ON_PINNED_1461
    assert len(blocked) == 9
    assert all("//" in name for name in blocked)
