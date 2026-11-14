"""Unit tests for the objective ranking-check metrics and CLI (issue #1349)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio import __main__ as studio_cli
from commander_lab.studio import strength, strength_view
from commander_lab.studio.ranking_check import (
    PLAUSIBILITY_ANCHOR_NOTE,
    SCHEMA,
    check_ranking,
    render_ranking_check,
    spearman_correlation,
)
from commander_lab.studio.store import StudioStore
from commander_lab.studio.strength import (
    BRACKET_INCLUSION,
    COMBOS,
    COMMANDER_INCLUSION,
    DECK_UNIVERSE,
    GLOBAL_INCLUSION,
    PLAYGROUP_OBSERVED,
    SYNERGY,
    TOURNAMENT_LISTS,
    Observation,
    PoolContext,
    StrengthSettings,
)


def _obs(
    cards: list[str],
    per_component: dict[str, dict[str, Observation]],
) -> dict[str, dict[str, Observation]]:
    result: dict[str, dict[str, Observation]] = {card: {} for card in cards}
    for comp, mapping in per_component.items():
        for card, item in mapping.items():
            result.setdefault(card, {})[comp] = item
    return result


def test_metric_1_spearman_monotone_vs_inverted_and_non_lands_split() -> None:
    """Metric 1: Spearman correlation distinguishes monotone agreement (+1.0) from
    inverted order (-1.0) and separates non-lands from lands; constant or <2 is None."""
    cards = ["c1", "c2", "c3", "c4", "l1", "l2"]
    shares = {
        "c1": Observation(0.10, 10, 100),
        "c2": Observation(0.20, 20, 100),
        "c3": Observation(0.40, 40, 100),
        "c4": Observation(0.80, 80, 100),
        "l1": Observation(0.90, 90, 100),
        "l2": Observation(0.05, 5, 100),
    }
    # Monotone for non-lands (c1 < c2 < c3 < c4), inverted for lands (l1 < l2 while share l1 > l2)
    cmd_inc = {
        "c1": Observation(0.10, 10, 100),
        "c2": Observation(0.20, 20, 100),
        "c3": Observation(0.40, 40, 100),
        "c4": Observation(0.80, 80, 100),
        "l1": Observation(0.05, 5, 100),
        "l2": Observation(0.90, 90, 100),
    }
    settings = StrengthSettings(
        weights={
            COMMANDER_INCLUSION: 1.0,
            BRACKET_INCLUSION: 0.0,
            DECK_UNIVERSE: 0.0,
            SYNERGY: 0.0,
            TOURNAMENT_LISTS: 0.0,
            GLOBAL_INCLUSION: 0.0,
            COMBOS: 0.0,
            PLAYGROUP_OBSERVED: 0.0,
        },
        min_components=1,
        min_coverage=0.1,
    )
    ctx = PoolContext(
        type_group={
            "c1": "Creature",
            "c2": "Instant",
            "c3": "Sorcery",
            "c4": "Artifact",
            "l1": "Land",
            "l2": "Land",
        }
    )
    report = check_ranking(
        settings,
        _obs(cards, {COMMANDER_INCLUSION: cmd_inc}),
        {COMMANDER_INCLUSION},
        context=ctx,
        counted_lists=shares,
        counted_lists_label="Test-Universum",
    )
    assert report["schema"] == SCHEMA
    assert report["spearman"]["note"] == PLAUSIBILITY_ANCHOR_NOTE
    assert report["spearman"]["denominator"] == 100
    assert report["spearman"]["non_lands"]["spearman_rho"] == 1.0
    assert report["spearman"]["non_lands"]["compared"] == 4
    assert report["spearman"]["lands"]["spearman_rho"] == -1.0
    assert report["spearman"]["lands"]["compared"] == 2
    assert report["spearman"]["all_ranked"]["spearman_rho"] is not None
    assert -1.0 < report["spearman"]["all_ranked"]["spearman_rho"] < 1.0

    # Counterexample: invert non-land signal order -> non_lands Spearman becomes -1.0
    inv_cmd = {
        "c1": Observation(0.80, 80, 100),
        "c2": Observation(0.40, 40, 100),
        "c3": Observation(0.20, 20, 100),
        "c4": Observation(0.10, 10, 100),
        "l1": Observation(0.05, 5, 100),
        "l2": Observation(0.90, 90, 100),
    }
    inv_report = check_ranking(
        settings,
        _obs(cards, {COMMANDER_INCLUSION: inv_cmd}),
        {COMMANDER_INCLUSION},
        context=ctx,
        counted_lists=shares,
    )
    assert inv_report["spearman"]["non_lands"]["spearman_rho"] == -1.0

    # Edge cases: fewer than 2 shared keys or constant values -> None (unknown, never 0.0)
    assert spearman_correlation({"a": 1.0}, {"a": 2.0}) is None
    assert (
        spearman_correlation({"a": 5.0, "b": 5.0, "c": 5.0}, {"a": 1.0, "b": 2.0, "c": 3.0}) is None
    )


def test_metric_2_marginal_cards_at_top_and_counterexample() -> None:
    """Metric 2: counts and names cards in S or A whose counted-list share is strictly < 5 %."""
    cards = [f"c{i}" for i in range(10)]
    # Give c9 (index 100 -> S) a 2 % share (< 5 % -> marginal at top)
    # Give c8 (index 89 -> A) a 5 % share (== 5 % -> boundary, NOT marginal)
    # Give c7 (index 78 -> A) a 4.9 % share (< 5 % -> marginal at top)
    # Give c0 (index 0 -> D) a 1 % share (< 5 %, but in D -> NOT at top)
    cmd_inc = {f"c{i}": Observation((i + 1) * 10 / 100, (i + 1) * 10, 100) for i in range(10)}
    counted = {f"c{i}": Observation(0.20, 200, 1000) for i in range(10)}
    counted["c9"] = Observation(0.02, 20, 1000)
    counted["c8"] = Observation(0.05, 50, 1000)
    counted["c7"] = Observation(0.049, 49, 1000)
    counted["c0"] = Observation(0.01, 10, 1000)

    settings = StrengthSettings(
        weights={
            COMMANDER_INCLUSION: 1.0,
            BRACKET_INCLUSION: 0.0,
            DECK_UNIVERSE: 0.0,
            SYNERGY: 0.0,
            TOURNAMENT_LISTS: 0.0,
            GLOBAL_INCLUSION: 0.0,
            COMBOS: 0.0,
            PLAYGROUP_OBSERVED: 0.0,
        },
        share_scale="rank",
        tier_cuts={"S": 90.0, "A": 75.0, "B": 55.0, "C": 35.0},
        min_components=1,
        min_coverage=0.1,
    )
    names = {f"c{i}": f"Card {i}" for i in range(10)}
    report = check_ranking(
        settings,
        _obs(cards, {COMMANDER_INCLUSION: cmd_inc}),
        {COMMANDER_INCLUSION},
        names=names,
        counted_lists=counted,
    )
    assert report["marginal_top"]["of_s_and_a"] == 3  # c9 (S), c8 (A), c7 (A)
    assert report["marginal_top"]["count"] == 2
    assert report["marginal_top"]["names"] == ["Card 9", "Card 7"]

    # Counterexample: when c9 and c7 have >= 5 % share, marginal_top drops to 0
    counted_fixed = dict(counted)
    counted_fixed["c9"] = Observation(0.50, 500, 1000)
    counted_fixed["c7"] = Observation(0.05, 50, 1000)
    fixed_report = check_ranking(
        settings,
        _obs(cards, {COMMANDER_INCLUSION: cmd_inc}),
        {COMMANDER_INCLUSION},
        names=names,
        counted_lists=counted_fixed,
    )
    assert fixed_report["marginal_top"]["count"] == 0
    assert fixed_report["marginal_top"]["names"] == []


def test_metric_3_staples_at_bottom_and_counterexample() -> None:
    """Metric 3: counts and names cards with strictly > 30 % share that land in C or D."""
    cards = [f"c{i}" for i in range(10)]
    cmd_inc = {f"c{i}": Observation((i + 1) * 10 / 100, (i + 1) * 10, 100) for i in range(10)}
    counted = {f"c{i}": Observation(0.10, 100, 1000) for i in range(10)}
    # c0 (tier D) has 45 % share -> staple at bottom
    # c3 (tier C, index 33.3) has 31 % share -> staple at bottom
    # c4 (tier C, index 44.4) has exactly 30 % share -> NOT > 30 %
    # c9 (tier S) has 60 % share -> staple, but at top (counts in denominator of_staples, not count)
    counted["c0"] = Observation(0.45, 450, 1000)
    counted["c3"] = Observation(0.31, 310, 1000)
    counted["c4"] = Observation(0.30, 300, 1000)
    counted["c9"] = Observation(0.60, 600, 1000)

    settings = StrengthSettings(
        weights={
            COMMANDER_INCLUSION: 1.0,
            BRACKET_INCLUSION: 0.0,
            DECK_UNIVERSE: 0.0,
            SYNERGY: 0.0,
            TOURNAMENT_LISTS: 0.0,
            GLOBAL_INCLUSION: 0.0,
            COMBOS: 0.0,
            PLAYGROUP_OBSERVED: 0.0,
        },
        share_scale="rank",
        tier_cuts={"S": 90.0, "A": 75.0, "B": 55.0, "C": 35.0},
        min_components=1,
        min_coverage=0.1,
    )
    names = {f"c{i}": f"Card {i}" for i in range(10)}
    report = check_ranking(
        settings,
        _obs(cards, {COMMANDER_INCLUSION: cmd_inc}),
        {COMMANDER_INCLUSION},
        names=names,
        counted_lists=counted,
    )
    assert report["staples_bottom"]["of_staples"] == 3  # c9, c0, c3
    assert report["staples_bottom"]["count"] == 2
    assert report["staples_bottom"]["names"] == ["Card 0", "Card 3"]

    # Counterexample: when c0 and c3 rank high (in S/A/B), staples_bottom is 0
    cmd_high = dict(cmd_inc)
    cmd_high["c0"] = Observation(0.95, 95, 100)
    cmd_high["c3"] = Observation(0.85, 85, 100)
    cmd_high["c8"] = Observation(0.05, 5, 100)
    cmd_high["c7"] = Observation(0.15, 15, 100)
    high_report = check_ranking(
        settings,
        _obs(cards, {COMMANDER_INCLUSION: cmd_high}),
        {COMMANDER_INCLUSION},
        names=names,
        counted_lists=counted,
    )
    assert high_report["staples_bottom"]["count"] == 0
    assert high_report["staples_bottom"]["of_staples"] == 3


def test_metric_4_thin_coverage_at_top_and_counterexample() -> None:
    """Metric 4: counts cards in S or A that have fewer than 5 present weighted signals."""
    cards = [f"c{i}" for i in range(6)]
    five_components = (
        COMMANDER_INCLUSION,
        BRACKET_INCLUSION,
        DECK_UNIVERSE,
        SYNERGY,
        GLOBAL_INCLUSION,
    )
    per_comp: dict[str, dict[str, Observation]] = {comp: {} for comp in five_components}
    for i, card in enumerate(cards):
        val = (i + 1) * 10
        # c5 (top card, tier S) gets all 5 signals -> present == 5 (NOT thin)
        # c4 (second card, tier A, index 80.0) gets only 2 signals -> present == 2 (< 5, thin!)
        for idx, comp in enumerate(five_components):
            if card == "c4" and idx >= 2:
                continue
            if comp == SYNERGY:
                per_comp[comp][card] = Observation(float(val))
            else:
                per_comp[comp][card] = Observation(val / 100, val, 100)

    settings = StrengthSettings(
        weights={
            COMMANDER_INCLUSION: 1.0,
            BRACKET_INCLUSION: 1.0,
            DECK_UNIVERSE: 1.0,
            SYNERGY: 1.0,
            TOURNAMENT_LISTS: 0.0,
            GLOBAL_INCLUSION: 1.0,
            COMBOS: 0.0,
            PLAYGROUP_OBSERVED: 0.0,
        },
        share_scale="rank",
        tier_cuts={"S": 90.0, "A": 75.0, "B": 55.0, "C": 35.0},
        min_components=2,
        min_coverage=0.2,
    )
    report = check_ranking(
        settings,
        _obs(cards, per_comp),
        set(five_components),
    )
    assert report["thin_coverage_top"]["of_s_and_a"] == 2  # c5 (S) and c4 (A)
    assert report["thin_coverage_top"]["count"] == 1
    assert report["thin_coverage_top"]["names"] == ["c4"]
    assert report["thin_coverage_top"]["by_signal_count"] == {"2": 1, "5": 1}

    # Counterexample: give c4 all 5 signals -> thin_coverage_top drops to 0
    for comp in five_components[2:]:
        if comp == SYNERGY:
            per_comp[comp]["c4"] = Observation(50.0)
        else:
            per_comp[comp]["c4"] = Observation(0.50, 50, 100)
    full_report = check_ranking(
        settings,
        _obs(cards, per_comp),
        set(five_components),
    )
    assert full_report["thin_coverage_top"]["count"] == 0


def test_metric_5_tier_distribution_and_land_share() -> None:
    """Metric 5: counts per tier (S..D, U, N) and land share per tier (None when count is 0)."""
    cards = ["c1", "c2", "c3", "c4", "c5", "u1", "cmd"]
    cmd_inc = {
        "c1": Observation(0.10, 10, 100),
        "c2": Observation(0.30, 30, 100),
        "c3": Observation(0.50, 50, 100),
        "c4": Observation(0.70, 70, 100),
        "c5": Observation(0.90, 90, 100),
    }
    settings = StrengthSettings(
        weights={
            COMMANDER_INCLUSION: 1.0,
            BRACKET_INCLUSION: 0.0,
            DECK_UNIVERSE: 0.0,
            SYNERGY: 0.0,
            TOURNAMENT_LISTS: 0.0,
            GLOBAL_INCLUSION: 0.0,
            COMBOS: 0.0,
            PLAYGROUP_OBSERVED: 0.0,
        },
        share_scale="rank",
        tier_cuts={"S": 90.0, "A": 75.0, "B": 55.0, "C": 35.0},
        min_components=1,
        min_coverage=0.1,
    )
    ctx = PoolContext(
        type_group={
            "c1": "Creature",
            "c2": "Creature",
            "c3": "Land",
            "c4": "Land",
            "c5": "Land",
            "u1": "Instant",
            "cmd": "Creature",
        },
        unranked={"cmd": strength.NOT_RANKED_COMMANDER},
    )
    report = check_ranking(
        settings,
        _obs(cards, {COMMANDER_INCLUSION: cmd_inc}),
        {COMMANDER_INCLUSION},
        context=ctx,
    )
    by_tier = {row["tier"]: row for row in report["tier_distribution"]}
    assert sum(row["count"] for row in report["tier_distribution"]) == len(cards)
    assert by_tier["S"]["count"] == 1
    assert by_tier["S"]["lands"] == 1
    assert by_tier["S"]["land_share"] == 1.0
    assert by_tier["A"]["count"] == 1
    assert by_tier["A"]["lands"] == 1
    assert by_tier["A"]["land_share"] == 1.0
    assert by_tier["B"]["count"] == 0
    assert by_tier["B"]["land_share"] is None  # empty tier -> None, never 0.0
    assert by_tier["C"]["count"] == 1
    assert by_tier["C"]["lands"] == 1
    assert by_tier["C"]["land_share"] == 1.0
    assert by_tier["D"]["count"] == 2
    assert by_tier["D"]["lands"] == 0
    assert by_tier["D"]["land_share"] == 0.0
    assert by_tier["U"]["count"] == 1
    assert by_tier["N"]["count"] == 1

    # Counterexample: change c5 from Land to Creature -> S land_share drops from 1.0 to 0.0
    ctx_no_land_s = PoolContext(
        type_group={**ctx.type_group, "c5": "Creature"},
        unranked=ctx.unranked,
    )
    report_no_land_s = check_ranking(
        settings,
        _obs(cards, {COMMANDER_INCLUSION: cmd_inc}),
        {COMMANDER_INCLUSION},
        context=ctx_no_land_s,
    )
    by_tier_no_land_s = {row["tier"]: row for row in report_no_land_s["tier_distribution"]}
    assert by_tier_no_land_s["S"]["lands"] == 0
    assert by_tier_no_land_s["S"]["land_share"] == 0.0


def test_metric_6_leave_one_out_stability_and_largest_impact() -> None:
    """Metric 6: leave-one-out stability identifies how many cards change tier per signal
    and names the signal with the largest impact."""
    cards = [f"c{i}" for i in range(6)]
    # Signal 1 and Signal 2 agree completely; Signal 3 is completely inverted
    asc = {f"c{i}": Observation((i + 1) * 10 / 100, (i + 1) * 10, 100) for i in range(6)}
    desc = {f"c{i}": Observation((6 - i) * 10 / 100, (6 - i) * 10, 100) for i in range(6)}

    settings = StrengthSettings(
        weights={
            COMMANDER_INCLUSION: 1.0,
            BRACKET_INCLUSION: 1.0,
            DECK_UNIVERSE: 0.0,
            SYNERGY: 0.0,
            TOURNAMENT_LISTS: 0.0,
            GLOBAL_INCLUSION: 2.0,
            COMBOS: 0.0,
            PLAYGROUP_OBSERVED: 0.0,
        },
        min_components=1,
        min_coverage=0.1,
    )
    report = check_ranking(
        settings,
        _obs(
            cards,
            {
                COMMANDER_INCLUSION: asc,
                BRACKET_INCLUSION: asc,
                GLOBAL_INCLUSION: desc,
            },
        ),
        {COMMANDER_INCLUSION, BRACKET_INCLUSION, GLOBAL_INCLUSION},
    )
    signals_by_name = {row["component"]: row for row in report["stability"]["signals"]}
    assert set(signals_by_name) == {COMMANDER_INCLUSION, BRACKET_INCLUSION, GLOBAL_INCLUSION}
    assert (
        signals_by_name[GLOBAL_INCLUSION]["tier_changes"]
        > signals_by_name[COMMANDER_INCLUSION]["tier_changes"]
    )
    assert report["stability"]["largest_impact"] is not None
    assert report["stability"]["largest_impact"]["component"] == GLOBAL_INCLUSION

    # Counterexample: when all 3 signals are identical, omitting any single one changes 0 tiers
    agree_report = check_ranking(
        settings,
        _obs(
            cards,
            {
                COMMANDER_INCLUSION: asc,
                BRACKET_INCLUSION: asc,
                GLOBAL_INCLUSION: asc,
            },
        ),
        {COMMANDER_INCLUSION, BRACKET_INCLUSION, GLOBAL_INCLUSION},
    )
    for row in agree_report["stability"]["signals"]:
        assert row["tier_changes"] == 0


def test_cli_ranking_check_renders_text_and_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI subcommand ``ranking-check`` runs on a StudioStore and outputs text and JSON."""
    from commander_lab.studio import signals
    from tests.unit.test_studio_builder import _fill
    from tests.unit.test_studio_strength import COMMANDER, _write_signals

    studio_dir = tmp_path / "studio"
    store = StudioStore.open(studio_dir)
    try:
        _fill(store, tmp_path)
        _write_signals(tmp_path / "signals")
        signals.import_signals(store, tmp_path / "signals", commander=COMMANDER)
        strength_view.save_profile(store, "MeinProfil", StrengthSettings(min_coverage=0.1))
    finally:
        store.close()

    code = studio_cli.main(
        [
            "--data",
            str(studio_dir),
            "ranking-check",
            "--commander",
            COMMANDER,
            "--preset",
            "Ausgewogen",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert f"Prüfzahlen für die Rangfolge: {COMMANDER} (Ausgewogen)" in out
    assert "Plausibilitäts-Anker" in out
    assert '"schema": "studio-ranking-check-1"' in out

    # JSON-only mode with saved --profile
    code_json = studio_cli.main(
        [
            "--data",
            str(studio_dir),
            "ranking-check",
            "--commander",
            COMMANDER,
            "--profile",
            "MeinProfil",
            "--json",
        ]
    )
    assert code_json == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == SCHEMA
    assert payload["profile_or_preset"] == "MeinProfil"
    assert render_ranking_check(payload).startswith("Prüfzahlen für die Rangfolge:")

    with pytest.raises(SystemExit, match="ranking-check:"):
        studio_cli.main(
            [
                "--data",
                str(studio_dir),
                "ranking-check",
                "--commander",
                COMMANDER,
                "--profile",
                "Unbekannt",
            ]
        )
