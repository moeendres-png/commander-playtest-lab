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

# Four PB-03 guards in this family require the WSR22 evidence bundle
# (qualification/final-current-boundary-20260927/EFFECTIVE_FULL107_MANIFEST.json)
# and therefore stay on the WSR22 branch together with that bundle and its
# integrity guard (tests/qualification/test_wsr22_current_boundary.py):
#   test_mechanism_split_agrees_with_the_historical_split_exactly
#   test_the_two_groups_share_no_event
#   test_denominator_is_preserved_at_107
#   test_blocked_rows_earn_no_credit_and_stay_explicit
# They are bundle assertions, not classifier assertions. The classifier itself
# is guarded here and is exercised on this lineage.

from __future__ import annotations

from pathlib import Path

from commander_lab.qualification.current_boundary import materialization

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"
MATERIALIZATION = REPO / "src/commander_lab/qualification/current_boundary/materialization.py"

# The historical prefix tuple, kept here only as the thing being retired.
RETIRED_PREFIXES = ("WS05-MP-", "WS05-CMD-ZONE-", "WS05-CMD-DMG-", "WS05-CMD-ELIM-")


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
