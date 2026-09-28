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
    for both candidates. The read must name the principal through
    ``observer_player_id`` and derive counts from the engine's own zones.
    """
    source = DRIVER.read_text(encoding="utf-8")
    block = source[source.index('if drive_to == "first_turn_draw_skip":') :]
    block = block[: block.index('result.terminal_facts["decision_identity_shape"]')]
    assert '"observer_player_id": actor_id' in block
    assert '"actor": actor_seat' not in block
    assert 'zones.get("library_size")' in block
    assert "len(hand)" in block
    # Counts come from the marked principal entry only, never from any seat.
    assert 'entry.get("is_actor") is not True' in block
    # The actor identity comes from the observed frame, never guessed.
    assert 'frame.get("decision", {}).get("actor")' in block


def test_fixture_event_list_is_labelled_as_obligation_not_evidence() -> None:
    assert "fixture_required_events_are_obligation_statements_not_evidence" in _start2_source()


def test_start2_no_longer_decides_from_the_required_list() -> None:
    assert '"starting_player:P1" not in required' not in _start2_source()


def test_driver_observes_engine_reported_zone_counts() -> None:
    source = DRIVER.read_text(encoding="utf-8")
    assert "observed_actor_zone_counts" in source
    assert "ENGINE_REPORTED_PRINCIPAL_SCOPED" in source
    assert '"get_game_state"' in source
    # The observation must select only the marked acting principal, not every player.
    assert 'entry.get("is_actor") is not True' in source


def test_zone_count_observation_is_scoped_to_the_acting_principal() -> None:
    """A hidden-information guard: record the actor's own counts, never another seat's."""
    source = DRIVER.read_text(encoding="utf-8")
    start = source.index('seats = state.get("players")')
    end = source.index('"observed_actor_zone_counts"] = mine')
    block = source[start:end]
    assert 'entry.get("is_actor") is not True' in block
    assert "hand_count" in block
    assert "library_count" in block
    # The engine's own principal identifier must never be recorded.
    assert "player_id" not in block
    # Only the acting seat's entry is kept, never the whole players array.
    assert "for entry in seats or []" in block
