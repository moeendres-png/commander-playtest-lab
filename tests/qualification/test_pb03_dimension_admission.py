"""PB-03 dimension-admission tests (Muse XHIGH Wave 1).

The starting-state requirement is classified by required mechanism per row,
never by fixture-id prefix. These tests pin the admission table's internal
consistency, its mirror agreement with the live seam (via the Java admission
suite covering every tabled row), and the absence of the prefix hardcode in
the runner.
"""

from __future__ import annotations

from pathlib import Path

from commander_lab.qualification.current_boundary.full107 import (
    REQUIRED_DIMENSIONS,
    SEAM_SUPPORTED_DIMENSIONS,
    TIER_1_CONSTRUCT_ONLY,
    TIER_2_GENUINE_CAUSAL,
    TIER_3_NO_GENUINE_PATH,
    admit_row,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_admission_table_partitions_without_overlap() -> None:
    assert len(REQUIRED_DIMENSIONS) == 36
    assert len(TIER_1_CONSTRUCT_ONLY) == 12
    assert len(TIER_2_GENUINE_CAUSAL) == 18
    assert len(TIER_3_NO_GENUINE_PATH) == 6
    assert set(REQUIRED_DIMENSIONS) == (
        set(TIER_1_CONSTRUCT_ONLY) | set(TIER_2_GENUINE_CAUSAL) | set(TIER_3_NO_GENUINE_PATH)
    )


def test_tier_1_is_exactly_the_supported_subset() -> None:
    derived = {
        fixture
        for fixture, dims in REQUIRED_DIMENSIONS.items()
        if set(dims) <= set(SEAM_SUPPORTED_DIMENSIONS)
    }
    assert set(TIER_1_CONSTRUCT_ONLY) == derived


def test_tier_2_and_3_name_missing_dimensions() -> None:
    for fixture in (*TIER_2_GENUINE_CAUSAL, *TIER_3_NO_GENUINE_PATH):
        tier, missing = admit_row(fixture)
        assert tier in ("TIER_2", "TIER_3")
        assert len(missing) >= 1
        assert set(missing) <= set(REQUIRED_DIMENSIONS[fixture]) - set(SEAM_SUPPORTED_DIMENSIONS)


def test_tier_1_rows_admit_clean() -> None:
    for fixture in TIER_1_CONSTRUCT_ONLY:
        assert admit_row(fixture) == ("TIER_1", ())


def test_key_rows_classified_by_mechanism() -> None:
    assert admit_row("MICRO_COSTS")[0] == "TIER_1"
    assert admit_row("MICRO_STATE_BASED_ACTIONS")[0] == "TIER_1"
    assert admit_row("MICRO_TRIGGERS")[0] == "TIER_1"
    assert admit_row("WS05-CMD-ELIM-4")[0] == "TIER_1"
    assert admit_row("MICRO_CONTROL") == ("TIER_2", ("CONTROL_DIVERGENCE",))
    assert "STACK_SPELLS" in admit_row("MICRO_STACK")[1]
    assert "STACK_SPELLS" in admit_row("WS05-CMD-ZONE-GY-YES")[1]
    assert "STACK_SPELLS" in admit_row("WS05-CMD-ZONE-LIB-YES")[1]
    assert admit_row("WS05-MP-TURN-5") == ("TIER_2", ("EXTRA_TURN_QUEUE",))
    assert admit_row("WS05-MP-ELIM-5") == ("TIER_3", ("LIFE_ZERO_PRESTART",))
    assert admit_row("WS05-MP-ELIM-OWNED-3") == ("TIER_3", ("LIFE_ZERO_PRESTART",))
    assert set(admit_row("WS05-MP-ELIM-CONTROL-3")[1]) == {
        "LIFE_ZERO_PRESTART",
        "CONTROL_DIVERGENCE",
    }
    assert set(admit_row("WS05-MP-ELIM-STACK-3")[1]) == {
        "LIFE_ZERO_PRESTART",
        "STACK_SPELLS",
    }


def test_unlisted_rows_stay_unlisted() -> None:
    assert admit_row("WS05-CMD-START-2") == ("UNLISTED", ())
    assert admit_row("CARD_02") == ("UNLISTED", ())
    assert admit_row("MICRO_LAYERS") == ("UNLISTED", ())


def test_java_admission_suite_covers_every_tabled_row() -> None:
    """Mirror agreement: the seam-side suite must pin a verdict per row.

    This is a consistency check (every tabled row has seam evidence), never
    a promotion rule: mentioning a fixture promotes nothing.
    """
    source = (
        REPO_ROOT
        / "engine-bridge/src/test/java/org/commanderlab/xmage/XmagePb03DimensionAdmissionTest.java"
    ).read_text(encoding="utf-8")
    for fixture in REQUIRED_DIMENSIONS:
        assert f'"{fixture}"' in source, fixture


def test_runner_has_no_fixture_prefix_hardcode() -> None:
    """PB-03 regression guard: no BLOCKED outcome may be decided by a
    fixture-id prefix tuple. (A benign PILOT_ prefix read elsewhere is not
    a BLOCKED hardcode and is out of scope for this guard.)"""
    runner = (
        REPO_ROOT / "scripts/run_current_boundary_qualification.py"
    ).read_text(encoding="utf-8")
    assert "INJECTION_BLOCKED_FAMILIES" not in runner
    assert '("WS05-MP-", "WS05-CMD-ZONE-"' not in runner
    assert "mid_game_mechanisms" in runner or "admit_row" in runner
