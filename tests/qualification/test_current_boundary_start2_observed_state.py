"""START-2 must be judged from observed engine state, not the fixture.

The defect: the row read the fixture's own ``required_events`` to decide its
verdict, recorded ``rules_rng_binding.engine_owned: true`` unconditionally, and
claimed that no draw event was exposed and that hand/library counts were
unchanged, while observing neither. A checkpoint is not a draw: an engine can
skip the decision checkpoint and still draw the card, and only engine-reported
zone counts distinguish those cases.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FULL107 = REPO / "src/commander_lab/qualification/current_boundary/full107.py"
DRIVER = REPO / "src/commander_lab/qualification/current_boundary/game_driver.py"


def _start2_source() -> str:
    return FULL107.read_text(encoding="utf-8")


def test_start2_does_not_hard_code_engine_owned() -> None:
    source = _start2_source()
    assert '"engine_owned": True' not in source
    assert "UNCONTROLLED_ENGINE_RNG" in source


def test_start2_binding_comes_from_the_real_result() -> None:
    assert "game.seed_binding.to_document()" in _start2_source()


def test_start2_reads_observed_zone_counts() -> None:
    source = _start2_source()
    assert "observed_actor_zone_counts" in source
    assert "observed_draw_semantic_events" in source
    assert "observed_starting_actor" in source


def test_start2_verdict_requires_the_observation_not_just_the_fixture() -> None:
    """Missing observations must yield UNKNOWN, never PASS."""
    source = _start2_source()
    start2 = source[source.index("def start2_row(") :]
    start2 = start2[: start2.index("\ndef non_executed_row(")]
    for marker in (
        "if not zone_counts:",
        "if observed_starting_actor is None:",
        "if observed_draw_events:",
    ):
        assert marker in start2, marker
    # Each guard must produce an UNKNOWN or FAIL, never a PASS.
    for marker in ("if not zone_counts:", "if observed_starting_actor is None:"):
        tail = start2.split(marker, 1)[1]
        match = re.search(r'return RowResult\(\s*\w+,\s*\w+,\s*"(\w+)"', tail)
        assert match, f"no RowResult verdict after {marker}"
        verdict = match.group(1)
        assert verdict in {"UNKNOWN", "FAIL"}, (marker, verdict)


def test_start2_observation_names_the_principal_and_reads_engine_zones() -> None:
    """The provider's principal-scoped read, not a guessed seat or a phantom field.

    The committed run queried ``{"actor": ...}`` (a key the providers ignore)
    and read ``hand_count``/``library_count`` (fields no provider emits), so the
    row was UNKNOWN with "the engine reported no principal-scoped zone counts"
    for both candidates. The read must name the engine-stated acting principal
    through ``observer_player_id`` and derive counts from the engine's own
    zones of that principal's row.
    """
    source = DRIVER.read_text(encoding="utf-8")
    block = source[source.index('if drive_to == "first_turn_draw_skip":') :]
    block = block[: block.index('result.terminal_facts["decision_identity_shape"]')]
    # Explicit principal, stated by the engine frame; never inferred from cards.
    assert '{"observer_player_id": principal}' in block
    assert 'decision.get("actor")' in block
    # Counts come from the acting seat's row only.
    assert 'actor_row.get("seat") != seat_index' in block
    assert 'zones.get("library_size")' in block
    assert "hand=hand" in block
    assert "library_size=library_size" in block
    helper = source[source.index("def _zone_count_record(") :]
    helper = helper[: helper.index("\ndef drive_commander_game(")]
    assert "len(hand)" in helper
    assert '"hand_count"' in helper
    assert '"library_count"' in helper


def test_start2_observation_validates_both_authoritative_binding_shapes() -> None:
    """Either an exact live-engine envelope or an in-state actor marker must bind.

    The two providers bind differently: XMage emits the observer envelope
    (requested id + resolved live engine id + seat), Forge marks the scoped
    principal with ``is_actor``. The driver must accept whichever mechanism the
    provider actually emits and refuse a response that establishes neither, or
    that contradicts itself.
    """
    source = DRIVER.read_text(encoding="utf-8")
    block = source[source.index('if drive_to == "first_turn_draw_skip":') :]
    block = block[: block.index('result.terminal_facts["decision_identity_shape"]')]
    # Mechanism A: the live-engine envelope with the resolved id checked
    # against the acting seat's own player row.
    assert 'payload.get("observer_player_id") == principal' in block
    assert 'payload.get("observer_seat") == seat_index' in block
    assert 'actor_row.get("player_id") == engine_id' in block
    # Mechanism B: the authoritative in-state actor marker.
    assert 'row.get("is_actor") is True' in block
    assert 'marked[0].get("seat") == seat_index' in block
    # Neither binds, or a conflicting one binds: fail closed.
    assert "if not (envelope_bound or marker_bound):" in block
    assert "establishes no authoritative acting principal" in block
    assert "does not bind the acting principal" in block
    assert "does not identify exactly the acting" in block
    # A marker-bound response emits no engine-id proof: there was no envelope
    # id to compare, and recording false would read as a failed proof.
    helper = source[source.index("def _zone_count_record(") :]
    helper = helper[: helper.index("\ndef drive_commander_game(")]
    assert '"LIVE_ENGINE_ENVELOPE" if envelope_bound else "STATE_ACTOR_MARKER"' in helper
    assert "if envelope_bound:" in helper
    assert 'record["engine_id_matches_state_row"] = True' in helper


def test_start2_guard_observations_are_persisted_for_audit() -> None:
    """A verdict whose guard inputs are absent from the artifact cannot be audited.

    The row schema persists ``terminal_facts``, not the row-local evidence
    dict, so the starting actor and the observed draw events must be written
    into the terminal facts as well as used by the verdict.
    """
    source = _start2_source()
    start2 = source[source.index("def start2_row(") :]
    start2 = start2[: start2.index("\ndef non_executed_row(")]
    for marker in (
        'terminal_facts["observed_decision_kinds"]',
        'terminal_facts["observed_draw_semantic_events"]',
        'terminal_facts["observed_starting_actor"]',
    ):
        assert marker in start2, marker


def test_fixture_event_list_is_labelled_as_obligation_not_evidence() -> None:
    assert "fixture_required_events_are_obligation_statements_not_evidence" in _start2_source()


def test_start2_no_longer_decides_from_the_required_list() -> None:
    assert '"starting_player:P1" not in required' not in _start2_source()


def test_driver_observes_engine_reported_zone_counts() -> None:
    source = DRIVER.read_text(encoding="utf-8")
    assert "observed_actor_zone_counts" in source
    assert "ENGINE_REPORTED_PRINCIPAL_SCOPED" in source
    assert '"get_game_state"' in source
    # The read names the engine-stated principal explicitly, and both
    # authoritative binding shapes are represented in the implementation.
    assert '{"observer_player_id": principal}' in source
    assert "LIVE_ENGINE_ENVELOPE" in source
    assert "STATE_ACTOR_MARKER" in source


def test_zone_count_observation_is_scoped_to_the_acting_principal() -> None:
    """Record only the acting principal's counts; never persist another live principal id."""
    source = DRIVER.read_text(encoding="utf-8")
    start = source.index("seat_index = seats_known.index(principal)")
    end = source.index('result.terminal_facts["observed_zone_count_source"]')
    block = source[start:end]
    assert '{"observer_player_id": principal}' in block
    assert 'actor_row.get("seat") != seat_index' in block
    helper = source[source.index("def _zone_count_record(") :]
    helper = helper[: helper.index("\ndef drive_commander_game(")]
    assert '"hand_count"' in helper
    assert '"library_count"' in helper
    # The engine id may be used transiently to prove the binding but must not
    # be stored in the terminal-facts record.
    assert '"observer_engine_player_id"' not in helper
    assert '"player_id"' not in helper
