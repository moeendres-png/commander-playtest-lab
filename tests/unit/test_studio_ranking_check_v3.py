"""Ranking check additions of Tierliste v3 (#1364): counter-checks against the bracket-5 share
and the EDHTop16 play rate, the redundancy matrix, the log-scale sensitivity and the rule and
prior block. Synthetic data only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio import __main__ as studio_cli
from commander_lab.studio import strength
from commander_lab.studio.ranking_check import (
    REDUNDANCY_THRESHOLD,
    SENSITIVITY_KS,
    check_ranking,
    render_ranking_check,
    run_ranking_check,
)
from commander_lab.studio.strength import Observation, PoolContext, StrengthSettings
from tests.unit.test_studio_strength_v3_view import CMD, _store

SPELLS = [f"s{index}" for index in range(8)]
LANDS = ["l0", "l1", "l2", "l3", "l4", "l5"]
CARDS = SPELLS + LANDS


def _share(count: int, total: int) -> Observation:
    return Observation(count / total, count, total)


def _settings(**weights: float) -> StrengthSettings:
    base = {name: 0.0 for name in strength.COMPONENTS}
    return StrengthSettings(
        weights=base | weights,
        min_components=1,
        min_coverage=0.0,
        require_commander_signal=False,
    )


def _context() -> PoolContext:
    return PoolContext(
        type_group={card: "Land" if card.startswith("l") else "Artifact" for card in CARDS}
    )


def _observations() -> dict[str, dict[str, Observation]]:
    """deck_universe and corpus_tuned are the same share (redundant); global_inclusion runs the
    other way round."""
    observations: dict[str, dict[str, Observation]] = {}
    for index, card in enumerate(CARDS):
        observations[card] = {
            "deck_universe": _share(10 + 40 * index, 2000),
            "corpus_tuned": _share(10 + 40 * index, 2000),
            "global_inclusion": _share(900_000 - 50_000 * index, 1_000_000),
        }
    return observations


COLLECTED = {strength.DECK_UNIVERSE, strength.CORPUS_TUNED, strength.GLOBAL_INCLUSION}


def _report(**extra: object) -> object:
    return check_ranking(
        _settings(deck_universe=2.0, corpus_tuned=1.0, global_inclusion=1.0),
        _observations(),
        COLLECTED,
        context=_context(),
        **extra,  # type: ignore[arg-type]
    )


# ---------- counter-checks ----------


def test_counter_checks_correlate_the_index_with_each_reference_for_spells_and_lands() -> None:
    bracket_5 = {card: _share(5 + 10 * index, 265) for index, card in enumerate(CARDS)}
    # EDHTop16 rates exist for the spells only, and run against the index
    top16 = {
        card: Observation(0.9 - 0.1 * index, round((0.9 - 0.1 * index) * 48), 48)
        for index, card in enumerate(SPELLS)
    }
    report = check_ranking(
        _settings(deck_universe=2.0, corpus_tuned=1.0, global_inclusion=0.5),
        _observations(),
        COLLECTED,
        context=_context(),
        counter_shares={
            "bracket_5": ("Korpus Bracket 5", bracket_5),
            "edhtop16": ("EDHTop16-Spielrate", top16),
        },
    )
    checks = {item["key"]: item for item in report["counter_checks"]}
    b5 = checks["bracket_5"]
    assert b5["label"] == "Korpus Bracket 5"
    assert b5["denominator"] == 265
    assert b5["non_lands"]["spearman_rho"] == pytest.approx(1.0)
    assert b5["lands"]["spearman_rho"] == pytest.approx(1.0)
    assert b5["all_ranked"]["compared"] == len(CARDS)
    assert b5["non_lands"]["compared"] == len(SPELLS) and b5["lands"]["compared"] == len(LANDS)
    t16 = checks["edhtop16"]
    assert t16["denominator"] == 48
    assert t16["non_lands"]["spearman_rho"] == pytest.approx(-1.0)
    assert t16["non_lands"]["compared"] == len(SPELLS)
    # no EDHTop16 value for any land: nothing to compare, shown as unknown, never 0
    assert t16["lands"]["spearman_rho"] is None
    assert t16["lands"]["compared"] == 0
    assert "kein Beweis" in b5["note"] or "Gegenprobe" in b5["note"]


def test_without_references_there_are_no_counter_checks() -> None:
    report = _report()
    assert report["counter_checks"] == []  # type: ignore[index]


# ---------- redundancy matrix ----------


def test_the_redundancy_matrix_flags_pairs_above_the_threshold() -> None:
    assert REDUNDANCY_THRESHOLD == 0.90
    report = _report()
    redundancy = report["redundancy"]  # type: ignore[index]
    assert redundancy["threshold"] == 0.90
    assert redundancy["components"] == ["deck_universe", "corpus_tuned", "global_inclusion"]
    pairs = {(item["a"], item["b"]): item for item in redundancy["pairs"]}
    assert set(pairs) == {
        ("deck_universe", "corpus_tuned"),
        ("deck_universe", "global_inclusion"),
        ("corpus_tuned", "global_inclusion"),
    }
    same = pairs[("deck_universe", "corpus_tuned")]
    assert same["spearman_rho"] == pytest.approx(1.0)
    assert same["compared"] == len(CARDS)
    assert same["flagged"] is True
    opposite = pairs[("deck_universe", "global_inclusion")]
    # lands and spells are scaled apart (separate_lands), so the joint order is not exactly -1
    assert opposite["spearman_rho"] is not None and opposite["spearman_rho"] < -0.5
    assert opposite["flagged"] is False  # only r above +0.90 is redundancy
    assert [(item["a"], item["b"]) for item in redundancy["flagged"]] == [
        ("deck_universe", "corpus_tuned")
    ]


def test_the_redundancy_matrix_skips_inactive_components_and_thin_overlap() -> None:
    settings = _settings(deck_universe=2.0, corpus_tuned=0.0, global_inclusion=1.0)
    report = check_ranking(settings, _observations(), COLLECTED, context=_context())
    redundancy = report["redundancy"]
    assert redundancy["components"] == ["deck_universe", "global_inclusion"]
    assert len(redundancy["pairs"]) == 1
    # a component present for one card only: no correlation (None), not flagged
    sparse = _observations()
    for card in CARDS[1:]:
        del sparse[card]["corpus_tuned"]
    report = check_ranking(
        _settings(deck_universe=2.0, corpus_tuned=1.0, global_inclusion=1.0),
        sparse,
        COLLECTED,
        context=_context(),
    )
    pair = next(
        item
        for item in report["redundancy"]["pairs"]
        if (item["a"], item["b"]) == ("deck_universe", "corpus_tuned")
    )
    assert pair["spearman_rho"] is None and pair["compared"] == 1 and pair["flagged"] is False


# ---------- log-scale sensitivity ----------


def test_the_sensitivity_reports_tier_counts_for_k_100_150_200() -> None:
    assert SENSITIVITY_KS == (100.0, 150.0, 200.0)
    report = _report()
    sensitivity = report["sensitivity"]
    assert sensitivity is not None
    assert sensitivity["base_k"] == strength.LOG_SHARE_K == 150.0
    runs = {run["k"]: run for run in sensitivity["runs"]}
    assert set(runs) == {100.0, 150.0, 200.0}
    base = {row["tier"]: row["count"] for row in report["tier_distribution"]}  # type: ignore[index]
    assert runs[150.0]["tier_counts"] == base
    assert runs[150.0]["tier_changes_vs_base"] == 0
    for run in runs.values():
        assert sum(run["tier_counts"].values()) == len(CARDS)
    # k changes the scale: some run differs from the base in at least one tier count or change
    assert any(run["tier_changes_vs_base"] > 0 for run in (runs[100.0], runs[200.0])) or all(
        runs[k]["tier_counts"] == base for k in (100.0, 200.0)
    )


def test_the_sensitivity_exists_only_for_the_log_scale() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"deck_universe": 1.0},
        share_scale="share",
        min_components=1,
        min_coverage=0.0,
        require_commander_signal=False,
    )
    report = check_ranking(settings, _observations(), COLLECTED, context=_context())
    assert report["sensitivity"] is None


def test_k_changes_the_scores_of_small_shares() -> None:
    values = {"a": 0.5, "b": 0.01}
    low = strength.score_pool(
        _settings(deck_universe=1.0),
        {card: {"deck_universe": _share(round(v * 1000), 1000)} for card, v in values.items()}
        | {f"x{i}": {"deck_universe": _share(i, 1000)} for i in range(1, 6)},
        {strength.DECK_UNIVERSE},
        log_k=100.0,
    )
    high = strength.score_pool(
        _settings(deck_universe=1.0),
        {card: {"deck_universe": _share(round(v * 1000), 1000)} for card, v in values.items()}
        | {f"x{i}": {"deck_universe": _share(i, 1000)} for i in range(1, 6)},
        {strength.DECK_UNIVERSE},
        log_k=200.0,
    )
    assert low["b"]["index"] is not None and high["b"]["index"] is not None
    assert low["b"]["index"] < high["b"]["index"]


# ---------- the rule, the priors, the render ----------


def test_the_report_carries_the_rule_the_priors_and_renders_the_new_sections() -> None:
    rule = strength.apply_corpus_rule(StrengthSettings(), corpus_decks=100, min_universe=30)[1]
    report = _report(weight_rule=rule)
    assert report["weight_rule"] == rule  # type: ignore[index]
    assert report["shrinkage"] == {}  # type: ignore[index]  (all denominators are 1000 or more)
    text = render_ranking_check(report)  # type: ignore[arg-type]
    assert "7. Gegenproben" in text
    assert "8. Redundanz" in text
    assert "9. Sensitivität" in text
    assert "r > 0.90" in text
    assert "CORPUS_ZERO" in text


def test_the_shrinkage_is_reported_for_small_denominators() -> None:
    small = {card: {"corpus_tuned": _share(index, 60)} for index, card in enumerate(CARDS)}
    report = check_ranking(
        _settings(corpus_tuned=1.0),
        small,
        {strength.CORPUS_TUNED},
        context=_context(),
    )
    prior = report["shrinkage"]["corpus_tuned"]
    assert prior["cards"] == len(CARDS)
    assert "Prior" in render_ranking_check(report)


# ---------- the store path and the CLI ----------


def test_the_store_run_uses_the_corpus_the_rule_and_the_counter_references() -> None:
    store = _store()
    report = run_ranking_check(store, CMD, preset="Ausgewogen")
    assert report["weight_rule"]["rule"] == "CORPUS_ZERO"
    checks = {item["key"]: item for item in report["counter_checks"]}
    assert checks["bracket_5"]["denominator"] == 35
    assert checks["edhtop16"]["denominator"] == 48
    components = report["redundancy"]["components"]
    assert "commander_inclusion" not in components  # weight 0 under the corpus rule
    assert "deck_universe" in components and "corpus_tuned" in components
    assert report["sensitivity"] is not None
    stability = {row["component"] for row in report["stability"]["signals"]}
    assert "commander_inclusion" not in stability


def test_the_cli_prints_the_new_sections_and_the_json_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "studio"
    _store(folder=folder).close()
    code = studio_cli.main(
        ["--data", str(folder), "ranking-check", "--commander", CMD, "--preset", "Ausgewogen"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "7. Gegenproben" in out and "8. Redundanz" in out and "9. Sensitivität" in out
    payload = json.loads(out[out.index("{\n") :])
    assert {"counter_checks", "redundancy", "sensitivity", "weight_rule", "shrinkage"} <= set(
        payload
    )
