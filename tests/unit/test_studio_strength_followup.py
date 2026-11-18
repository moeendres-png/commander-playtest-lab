"""Strength index follow-up to #1275: truthful reasons, tiers on the shown index, configurable
other commanders, oracle_id fallback parity. Synthetic data only."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from scripts import import_card_understanding as importer

from commander_lab.studio import (
    StudioStore,
    card_understanding,
    overall_rating,
    strength,
    strength_view,
    universe,
)
from commander_lab.studio.strength import Observation, PoolContext, StrengthSettings
from commander_lab.studio.web import create_app
from tests.unit.studio_synth import add_card, add_deck, add_signal, make_store

CMD = "Cmd A"
INCLUSION = "edhrec_commander_inclusion"
CARDS = [f"Card {index:02d}" for index in range(6)]


def _store(folder: Path | None = None) -> StudioStore:
    store = make_store(folder)
    add_card(store, CMD, type_line="Legendary Creature — Test")
    add_card(store, "Other Cmd", type_line="Legendary Creature — Test")
    add_card(store, "Forest", type_line="Basic Land — Forest", basic=True)
    for name in CARDS:
        add_card(store, name)
    for index, name in enumerate(CARDS[:5]):  # one source only: 5 of 6 cards listed
        add_signal(store, CMD, INCLUSION, name, 90 - 10 * index, 100)
    add_signal(store, "Other Cmd", INCLUSION, "Card 00", 1, 10)  # makes "Other Cmd" known
    return store


def _cards(result: strength_view.StrengthResult) -> dict[str, strength_view.StrengthCard]:
    return {card["name"]: card for card in result["cards"]}


def test_a_filter_card_leaves_the_deck_universe_out_of_its_denominator() -> None:
    """Main's denominator (every weighted component the source can exist for, here 10.5: 3 + 2 +
    4 + 1 + 0.5) minus the deck universe (4) for a filter card: 3 of 6.5 for a card with only the
    commander inclusion; the control card, which is no filter card, has the same signal and the
    universe too: 7 of 10.5."""
    settings = StrengthSettings(min_coverage=0.0, min_components=1)
    obs = {
        "x": {"commander_inclusion": Observation(0.9, 90, 100)},
        "y": {
            "commander_inclusion": Observation(0.5, 50, 100),
            "deck_universe": Observation(0.5, 50, 100),
        },
        "z": {
            "commander_inclusion": Observation(0.1, 10, 100),
            "deck_universe": Observation(0.1, 10, 100),
        },
        "w": {"commander_inclusion": Observation(0.3, 30, 100)},  # control: not a filter card
    }
    collected = {strength.COMMANDER_INCLUSION, strength.DECK_UNIVERSE}
    scored = strength.score_pool(
        settings, obs, collected, context=PoolContext(filter_cards=frozenset({"x"}))
    )
    assert scored["x"]["coverage"] == pytest.approx(3 / 6.5, abs=1e-4)
    assert scored["w"]["coverage"] == pytest.approx(3 / 10.5, abs=1e-4)
    assert scored["y"]["coverage"] == pytest.approx(7 / 10.5, abs=1e-4)


def test_no_positive_weight_and_no_source_have_their_own_reasons() -> None:
    zero = StrengthSettings(weights={name: 0.0 for name in strength.COMPONENTS})
    obs = {"a": {"commander_inclusion": Observation(0.9, 90, 100)}}
    only = strength.score_pool(zero, obs, {"commander_inclusion"})["a"]
    assert only["index"] is None and only["tier"] == "U"
    assert only["reason"] == "NO_POSITIVE_WEIGHT"  # not ENOUGH_DATA, not TOO_LITTLE_DATA
    nothing = strength.score_pool(StrengthSettings(), {"a": {}}, set())["a"]
    assert nothing["reason"] == "NO_SOURCE_FOR_COMMANDER" and nothing["tier"] == "U"


def test_the_tier_follows_the_index_as_shown() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"synergy": 1.0},
        tier_cuts={"S": 90.0, "A": 66.7, "B": 40.0, "C": 10.0},
        min_coverage=0.0,
        min_components=1,
    )
    values = zip("abcd", (1, 2, 3, 4), strict=True)
    obs = {key: {"synergy": Observation(value)} for key, value in values}
    result = strength.score_pool(settings, obs, {"synergy"})
    assert result["c"]["index"] == 66.7  # raw 66.666...: shown as 66.7
    assert result["c"]["tier"] == "A"  # the shown value meets the cut 66.7: never "66.7 but B"


def test_other_commanders_are_ranked_by_default_and_not_when_switched_off() -> None:
    store = _store()
    default = _cards(strength_view.compute(store, CMD, StrengthSettings()))
    assert default["Other Cmd"]["tier"] != "N"  # ranked like any card by default
    assert StrengthSettings().rank_other_commanders is True
    cards = _cards(strength_view.compute(store, CMD, StrengthSettings(rank_other_commanders=False)))
    assert cards["Other Cmd"]["tier"] == "N"
    assert cards["Other Cmd"]["reason"] == strength.NOT_RANKED_OTHER_COMMANDER
    assert cards[CMD]["tier"] == "N" and cards["Forest"]["tier"] == "N"
    # They take no part in the percentile population: Card 00 is the top of the five listed.
    top = next(c for c in cards["Card 00"]["components"] if c["component"] == "commander_inclusion")
    assert top["percentile"] == 1.0
    on = _cards(strength_view.compute(store, CMD, StrengthSettings(rank_commander_and_basics=True)))
    assert on["Other Cmd"]["tier"] != "N"


def test_the_deck_universe_filter_card_has_the_universe_out_of_its_denominator() -> None:
    store = _store()
    for index in range(40):
        add_deck(store, f"d{index}", ["Card 00", "Card 01"])
    universe.save_profile(store, "mit", {"min_universe": 5, "must_contain": ["Card 00"]})
    # 40 local decks are a counted corpus: keep the EDHREC weights (E2.a off) so that the control
    # card still has its commander inclusion in the denominator, as this test measures
    result = strength_view.compute(
        store, CMD, StrengthSettings(universe_profile="mit", edhrec_with_corpus=True)
    )
    cards = _cards(result)
    status = {c["component"]: c["status"] for c in cards["Card 00"]["components"]}
    assert status["deck_universe"] == strength.FILTER_CARD
    # the filter card has the universe weight (4) out of its denominator: 3 of 6.5; the control
    # card of the same pool has the commander inclusion and the universe present: 7 of 10.5
    assert cards["Card 00"]["coverage"] == pytest.approx(3 / 6.5, abs=1e-4)
    assert cards["Card 01"]["coverage"] == pytest.approx(7 / 10.5, abs=1e-4)
    with pytest.raises(KeyError):
        strength_view.compute(store, CMD, StrengthSettings(universe_profile="nope"))


def test_the_minimum_number_of_signals_never_exceeds_the_weighted_components() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"commander_inclusion": 1.0},
        min_coverage=0.0,
        min_components=3,
    )
    obs = {"a": {"commander_inclusion": Observation(0.9, 90, 100)}}
    scored = strength.score_pool(settings, obs, {strength.COMMANDER_INCLUSION})
    assert scored["a"]["tier"] != "U" and scored["a"]["reason"] == "ENOUGH_DATA"


def test_a_deck_row_with_an_oracle_id_counts_for_the_card_under_any_spelling() -> None:
    from commander_lab.studio import builder, universe_view

    store = make_store()
    add_card(store, CMD, type_line="Legendary Creature — Test")
    fire_id = add_card(store, "Fire // Ice")
    vault_id = add_card(store, "Lim-Dûl's Vault")
    db = store.connection
    db.execute("UPDATE card SET oracle_id = 'o-fire' WHERE oracle_name = 'Fire // Ice'")
    db.execute("UPDATE card SET oracle_id = 'o-vault' WHERE oracle_name = 'Lim-Dûl''s Vault'")
    add_deck(store, "d1", ["Fire", "Lim-Dul's Vault"])
    add_deck(store, "d2", ["Fire // Ice"])
    db.execute(
        "UPDATE corpus_deck_card SET oracle_id = 'o-vault' WHERE card_name = 'Lim-Dul''s Vault'"
    )
    pool = builder.pool_cards(store, [CMD], with_signals=False)
    cards = {str(c["name"]): c for c in pool["cards"]}  # type: ignore[attr-defined]
    assert cards["Fire // Ice"]["decks"]["all"] == 2  # front face "Fire" + the full name
    assert cards["Lim-Dûl's Vault"]["decks"]["all"] == 1  # accent spelling, found by its id
    assert cards["Lim-Dûl's Vault"]["decks_known"] is True

    universe.save_profile(store, "alle", {"min_universe": 1})
    spread = {
        c["name"]: c
        for c in universe_view.pool_spread(store, "alle", commander_names=[CMD])["cards"]
    }
    assert spread["Lim-Dûl's Vault"]["matched"] is True
    assert spread["Lim-Dûl's Vault"]["matched_name"] == "Lim-Dul's Vault"
    assert spread["Lim-Dûl's Vault"]["hits"] == 1

    co_fire = universe_view.card_cooccurrence(store, "alle", fire_id, commander_names=[CMD])
    co_vault = universe_view.card_cooccurrence(store, "alle", vault_id, commander_names=[CMD])
    assert co_vault["matched"] is True and co_vault["decks_with_card"] == 1
    assert any(
        p["card_name"] == "Lim-Dûl's Vault" and p["decks_together"] == 1 for p in co_fire["pairs"]
    )
    assert any(
        p["card_name"] == "Fire // Ice" and p["decks_together"] == 1 for p in co_vault["pairs"]
    )

    computed = _cards(strength_view.compute(store, CMD, StrengthSettings(universe_profile="alle")))
    vault_comp = next(
        c for c in computed["Lim-Dûl's Vault"]["components"] if c["component"] == "deck_universe"
    )
    assert vault_comp["status"] == strength.PRESENT
    assert vault_comp["numerator"] == 1 and vault_comp["denominator"] == 2


def test_other_commander_names_matches_case_insensitively() -> None:
    store = _store()
    others = strength_view._other_commander_names(store, "other cmd")
    assert "other cmd" not in others
    assert "cmd a" in others


def test_filter_card_removing_sole_weighted_signal_gets_too_little_data() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"deck_universe": 1.0},
        min_coverage=0.0,
        min_components=1,
        require_commander_signal=False,
    )
    obs = {"x": {}, "y": {"deck_universe": Observation(0.5, 5, 10)}}
    scored = strength.score_pool(
        settings,
        obs,
        {strength.DECK_UNIVERSE},
        context=PoolContext(filter_cards=frozenset({"x"})),
    )
    assert scored["x"]["tier"] == "U"
    assert scored["x"]["reason"] == "TOO_LITTLE_DATA"


def test_bracket_labels_follow_the_bracket_column_of_the_imported_files() -> None:
    import csv
    from pathlib import Path

    folder = Path(__file__).resolve().parents[2] / "data" / "research" / "deckbuilder_1655"
    seen: dict[str, str] = {}
    for variant in strength.BRACKETS:
        path = folder / f"commander_bracket_signals_{variant}_1.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        assert row["variant"] == variant
        seen[variant] = row["bracket"]
    assert seen == {"core": "2", "upgraded": "3", "optimized": "4", "cedh": "5"}
    choices = strength_view.presets()["panel"]["choices"]["bracket"]  # type: ignore[index,call-overload]
    served = {choice["value"]: choice["label"] for choice in choices}
    for variant, number in seen.items():
        assert f"Bracket {number})" in served[variant], (variant, served[variant])


def test_the_two_ranking_switches_are_independent() -> None:
    store = _store()
    both = StrengthSettings(rank_commander_and_basics=True, rank_other_commanders=False)
    cards = _cards(strength_view.compute(store, CMD, both))
    # the commander card and basics are ranked, the other commander card still is not
    assert cards["Other Cmd"]["tier"] == "N"
    assert cards["Other Cmd"]["reason"] == strength.NOT_RANKED_OTHER_COMMANDER
    assert cards["Forest"]["tier"] != "N"


# ---------- second overall rating: Kartenverständnis-Gesamtrating (#1369) ----------

SCORES = {"E": 60, "F": 70, "T": 40, "R": 50, "K": 20, "D": 80, "H": 65}


def _row(oracle_id: str, card: str = "Card", **changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "oracle_id": oracle_id,
        "card": card,
        "scores": dict(SCORES),
        "confidence": "high",
        "reason": "According to the card text it does one small thing.",
        "notes": {"H": "small"},
        "rule_claims": [],
        "version": "v2.1",
        "rater_tier": "large",
        "rubric": "chulane-rubric-v2.1",
    }
    return row | changes


def _dataset(rows: list[dict[str, object]]) -> dict[str, card_understanding.UnderstandingRow]:
    return card_understanding.parse_lines([json.dumps(row) for row in rows])


def _with_oracle_ids(store: StudioStore, names: list[str]) -> None:
    for name in names:
        store.connection.execute(
            "UPDATE card SET oracle_id = ? WHERE oracle_name = ?", (f"o-{name}", name)
        )


def _scored_answer() -> tuple[StudioStore, strength_view.StrengthResult]:
    store = _store()
    _with_oracle_ids(store, CARDS)
    return store, strength_view.compute(store, CMD, StrengthSettings())


def test_the_overall_rating_only_adds_fields_and_leaves_the_usage_index_as_it_was() -> None:
    store, answer = _scored_answer()
    before = copy.deepcopy(answer)
    data = _dataset(
        [
            _row("o-Card 00", scores=SCORES | {"H": 90}),
            _row("o-Card 01", scores=SCORES | {"H": 30}),
            _row("o-Card 03"),
        ]
    )
    after = overall_rating.with_overall(store, answer, dataset=data, commander=CMD)
    assert answer == before  # the given (possibly remembered) answer is not modified
    assert set(after) - set(before) == {"overall_meta"}
    stripped = [{k: v for k, v in card.items() if k != "overall"} for card in after["cards"]]  # type: ignore[attr-defined]
    assert stripped == before["cards"]
    assert all("overall" in card for card in after["cards"])  # type: ignore[attr-defined]
    for key in before:
        if key != "cards":
            assert after[key] == before[key], key
    meta = after["overall_meta"]
    assert meta["n_rated"] == 3 and meta["n_total"] == len(before["cards"])  # type: ignore[index]
    assert meta["version"] == overall_rating.OVERALL_RULES_VERSION  # type: ignore[index]
    assert "große Stufe" in meta["caveat"] and meta["weights_note"] == "Setzung, keine Messung"  # type: ignore[index,operator]


def test_the_breakdown_adds_up_to_the_score_exactly() -> None:
    probes = [
        {"usage": 83.3, "H": 65, "F": 70, "E": 60, "T": 40, "R": 50, "D": 80, "K": 20},
        {"usage": 12.7, "H": 5, "F": 95, "E": 35, "T": 15, "R": 85, "D": 45, "K": 55},
        {"usage": None, "H": 45, "F": 25, "E": 60, "T": 40, "R": 50, "D": 80, "K": 20},
        {"usage": None, "H": 33, "F": 77, "E": 11, "T": 99, "R": 1, "D": 66, "K": 44},
    ]
    for values in probes:
        found = overall_rating.decompose(values)
        assert found is not None
        total = sum(item["contribution"] for item in found["axes"])
        assert total == pytest.approx(found["score"], abs=1e-9), values
        assert sum(item["weight_effective"] for item in found["axes"]) == pytest.approx(1, abs=1e-3)
    assert sum(overall_rating.OVERALL_WEIGHTS_V1.values()) == pytest.approx(1.0)
    assert overall_rating.OVERALL_WEIGHTS_V1["usage"] == 0.30


def test_a_card_without_a_rating_is_unknown_never_zero() -> None:
    store, answer = _scored_answer()
    data = _dataset([_row("o-Card 00"), _row("o-Card 01")])
    after = overall_rating.with_overall(store, answer, dataset=data, commander=CMD)
    by_name = {card["name"]: card["overall"] for card in after["cards"]}  # type: ignore[attr-defined]
    missing = by_name["Card 05"]
    assert missing["score"] is None and missing["rank"] is None and missing["axes"] == []
    assert (
        missing["status"] == "unbekannt" and "keine Kartenverständnis" in missing["unknown_reason"]
    )
    assert by_name["Card 00"]["score"] is not None
    assert all(item["n_rated"] == 2 for item in by_name.values())
    assert after["overall_meta"]["n_rated"] == 2  # type: ignore[index]


def test_missing_axes_renormalise_and_report_the_coverage() -> None:
    full = overall_rating.decompose({"usage": 50.0} | dict(SCORES))
    without = overall_rating.decompose({"usage": None} | dict(SCORES))
    assert full is not None and without is not None
    assert full["coverage"] == 1.0 and without["coverage"] == pytest.approx(0.7)
    by_axis = {item["axis"]: item for item in without["axes"]}
    assert "usage" not in by_axis
    assert by_axis["H"]["weight_effective"] == pytest.approx(0.3 / 0.7, abs=1e-4)
    # too few axes: below the minimum coverage there is no score, never 0
    assert overall_rating.decompose({"H": 80.0, "F": 80.0, "usage": 40.0}) is not None  # 0.75
    assert overall_rating.decompose({"H": 80.0, "F": 80.0}) is None  # 0.45
    assert overall_rating.decompose({"usage": 90.0}) is None
    assert overall_rating.decompose({}) is None


def test_usage_index_of_an_unranked_card_is_a_missing_axis_not_a_zero() -> None:
    store, answer = _scored_answer()
    data = _dataset([_row(f"o-{name}") for name in CARDS])
    after = overall_rating.with_overall(store, answer, dataset=data, commander=CMD)
    rated = [c for c in after["cards"] if c["name"] in CARDS]  # type: ignore[attr-defined]
    assert len(rated) == len(CARDS)
    for card in rated:
        axes = {item["axis"] for item in card["overall"]["axes"]}
        has_usage = card["tier"] in strength.TIERS and card["index"] is not None
        assert ("usage" in axes) is has_usage, card["name"]
        assert card["overall"]["coverage"] == (1.0 if has_usage else 0.7), card["name"]


def test_ranks_share_the_best_rank_on_ties() -> None:
    ranks = overall_rating.competition_ranks(
        {"a": 50.0, "b": 50.0, "c": 40.0, "d": 60.0, "e": 50.04}
    )
    assert ranks == {"d": 1, "a": 2, "b": 2, "e": 2, "c": 5}
    store, answer = _scored_answer()
    data = _dataset(
        [_row("o-Card 00", scores=SCORES | {"H": 100}), _row("o-Card 01"), _row("o-Card 02")]
    )
    after = overall_rating.with_overall(store, answer, dataset=data, commander=CMD)
    rated = [c["overall"] for c in after["cards"] if c["overall"]["score"] is not None]  # type: ignore[attr-defined]
    assert sorted(item["rank"] for item in rated)[0] == 1 and len(rated) == 3
    for item in rated:
        better = sum(1 for other in rated if other["score"] > item["score"])
        assert item["rank"] == better + 1


def test_the_stability_span_is_deterministic_and_contains_the_rank() -> None:
    first = overall_rating.weight_variants()
    assert first == overall_rating.weight_variants() and len(first) == 80
    assert first[0]["usage"] == pytest.approx(0.30 * 1.2407571359998, abs=1e-9)
    for variant in first:
        for axis, weight in variant.items():
            base = overall_rating.OVERALL_WEIGHTS_V1[axis]
            assert 0.7 * base - 1e-12 <= weight <= 1.3 * base + 1e-12
    values: dict[str, dict[str, float | None]] = {
        f"c{index}": {"usage": 10.0 * index, "H": 100.0 - 7.0 * index, "F": 5.0 * (index % 4)}
        | {axis: 50.0 for axis in "ETRDK"}
        for index in range(12)
    }
    scores = {}
    for card, axes in values.items():
        found = overall_rating.decompose(axes)
        assert found is not None
        scores[card] = found["score"]
    base = overall_rating.competition_ranks(scores)
    spans = overall_rating.rank_spans(values, base)
    assert spans == overall_rating.rank_spans(values, base)
    assert any(low != high for low, high in spans.values())
    for card, (low, high) in spans.items():
        assert low <= base[card] <= high


def test_unsharp_is_a_rank_span_of_ten_percent_of_the_rated_cards() -> None:
    store = _store()
    names = [f"Card {index:02d}" for index in range(6)]
    _with_oracle_ids(store, names)
    answer = strength_view.compute(store, CMD, StrengthSettings())
    data = _dataset(
        [_row(f"o-{name}", scores=SCORES | {"H": 10 * index}) for index, name in enumerate(names)]
    )
    after = overall_rating.with_overall(store, answer, dataset=data, commander=CMD)
    n_rated = after["overall_meta"]["n_rated"]  # type: ignore[index]
    flags = 0
    for card in after["cards"]:  # type: ignore[attr-defined]
        found = card["overall"]
        if found["stability"] is None:
            continue
        span = found["stability"]["rank_max"] - found["stability"]["rank_min"]
        assert found["stability"]["unscharf"] is (span >= 0.1 * n_rated)
        flags += found["stability"]["unscharf"]
    assert after["overall_meta"]["stability"]["unscharf_count"] == flags  # type: ignore[index]


def test_confidence_follows_the_rater_confidence_and_the_h_spread() -> None:
    plain = _dataset([_row("a")])["a"]
    assert overall_rating.confidence_of(plain)["level"] == "high"
    assert overall_rating.confidence_of(plain)["h_sd"] is None  # one rater: unknown, not 0
    low = _dataset([_row("b", confidence="low")])["b"]
    assert overall_rating.confidence_of(low)["uncertain"] is True
    wide_sd = dict.fromkeys(card_understanding.CRITERIA, 5.0) | {"H": 20.0}
    wide = _dataset([_row("c", score_sd=wide_sd, raters=2)])["c"]
    found = overall_rating.confidence_of(wide)
    assert found["uncertain"] and found["level"] == "low" and found["rater_confidence"] == "high"
    narrow = _dataset([_row("d", score_sd=wide_sd | {"H": 19.9}, raters=2)])["d"]
    assert overall_rating.confidence_of(narrow)["uncertain"] is False


def test_the_usage_axis_is_dropped_when_the_index_carries_a_locked_signal() -> None:
    store, answer = _scored_answer()
    data = _dataset([_row(f"o-{name}") for name in CARDS])
    for patch in (
        {"effective_weights": {**answer["effective_weights"], "playgroup_observed": 0.5}},
        {"effective_weights": {**answer["effective_weights"], "rubric": 1.0}},
        {"layer_summary": {**answer["layer_summary"], "weighted": ["tempo"]}},
    ):
        after = overall_rating.with_overall(store, answer | patch, dataset=data, commander=CMD)  # type: ignore[arg-type]
        usage = after["overall_meta"]["usage_axis"]  # type: ignore[index]
        assert (
            usage["included"] is False and usage["excluded_reason"] and usage["n_with_usage"] == 0
        )
        for card in (c for c in after["cards"] if c["name"] in CARDS):  # type: ignore[attr-defined]
            assert card["overall"]["coverage"] == 0.7 and card["overall"]["score"] is not None


def test_another_commander_gets_no_overall_rating() -> None:
    store, answer = _scored_answer()
    data = _dataset([_row(f"o-{name}") for name in CARDS])
    after = overall_rating.with_overall(store, answer, dataset=data, commander="Someone Else")
    assert after["overall_meta"]["available"] is False  # type: ignore[index]
    assert all("overall" not in card for card in after["cards"])  # type: ignore[attr-defined]
    assert after["cards"] == answer["cards"]


def test_the_strength_route_adds_the_overall_fields_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "studio"
    store = _store(folder)
    _with_oracle_ids(store, CARDS)
    store.connection.commit()
    expected = strength_view.compute(store, CMD, StrengthSettings())
    store.close()
    path = tmp_path / "cu.jsonl"
    path.write_text(
        "\n".join(json.dumps(_row(f"o-{name}", name)) for name in CARDS[:4]) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(card_understanding, "DATASET_PATH", path)
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", CMD)
    with TestClient(create_app(folder)) as client:
        body = client.post(
            "/api/strength", json={"commander": CMD}, headers={"X-Studio": "1"}
        ).json()
    assert body["overall_meta"]["n_rated"] == 4 and body["overall_meta"]["available"] is True
    assert [{k: v for k, v in c.items() if k != "overall"} for c in body["cards"]] == json.loads(
        json.dumps(expected["cards"])
    )
    assert body["tier_counts"] == expected["tier_counts"]
    assert sum(1 for c in body["cards"] if c["overall"]["score"] is not None) == 4


# ---------- the data set loader ----------


def test_the_loader_accepts_a_valid_line_and_keeps_the_optional_fields() -> None:
    row = card_understanding.parse_row(
        _row("x", raters=2, rounded=True, score_sd=dict.fromkeys(card_understanding.CRITERIA, 2.5))
    )
    assert row["scores"]["H"] == 65 and row["raters"] == 2 and row["rounded"] is True
    assert card_understanding.parse_row(_row("y", score_sd=None))["score_sd"] is None
    assert card_understanding.load(Path("does/not/exist.jsonl")) == {}


@pytest.mark.parametrize(
    "change",
    [
        {"scores": {k: v for k, v in SCORES.items() if k != "K"}},
        {"scores": SCORES | {"X": 10}},
        {"scores": SCORES | {"H": 101}},
        {"scores": SCORES | {"H": -5}},
        {"scores": SCORES | {"H": True}},
        {"scores": SCORES | {"H": "70"}},
        {"scores": SCORES | {"H": math.inf}},
        {"scores": [1, 2]},
        {"confidence": "certain"},
        {"rater_tier": "medium"},
        {"rater_tier": None},
        {"model": "anything"},
        {"oracle_id": ""},
        {"reason": "  "},
        {"notes": {"Z": "unknown criterion"}},
        {"rule_claims": "none"},
        {"raters": 0},
        {"score_sd": {"H": 1.0}},
        {"rounded": "yes"},
    ],
)
def test_the_loader_rejects_a_broken_line(change: dict[str, object]) -> None:
    with pytest.raises(card_understanding.UnderstandingDataError):
        card_understanding.parse_row(_row("x") | change)


@pytest.mark.parametrize(
    "missing",
    [
        "oracle_id",
        "card",
        "scores",
        "confidence",
        "reason",
        "notes",
        "rule_claims",
        "version",
        "rater_tier",
        "rubric",
    ],
)
def test_the_loader_rejects_a_line_without_a_required_field(missing: str) -> None:
    row = _row("x")
    del row[missing]
    with pytest.raises(card_understanding.UnderstandingDataError, match="missing"):
        card_understanding.parse_row(row)


def test_the_loader_fails_closed_and_names_the_lines() -> None:
    lines = [
        json.dumps(_row("a")),
        "",
        "{not json",
        json.dumps(_row("a")),
        json.dumps(_row("b", scores={})),
    ]
    with pytest.raises(card_understanding.UnderstandingDataError) as caught:
        card_understanding.parse_lines(lines)
    text = str(caught.value)
    assert (
        "3 broken" in text
        and "line 3" in text
        and "line 4" in text
        and "twice" in text
        and "line 5" in text
    )
    with pytest.raises(card_understanding.UnderstandingDataError):
        card_understanding.parse_row([])


def test_a_broken_data_file_makes_the_overall_rating_unavailable_not_wrong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, answer = _scored_answer()
    path = tmp_path / "bad.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(card_understanding, "DATASET_PATH", path)
    after = overall_rating.with_overall(store, answer, commander=CMD)
    assert after["overall_meta"]["available"] is False  # type: ignore[index]
    assert all("overall" not in card for card in after["cards"])  # type: ignore[attr-defined]


def test_the_checked_in_data_set_is_valid_and_matches_its_constants() -> None:
    rows = card_understanding.load(card_understanding.DATASET_PATH)
    assert rows, "the data set is empty"
    for row in rows.values():
        assert row["version"] == card_understanding.DATASET_VERSION
        assert row["rubric"] == card_understanding.DATASET_RUBRIC
        assert all(row["scores"][axis] % 5 == 0 for axis in card_understanding.CRITERIA)


# ---------- the importer ----------


def _raw(oracle_id: str, rater: str, version: str = "v2.1", **changes: object) -> dict[str, object]:
    row = _row(oracle_id, "Card") | {"rater": rater, "batch": f"{rater}_b0", "version": version}
    row.pop("rater_tier")
    row.pop("rubric")
    row["uncertainty"] = ""
    row["pattern_check"] = []
    row["model"] = "ignored"
    return row | changes


def _import(
    rows: list[dict[str, object]], versions: list[str], tmp_path: Path
) -> list[card_understanding.UnderstandingRow]:
    source = tmp_path / "in.jsonl"
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    ratings, _skipped = importer.read_ratings([source], versions, "large")
    lines, _used = importer.build(ratings, versions)
    return lines


def test_the_importer_means_rounds_and_keeps_the_lowest_confidence(tmp_path: Path) -> None:
    rows = [
        _raw("a", "R1", scores=SCORES | {"H": 45, "E": 50}),
        _raw("a", "R2", scores=SCORES | {"H": 50, "E": 50}, confidence="low"),
        _raw("b", "R1"),
    ]
    lines = {line["oracle_id"]: line for line in _import(rows, ["v2.1"], tmp_path)}
    one, single = lines["a"], lines["b"]
    assert one["scores"]["H"] == 50 and one["scores"]["E"] == 50  # 47.5 rounds half up
    assert one["rounded"] is True and one["raters"] == 2 and one["confidence"] == "low"
    assert one["score_sd"]["H"] == pytest.approx(3.54, abs=0.01) and one["score_sd"]["E"] == 0
    assert (
        one["reason"] == rows[1]["reason"]
    )  # the rater whose H is closest to the mean (tie: name)
    assert single["raters"] == 1 and single["score_sd"] is None and single["rounded"] is False
    assert single["rater_tier"] == "large" and "model" not in single


def test_the_importer_prefers_the_better_version_and_rounds_off_grid_scores(tmp_path: Path) -> None:
    rows = [
        _raw("a", "R1", version="v2", scores=SCORES | {"H": 5}),
        _raw("a", "R2", version="v2.1"),
        _raw("c", "R1", version="v2", scores=SCORES | {"H": 44}, rater_tier="small"),
        _raw("d", "R1", version="v1"),
    ]
    lines = {line["oracle_id"]: line for line in _import(rows, ["v2.1", "v2"], tmp_path)}
    assert set(lines) == {"a", "c"}  # v1 is not read
    assert lines["a"]["version"] == "v2.1" and lines["a"]["scores"]["H"] == 65
    assert (
        lines["c"]["version"] == "v2"
        and lines["c"]["scores"]["H"] == 45
        and lines["c"]["rounded"] is True
    )
    assert lines["c"]["rater_tier"] == "small"


def test_the_importer_rejects_a_broken_input_line(tmp_path: Path) -> None:
    source = tmp_path / "in.jsonl"
    source.write_text(
        json.dumps(_raw("a", "R1", scores=SCORES | {"H": 130})) + "\n", encoding="utf-8"
    )
    with pytest.raises(card_understanding.UnderstandingDataError, match=r"in\.jsonl:1"):
        importer.read_ratings([source], ["v2.1"], "large")
    out = tmp_path / "out.jsonl"
    assert importer.main([str(source), "--out", str(out)]) == 2 and not out.exists()


def test_the_importer_output_is_deterministic_and_checkable(tmp_path: Path) -> None:
    source = tmp_path / "in.jsonl"
    source.write_text(
        "\n".join(json.dumps(_raw(o, "R1")) for o in ("b", "a")) + "\n", encoding="utf-8"
    )
    out = tmp_path / "out.jsonl"
    assert importer.main([str(source), "--out", str(out)]) == 0
    first = out.read_text(encoding="utf-8")
    assert importer.main([str(source), "--out", str(out), "--check"]) == 0
    out.write_text(first + "\n", encoding="utf-8")
    assert importer.main([str(source), "--out", str(out), "--check"]) == 1
    assert len(card_understanding.load(out)) == 2
