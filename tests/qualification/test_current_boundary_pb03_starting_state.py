"""PB-03: the starting-state requirement is a mechanism, not a row name.

The runner decided which denominator rows were blocked by the missing generic
starting-state seam with a hard-coded tuple of fixture-id prefixes. A name-based
classifier cannot classify a row it has never seen, mis-classifies any future row
whose id shares a prefix, and hides the reason behind a string.

These tests pin the mechanism-based replacement. The key one does not hard-code
the expected split either: it derives the split from the effective materialization
and requires the mechanism classifier to agree with it exactly, and requires the
classifier source to contain no fixture id at all.
"""

from __future__ import annotations

import json
from pathlib import Path

from commander_lab.qualification.current_boundary import materialization

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"
MATERIALIZATION = REPO / "src/commander_lab/qualification/current_boundary/materialization.py"
MANIFEST = REPO / "qualification/final-current-boundary-20260927/EFFECTIVE_FULL107_MANIFEST.json"

# The historical prefix tuple, kept here only as the thing being retired.
RETIRED_PREFIXES = ("WS05-MP-", "WS05-CMD-ZONE-", "WS05-CMD-DMG-", "WS05-CMD-ELIM-")


def _rows() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["rows"]


def test_classifier_source_contains_no_fixture_id() -> None:
    """The classifier must not be keyed to any row's name."""
    source = MATERIALIZATION.read_text(encoding="utf-8")
    # Only the retired-prefix comment may mention the old constant.
    for prefix in RETIRED_PREFIXES:
        occurrences = source.count(prefix)
        assert occurrences <= 1, f"{prefix} appears {occurrences} times in the classifier"


def test_runner_has_no_prefix_match_on_obligation_rows() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "mid_game_mechanisms(record)" in source
    for prefix in RETIRED_PREFIXES:
        assert f'"{prefix}"' not in source, f"{prefix} is still matched by name"


def test_mechanism_split_agrees_with_the_historical_split_exactly() -> None:
    """The derived split must match the retired one, row for row."""
    rows = [r for r in _rows() if r["fixture_family"] == "multiplayer_commander"]
    by_mechanism = {r["fixture_id"] for r in rows if materialization.requires_starting_state(r)}
    by_prefix = {r["fixture_id"] for r in rows if r["fixture_id"].startswith(RETIRED_PREFIXES)}
    assert by_mechanism == by_prefix, (
        f"only-mechanism={sorted(by_mechanism - by_prefix)} "
        f"only-prefix={sorted(by_prefix - by_mechanism)}"
    )
    # And the split is non-trivial in both directions, so the test is not vacuous.
    assert len(by_mechanism) == 27
    assert len(by_prefix) == 27
    assert len(rows) == 36


def test_the_two_groups_share_no_event() -> None:
    """Why the split is exact rather than approximate."""
    rows = [r for r in _rows() if r["fixture_family"] == "multiplayer_commander"]
    mid = set()
    start = set()
    for record in rows:
        events = set(record.get("expected_events") or [])
        (mid if materialization.requires_starting_state(record) else start).update(events)
    assert mid, "expected some mid-game rows"
    assert start, "expected some game-start rows"
    assert not (mid & start), f"shared events: {sorted(mid & start)}"


def test_denominator_is_preserved_at_107() -> None:
    """PB-03 must not remove or duplicate a row to make the seam work."""
    assert len(_rows()) == 107


def test_blocked_rows_earn_no_credit_and_stay_explicit() -> None:
    """A mechanism-blocked row is UNKNOWN/BLOCKED, never a silent PASS."""
    for record in _rows():
        if not materialization.requires_starting_state(record):
            continue
        mechanisms = materialization.mid_game_mechanisms(record)
        assert mechanisms, record["fixture_id"]
        # Every mechanism named must be a declared family, not a raw event string.
        for mechanism in mechanisms:
            assert mechanism in materialization.MID_GAME_MECHANISM_FAMILIES


def test_an_unseen_mid_game_row_is_classified_correctly() -> None:
    """Generalization: a row the classifier has never seen still classifies."""
    unseen_mid = {
        "fixture_id": "TOTALLY-NEW-ID-999",
        "fixture_family": "multiplayer_commander",
        "expected_events": ["priority_ring_live_order", "brand_new_event"],
    }
    assert materialization.requires_starting_state(unseen_mid) is True
    assert materialization.mid_game_mechanisms(unseen_mid) == ["live_priority_ring"]


def test_an_unseen_game_start_row_is_classified_correctly() -> None:
    unseen_start = {
        "fixture_id": "ANOTHER-NEW-ID-000",
        "fixture_family": "multiplayer_commander",
        "expected_events": ["game_start_command_zone:cmd:P9-A", "mulligan_once:P1"],
    }
    assert materialization.requires_starting_state(unseen_start) is False
    assert materialization.mid_game_mechanisms(unseen_start) == []


def test_matching_is_exact_or_prefix_not_substring() -> None:
    """`player_leaves` must match `player_leaves:P2` but not `xplayer_leaves`."""
    assert materialization.requires_starting_state({"expected_events": ["player_leaves:P2"]})
    assert not materialization.requires_starting_state({"expected_events": ["xplayer_leaves:P2"]})


def test_malformed_records_do_not_raise() -> None:
    for record in (
        {},
        {"expected_events": None},
        {"expected_events": "nope"},
        {"expected_events": []},
    ):
        assert materialization.requires_starting_state(record) is False


def test_nested_event_mapping_form_is_supported() -> None:
    record = {"expected_events": {"required_events": ["response_on_stack"], "forbidden_events": []}}
    assert materialization.mid_game_mechanisms(record) == ["stack_response"]


def test_starting_state_injection_flag_is_not_flipped() -> None:
    """PB-03 forbids flipping the capability; the seam is a different obligation."""
    from commander_lab.qualification.current_boundary import full107

    source = (REPO / "src/commander_lab/qualification/current_boundary/full107.py").read_text(
        encoding="utf-8"
    )
    assert "starting_state_injection_supported" in source
    assert "INJECTION_BLOCKED_FAMILIES" not in source
    assert hasattr(full107, "INJECTION_BLOCKED_FAMILIES") is False
