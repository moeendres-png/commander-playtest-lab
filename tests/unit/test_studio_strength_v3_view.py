"""Tierliste v3 (#1364), store side: the corpus components, the edhtop16 numerator, the EDHREC
theme reach, the E2.a weight rule and the result fields the page needs.

One synthetic commander with a local corpus of 80 decks (20 in bracket 2, 25 in bracket 4, 35 in
bracket 5). Every number here is invented.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, signals, strength, strength_view
from commander_lab.studio.strength import StrengthSettings
from tests.unit.studio_synth import SOURCE, add_card, add_deck, add_signal, make_store

CMD = "Cmd A"
NAMES = [f"Card {index:02d}" for index in range(8)]
LAND = "Land A"
GLOBAL = "edhrec_global_inclusion"
INCLUSION = "edhrec_commander_inclusion"


def _decks(store: StudioStore) -> None:
    """80 local decks. Card 00 in every deck, Card 01 in 30 of the 60 high-bracket decks, Card 02
    in 10 of the 20 bracket-2 decks, Card 03 in one bracket-5 deck, Card 04 in none, Card 05 in
    6 bracket-5 decks, Card 06 in 5 high-bracket and 5 bracket-2 decks, the land in 50 decks."""
    for index in range(80):
        bracket = 2 if index < 20 else 4 if index < 45 else 5
        cards = ["Card 00"]
        if bracket in (4, 5) and index - 20 < 30:
            cards.append("Card 01")
        if bracket == 2 and index < 10:
            cards.append("Card 02")
        if index == 79:
            cards.append("Card 03")
        if bracket == 5 and index >= 74:
            cards.append("Card 05")
        if (bracket == 2 and 10 <= index < 15) or (bracket in (4, 5) and 20 <= index < 25):
            cards.append("Card 06")
        if index < 50:
            cards.append(LAND)
        add_deck(store, f"d{index:02d}", cards, cohorts=[f"bracket:{bracket}", "commander:cmd-a"])


def _theme(store: StudioStore, cohort: str, rows: dict[str, tuple[int, int]]) -> None:
    db = store.connection
    for name, (numerator, denominator) in rows.items():
        db.execute(
            "INSERT INTO observation(card_id, card_name, metric, cohort, value, numerator, "
            "denominator, data_class, url, snapshot, source_id) "
            "VALUES (NULL, ?, 'inclusion_pct', ?, ?, ?, ?, 'ORIGINAL_SOURCE', '', '', ?)",
            (name, cohort, 100.0 * numerator / denominator, numerator, denominator, SOURCE),
        )
    db.execute(
        "INSERT OR IGNORE INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('observation_cohort', ?, ?, 'TEST')",
        (cohort, CMD),
    )


def _store(*, corpus: bool = True, folder: Path | None = None) -> StudioStore:
    store = make_store(folder)
    add_card(store, CMD, type_line="Legendary Creature — Test")
    for name in NAMES:
        add_card(store, name)
    add_card(store, LAND, type_line="Land")
    global_share = {
        "Card 00": 500_000,
        "Card 01": 20_000,
        "Card 02": 200_000,
        "Card 03": 1_000,
        "Card 04": 50_000,
        "Card 05": 10_000,
        "Card 06": 100_000,
        "Card 07": 30_000,
        LAND: 400_000,
    }
    for name, count in global_share.items():
        add_signal(store, "", GLOBAL, name, count, 1_000_000)
    # EDHREC commander inclusion exists for a few cards (the fallback rule uses it)
    for index, name in enumerate(NAMES[:6]):
        add_signal(store, CMD, INCLUSION, name, 900 - 100 * index, 1000)
    # EDHTop16: the rate and the entry count are published, the card count is not (NULL)
    add_signal(store, CMD, signals.SIGNAL_EDHTOP16, "Card 00", None, 48, value=0.9375)
    add_signal(store, CMD, signals.SIGNAL_EDHTOP16, "Card 01", None, 48, value=0.5)
    if corpus:
        _decks(store)
    _theme(store, "edhrec:cmd-a", {"Card 00": (900, 1000)})  # the commander page itself
    _theme(store, "edhrec:cmd-a/ramp", {"Card 00": (60, 100), "Card 01": (10, 100)})
    _theme(store, "edhrec:cmd-a/blink", {"Card 01": (40, 80), "Card 02": (3, 90)})
    _theme(store, "edhrec:cmd-a/tiny", {"Card 01": (5, 5)})  # 5 decks: below the minimum
    _theme(store, "edhrec:cmd-a/optimized", {"Card 02": (99, 100)})  # a bracket page, no theme
    store.connection.commit()
    return store


def _cards(result: strength_view.StrengthResult) -> dict[str, strength_view.StrengthCard]:
    return {card["name"]: card for card in result["cards"]}


def _row(card: strength_view.StrengthCard, component: str) -> strength.ComponentResult:
    return next(row for row in card["components"] if row["component"] == component)


def _compute(store: StudioStore, **kwargs: object) -> strength_view.StrengthResult:
    return strength_view.compute(store, CMD, StrengthSettings(**kwargs))  # type: ignore[arg-type]


# ---------- the corpus components ----------


def test_corpus_tuned_is_the_share_in_brackets_4_and_5_with_numerator_and_denominator() -> None:
    cards = _cards(_compute(_store()))
    row = _row(cards["Card 01"], "corpus_tuned")
    assert row["status"] == "PRESENT"
    assert (row["numerator"], row["denominator"]) == (30, 60)
    assert row["data_class"] == "DERIVED_DESCRIPTIVE"
    assert row["signal"] == "corpus_share:bracket:4+5"
    land = _row(cards[LAND], "corpus_tuned")
    assert (land["numerator"], land["denominator"]) == (30, 60)  # 50 decks: d00..d49
    zero = _row(cards["Card 04"], "corpus_tuned")
    assert zero["status"] == "ZERO_COUNT"
    assert (zero["numerator"], zero["denominator"]) == (0, 60)
    assert zero["percentile"] is not None  # a counted zero counts fully


def test_corpus_log_lift_is_the_damped_log_ratio_against_the_global_share() -> None:
    cards = _cards(_compute(_store()))
    row = _row(cards["Card 01"], "corpus_log_lift")
    # 30 hits of 80 decks (37.5 %) against a global share of 2 %: lift 18.75
    expected = strength.log_lift_value(30, 80, 0.02)
    assert expected is not None
    assert row["status"] == "PRESENT"
    assert row["value"] == pytest.approx(expected)
    # never ranked: the index counts only the part above neutral (0.5), max(0, 2v - 1)
    assert row["percentile"] == pytest.approx(max(0.0, 2 * expected - 1))
    assert (row["numerator"], row["denominator"]) == (30, 80)
    assert "Lift" in row["note"] and "30 von 80" in row["note"]
    # one hit, a tiny global share: damped to near the middle, never an extreme
    tiny = _row(cards["Card 03"], "corpus_log_lift")
    assert tiny["value"] is not None and 0.45 < tiny["value"] < 0.6
    # no hit: no lift (undefined, not low)
    none = _row(cards["Card 04"], "corpus_log_lift")
    assert none["status"] == "NO_VALUE" and none["percentile"] is None


def test_corpus_bracket_slope_compares_brackets_4_5_with_2_from_five_hits() -> None:
    cards = _cards(_compute(_store()))
    up = _row(cards["Card 01"], "corpus_bracket_slope")
    down = _row(cards["Card 02"], "corpus_bracket_slope")
    assert up["value"] == pytest.approx(strength.bracket_slope_value(30, 60, 0, 20))
    assert down["value"] == pytest.approx(strength.bracket_slope_value(0, 60, 10, 20))
    assert up["value"] is not None and down["value"] is not None
    assert up["value"] > 0.5 > down["value"]
    assert (up["numerator"], up["denominator"]) == (30, 60)
    assert "30 von 60" in up["note"] and "0 von 20" in up["note"]
    # fewer than 5 hits: no slope
    assert _row(cards["Card 03"], "corpus_bracket_slope")["status"] == "NO_VALUE"
    assert _row(cards["Card 04"], "corpus_bracket_slope")["status"] == "NO_VALUE"
    # five hits in total (5 + 5 over the two groups) are enough
    assert _row(cards["Card 06"], "corpus_bracket_slope")["status"] == "PRESENT"


def test_tournament_pools_edhtop16_and_the_bracket_5_corpus() -> None:
    cards = _cards(_compute(_store()))
    both = _row(cards["Card 00"], "tournament")
    # EDHTop16: 0.9375 * 48 = 45 of 48 (derived at read time from the published rate and
    # entry count); bracket 5: 35 of 35; pooled 80 of 83
    assert (both["numerator"], both["denominator"]) == (80, 83)
    assert both["status"] == "PRESENT"
    assert "EDHTop16 45 von 48" in both["note"] and "Bracket 5 35 von 35" in both["note"]
    only_corpus = _row(cards["Card 05"], "tournament")
    assert (only_corpus["numerator"], only_corpus["denominator"]) == (6, 35)
    assert "EDHTop16" not in only_corpus["note"]
    zero = _row(cards["Card 04"], "tournament")
    assert zero["status"] == "ZERO_COUNT"
    assert (zero["numerator"], zero["denominator"]) == (0, 35)
    both_sources = _row(cards["Card 01"], "tournament")  # 24 of 48 and 5 of 35 bracket-5 decks
    assert (both_sources["numerator"], both_sources["denominator"]) == (24 + 5, 83)


def test_the_stored_edhtop16_numerator_stays_null_the_reader_derives_it() -> None:
    store = _store()
    stored = store.connection.execute(
        "SELECT numerator, denominator FROM card_signal WHERE signal = ? AND card_name = ?",
        (signals.SIGNAL_EDHTOP16, "Card 00"),
    ).fetchone()
    assert (stored["numerator"], stored["denominator"]) == (None, 48)
    claims = strength_view._claim_index(store, [])
    assert claims == {}
    from commander_lab.studio import builder

    pool = builder.pool_cards(store, [CMD], with_signals=False)["cards"]
    assert isinstance(pool, list)
    ids = [str(card["card_id"]) for card in pool]
    display = {str(card["card_id"]): str(card["name"]) for card in pool}
    claims = strength_view._claim_index(store, ids)
    observed, exists = strength_view._signal_observations(
        store, CMD, signals.SIGNAL_EDHTOP16, claims, display, {}
    )
    assert exists
    by_name = {display[card_id]: item for card_id, item in observed.items()}
    assert (by_name["Card 00"].numerator, by_name["Card 00"].denominator) == (45, 48)
    assert by_name["Card 00"].value == pytest.approx(0.9375)
    # only the rate-only EDHTop16 signal is derived: the Playgroup gap keeps its NULL numerator
    add_signal(store, "", "playgroup_observed_winrate_gap", "Card 00", None, 300, value=1.5)
    observed, _ = strength_view._signal_observations(
        store, CMD, "playgroup_observed_winrate_gap", claims, display, {}
    )
    card_id = next(card for card, name in display.items() if name == "Card 00")
    assert observed[card_id].numerator is None


def test_edhrec_theme_reach_is_the_maximum_over_real_themes_with_enough_decks() -> None:
    cards = _cards(_compute(_store(), separate_lands=False))
    reach = _row(cards["Card 01"], "edhrec_theme_reach")
    # ramp 10 of 100, blink 40 of 80; "tiny" (5 decks) is below the minimum of 30 decks
    assert (reach["numerator"], reach["denominator"]) == (40, 80)
    assert "blink" in reach["note"] and "Maximum" in reach["note"]
    assert reach["data_class"] == "DERIVED_DESCRIPTIVE"
    # the commander page and the bracket page are no themes: Card 02 has only blink 3 of 90
    other = _row(cards["Card 02"], "edhrec_theme_reach")
    assert (other["numerator"], other["denominator"]) == (3, 90)
    # a card no theme lists is a missing observation
    assert _row(cards["Card 04"], "edhrec_theme_reach")["reason"] == "NOT_LISTED"


def test_the_result_names_the_corpus_the_cohorts_and_the_denominators() -> None:
    result = _compute(_store())
    corpus = result["corpus"]
    assert corpus["available"] is True
    assert corpus["decks"] == 80
    assert corpus["min_universe"] == 30
    groups = {item["key"]: item for item in corpus["cohorts"]}
    assert groups["tuned"]["cohorts"] == ["bracket:4", "bracket:5"]
    assert groups["tuned"]["denominator"] == 60
    assert groups["low"]["cohorts"] == ["bracket:2"]
    assert groups["low"]["denominator"] == 20
    assert groups["tournament"]["denominator"] == 35
    for name in (
        "corpus_tuned",
        "corpus_log_lift",
        "corpus_bracket_slope",
        "tournament",
        "edhrec_theme_reach",
    ):
        assert name in result["collected"]


# ---------- E2.a: the explicit rule ----------


def test_with_a_corpus_the_edhrec_weights_are_zero_and_the_result_says_why() -> None:
    result = _compute(_store())
    rule = result["weight_rule"]
    assert rule["rule"] == "CORPUS_ZERO"
    assert rule["corpus_available"] is True and rule["corpus_decks"] == 80
    assert rule["effective"] == {"commander_inclusion": 0.0, "bracket_inclusion": 0.0}
    assert rule["requested"] == {"commander_inclusion": 3.0, "bracket_inclusion": 2.0}
    assert result["effective_weights"]["commander_inclusion"] == 0.0
    # the requested settings are shown as requested
    assert result["settings"]["weights"]["commander_inclusion"] == 3.0  # type: ignore[index]
    card = _cards(result)["Card 00"]
    assert _row(card, "commander_inclusion")["weight"] == 0.0
    assert _row(card, "commander_inclusion")["status"] == "PRESENT"  # still shown, not counted


def test_without_a_corpus_the_edhrec_weights_are_the_fallback() -> None:
    result = _compute(_store(corpus=False))
    rule = result["weight_rule"]
    assert rule["rule"] == "EDHREC_FALLBACK"
    assert rule["corpus_available"] is False and rule["corpus_decks"] == 0
    assert rule["effective"] == {"commander_inclusion": 3.0, "bracket_inclusion": 2.0}
    assert result["effective_weights"]["commander_inclusion"] == 3.0
    assert result["corpus"]["available"] is False
    card = _cards(result)["Card 00"]
    assert _row(card, "commander_inclusion")["weight"] == 3.0
    # no corpus: the corpus components are NOT_COLLECTED, without any coverage penalty
    for name in ("corpus_tuned", "corpus_log_lift", "corpus_bracket_slope"):
        assert _row(card, name)["status"] == "NOT_COLLECTED"
    assert "corpus_tuned" not in result["collected"]
    # coverage: commander inclusion 3 of the weights the sources can exist for here:
    # 3 + 2 + 4 + 1 + 0.5 (global) + tournament / theme reach (EDHTop16 and the themes exist)
    assert card["coverage"] is not None and card["coverage"] > 0.25


def test_the_setting_keeps_the_edhrec_weights_with_a_corpus() -> None:
    result = _compute(_store(), edhrec_with_corpus=True)
    assert result["weight_rule"]["rule"] == "EDHREC_KEPT"
    assert _row(_cards(result)["Card 00"], "commander_inclusion")["weight"] == 3.0


def test_a_small_corpus_below_the_minimum_is_no_corpus() -> None:
    store = make_store()
    add_card(store, CMD, type_line="Legendary Creature — Test")
    for name in NAMES:
        add_card(store, name)
    for index in range(10):
        add_deck(store, f"s{index}", ["Card 00"], cohorts=["bracket:4"])
    for index, name in enumerate(NAMES[:6]):
        add_signal(store, CMD, INCLUSION, name, 900 - 100 * index, 1000)
    result = _compute(store)
    assert result["weight_rule"]["rule"] == "EDHREC_FALLBACK"
    assert result["weight_rule"]["corpus_decks"] == 10
    assert result["corpus"]["available"] is False


# ---------- E4: zero counts through the whole path ----------


def test_a_card_with_only_zero_counts_and_global_inclusion_is_d_not_u() -> None:
    cards = _cards(_compute(_store()))
    zero = cards["Card 07"]  # in no deck, no theme, no EDHREC row; only the global inclusion
    # a real tier, not U (the 80-deck synthetic corpus is shrunk, so C or D; the 2,823-deck case
    # is D, see test_studio_strength_v3.py)
    assert zero["tier"] in strength.TIERS
    assert zero["reason"] == "ENOUGH_DATA"
    assert _row(zero, "deck_universe")["status"] == "ZERO_COUNT"
    assert _row(zero, "corpus_tuned")["status"] == "ZERO_COUNT"
    assert _row(zero, "commander_inclusion")["reason"] == "NOT_LISTED"
    assert _row(zero, "commander_inclusion")["status"] == "NO_VALUE"  # never filled with 0


def test_zero_count_tier_u_gives_the_same_card_too_little_data() -> None:
    cards = _cards(_compute(_store(), zero_count_tier="U"))
    zero = cards["Card 07"]
    assert zero["tier"] == "U"
    assert zero["reason"] == "ZERO_COUNT_ONLY"
    assert cards["Card 00"]["tier"] != "U"


# ---------- empirical Bayes and the log scale in the result ----------


def test_the_result_reports_the_empirical_bayes_priors() -> None:
    result = _compute(_store())
    shrinkage = result["shrinkage"]
    # corpus tuned (60 decks) and the tournament pool (35 / 83) have denominators below 500
    assert "corpus_tuned" in shrinkage and "tournament" in shrinkage
    prior = shrinkage["corpus_tuned"]
    assert 0.0 < prior["prior_mean"] < 1.0  # type: ignore[operator]
    assert strength.EB_STRENGTH_MIN <= prior["prior_strength"] <= strength.EB_STRENGTH_MAX  # type: ignore[operator,index]
    row = _row(_cards(result)["Card 04"], "corpus_tuned")
    assert row["shrunk"] is not None and row["shrunk"] > 0.0  # 0 of 60 stays above 0
    assert row["wilson"] is None
    assert row["prior_mean"] == pytest.approx(prior["prior_mean"], abs=1e-5)  # type: ignore[index]


def test_the_default_share_scale_is_the_log_scale_in_the_result() -> None:
    result = _compute(_store(), separate_lands=False)
    assert result["settings"]["share_scale"] == "log"
    rows = {card["name"]: _row(card, "corpus_tuned") for card in result["cards"]}
    shrunk = {
        name: row["shrunk"]
        for name, row in rows.items()
        if row["shrunk"] is not None and row["percentile"] is not None
    }
    assert len(shrunk) >= 5
    top = max(shrunk.values())
    for name, value in shrunk.items():
        assert rows[name]["percentile"] == pytest.approx(
            math.log1p(strength.LOG_SHARE_K * value) / math.log1p(strength.LOG_SHARE_K * top)
        )


def test_the_highest_theme_is_taken_after_each_theme_is_shrunk() -> None:
    store = _store()
    # many small themes at a low share give the pool prior; Card 03 sits in a small theme at a
    # high raw share (12 of 30) and in a large one at a slightly lower share (228 of 600)
    for index in range(6):
        _theme(store, f"edhrec:cmd-a/filler{index}", {f"Card {n:02d}": (3, 40) for n in (4, 5, 6)})
    _theme(store, "edhrec:cmd-a/small", {"Card 03": (12, 30)})
    _theme(store, "edhrec:cmd-a/large", {"Card 03": (228, 600)})
    assert 12 / 30 > 228 / 600  # the raw maximum would be the small theme
    result = _compute(store, separate_lands=False)
    row = _row(_cards(result)["Card 03"], "edhrec_theme_reach")
    assert (row["numerator"], row["denominator"]) == (228, 600)
    assert "large" in row["note"] and "Schrumpfung" in row["note"]
    assert row["prior_mean"] is not None  # the prior of the theme rows is reported
    assert "edhrec_theme_reach" in result["shrinkage"]


def _saved(store: StudioStore, name: str, **weights: float) -> StrengthSettings:
    settings = StrengthSettings(weights=strength.DEFAULT_WEIGHTS | weights)
    strength_view.save_profile(store, name, settings)
    return strength_view.resolve_settings(store, preset=None, profile=name, settings=None)


def test_a_loaded_profile_with_a_rubric_weight_says_the_subjective_signal_is_active() -> None:
    store = _store()
    loaded = _saved(store, "mit Raster", rubric=2.0)
    result = strength_view.compute(
        store,
        CMD,
        loaded,
        dangling_universe_ok=True,
        saved_weights=strength_view.profile_saved_weights(store, "mit Raster"),
    )
    assert any("subjektives Signal aktiv" in note for note in result["notices"])
    plain = strength_view.compute(store, CMD, StrengthSettings())
    assert not any("subjektives Signal" in note for note in plain["notices"])


def test_the_corpus_rule_names_the_saved_edhrec_weights_it_zeroes() -> None:
    store = _store()
    loaded = _saved(store, "alt")
    saved = strength_view.profile_saved_weights(store, "alt")
    assert saved["commander_inclusion"] == 3.0
    result = strength_view.compute(
        store, CMD, loaded, dangling_universe_ok=True, saved_weights=saved
    )
    note = next(n for n in result["notices"] if "Gespeicherte EDHREC-Gewichte" in n)
    assert "gespeichert 3" in note and "wirksam 0" in note and "CORPUS_ZERO" in note
    # no notice when the profile keeps the EDHREC weights (the setting is on) or has none saved
    kept = strength_view.compute(
        store, CMD, StrengthSettings(edhrec_with_corpus=True), saved_weights=saved
    )
    assert not any("Gespeicherte EDHREC" in n for n in kept["notices"])
    none_saved = strength_view.compute(store, CMD, loaded, dangling_universe_ok=True)
    assert not any("Gespeicherte EDHREC" in n for n in none_saved["notices"])


# ---------- D2 to D6 additions (#1369): the figures stay, new fields are added ----------

# The index and the tier of every card of this fixture, frozen from ``origin/main`` before the
# additions (default settings, and with ``zero_count_tier = U``). They must stay bit-identical.
FROZEN_REFERENCE = {
    "Card 00": (80.5, "S"),
    "Card 01": (71.9, "S"),
    "Card 02": (38.6, "A"),
    "Card 03": (23.1, "B"),
    "Card 04": (19.8, "C"),
    "Card 05": (42.8, "A"),
    "Card 06": (44.4, "A"),
    "Card 07": (18.3, "C"),
    "Cmd A": (None, "N"),
    "Land A": (69.8, "S"),
}
FROZEN_REFERENCE_ZERO_U = {**FROZEN_REFERENCE, "Card 04": (19.8, "U"), "Card 07": (18.3, "U")}


def test_index_and_tiers_stay_identical_to_the_frozen_reference() -> None:
    assert FROZEN_REFERENCE
    for kwargs, expected, counts in (
        ({}, FROZEN_REFERENCE, {"S": 3, "A": 3, "B": 1, "C": 2, "D": 0, "U": 0, "N": 1}),
        (
            {"zero_count_tier": "U"},
            FROZEN_REFERENCE_ZERO_U,
            {"S": 3, "A": 3, "B": 1, "C": 0, "D": 0, "U": 2, "N": 1},
        ),
    ):
        result = _compute(_store(), **kwargs)
        assert {card["name"]: (card["index"], card["tier"]) for card in result["cards"]} == expected
        assert result["tier_counts"] == counts
        for card in result["cards"]:
            if card["tier"] in ("U", "N"):  # only ranked cards get stability and a relative tier
                assert card["tier_stability"] is None and card["relative_tier"] is None
                assert card["relative_rank"] is None and card["unscharf"] is False
        spells = result["relative_tier_info"]["totals"]["spells"]
        assert spells == sum(
            1 for card in result["cards"] if card["tier"] in strength.TIERS and not card["is_land"]
        )


def test_the_tournament_row_shows_its_two_cohorts_with_their_own_n_of_n() -> None:
    cards = _cards(_compute(_store()))
    both = _row(cards["Card 00"], "tournament")
    parts = {part["key"]: part for part in both["parts"]}
    assert set(parts) == {"edhtop16", "corpus_bracket5"}
    assert (parts["edhtop16"]["numerator"], parts["edhtop16"]["denominator"]) == (45, 48)
    assert (parts["corpus_bracket5"]["numerator"], parts["corpus_bracket5"]["denominator"]) == (
        35,
        35,
    )
    assert both["mixed_cohorts_note"] == "zwei Kohorten addiert (E3.a)"
    assert _parts_add_up(cards) >= 5
    only_corpus = _row(cards["Card 05"], "tournament")
    assert [part["key"] for part in only_corpus["parts"]] == ["corpus_bracket5"]
    assert only_corpus["mixed_cohorts_note"] is None  # one cohort: nothing was added
    assert _row(cards["Card 00"], "deck_universe")["parts"] == []
    assert _row(cards["Card 00"], "deck_universe")["mixed_cohorts_note"] is None


def _parts_add_up(cards: dict[str, strength_view.StrengthCard]) -> int:
    """Where parts are listed, their n / N add up to the pooled n / N of the row."""
    checked = 0
    for card in cards.values():
        for row in card["components"]:
            if row["parts"]:
                assert sum(part["numerator"] for part in row["parts"]) == row["numerator"]
                assert sum(part["denominator"] for part in row["parts"]) == row["denominator"]
                checked += 1
    return checked


def test_the_payload_carries_stability_relative_tiers_and_weight_families() -> None:
    result = _compute(_store())
    cards = _cards(result)
    info = result["stability"]
    assert info["variants"] == info["single_weight_variants"] + info["random_variants"] >= 30
    ranked = [card for card in result["cards"] if card["tier"] in strength.TIERS]
    assert len(ranked) == 9
    for card in ranked:
        assert card["tier_stability"] == pytest.approx(
            (card["tier_stability_kept"] or 0) / (card["tier_stability_variants"] or 1), abs=1e-4
        )
        assert card["tier_stability_variants"] == info["variants"]
        assert card["unscharf"] == (card["tier_stability"] < strength.STABILITY_UNSHARP_BELOW)
        # both groups of this fixture hold fewer than 10 ranked cards: a rank, but no tier
        assert card["relative_tier"] is None
        assert card["relative_rank"] is not None
        assert card["confidence_basis"] in ("gezaehlte_null", "zaehler")
        assert card["tier_stability"] is not None
        if card["tier_stability"] == 1.0:
            assert card["tier_alternatives"] == []
        else:
            assert sum(item["variants"] for item in card["tier_alternatives"]) == (
                info["variants"] - (card["tier_stability_kept"] or 0)
            )
    unranked = cards[CMD]
    assert unranked["tier"] == "N"
    assert unranked["tier_stability"] is None and unranked["unscharf"] is False
    assert unranked["relative_tier"] is None and unranked["relative_rank"] is None
    assert unranked["tier_alternatives"] == []
    assert result["relative_tier_info"]["note"] == "relativ im Pool, keine Aussage über Spielstärke"
    assert result["relative_tier_info"]["totals"] == {"spells": 8, "lands": 1}
    assert result["relative_tier_info"]["min_group"] == 10
    assert result["relative_tier_info"]["f_note"].startswith("F = die untersten 10 %")
    assert sum(sum(c.values()) for c in result["relative_tier_info"]["counts"].values()) == 0
    # a land is ranked with the lands only: the only land is rank 1 of 1, the best spell 1 of 8
    assert cards[LAND]["relative_rank"] == {"rank": 1, "total": 1, "group": "lands"}
    assert cards["Card 00"]["relative_rank"] == {"rank": 1, "total": 8, "group": "spells"}
    shares = {item["family"]: item["share_of_total"] for item in result["weight_families"]}
    assert shares["source_decks"] == pytest.approx(0.75)  # 7.5 of 10 once E2.a zeroes EDHREC
    assert sum(shares.values()) == pytest.approx(1.0)
    assert cards["Card 00"]["confidence_by_denominator_level"] is not None
    assert cards["Card 00"]["zero_count_thin"] == []
