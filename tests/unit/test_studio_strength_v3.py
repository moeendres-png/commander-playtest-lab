"""Tierliste v3, packages 1 and 2 (#1364): the purely empirical strength index, pure part.

Synthetic data only: defaults and presets, the log share scale, empirical Bayes shrinkage, the
derived corpus values (lift, slope), the E2.a weight rule, the E4 zero-count tier and the
saved-profile reload. The store side is tested in ``test_studio_strength_v3_view.py``.
"""

from __future__ import annotations

import math

import pytest

from commander_lab.studio import strength
from commander_lab.studio.strength import Observation, PoolContext, StrengthSettings

PRESET_WEIGHTS = {
    "Ausgewogen": {
        "deck_universe": 4.0,
        "corpus_tuned": 1.5,
        "corpus_log_lift": 1.0,
        "corpus_bracket_slope": 1.0,
        "global_inclusion": 1.0,
        "tournament": 0.5,
        "edhrec_theme_reach": 0.5,
        "combos": 0.5,
    },
    "Commander-nah": {
        "deck_universe": 4.5,
        "corpus_tuned": 1.0,
        "corpus_log_lift": 2.0,
        "corpus_bracket_slope": 0.5,
        "global_inclusion": 0.5,
        "tournament": 0.0,
        "edhrec_theme_reach": 1.0,
        "combos": 0.5,
    },
    "Turniernah": {
        "deck_universe": 2.5,
        "corpus_tuned": 2.5,
        "corpus_log_lift": 0.5,
        "corpus_bracket_slope": 2.0,
        "global_inclusion": 0.5,
        "tournament": 2.0,
        "edhrec_theme_reach": 0.0,
        "combos": 1.0,
    },
}


# ---------- E1.a, E3.a, E4.b, E5.a: defaults and presets ----------


@pytest.mark.parametrize("name", sorted(PRESET_WEIGHTS))
def test_presets_carry_the_owner_weights_and_a_zero_rubric(name: str) -> None:
    weights = strength.PRESETS[name].weights
    for component, value in PRESET_WEIGHTS[name].items():
        assert weights[component] == value, (name, component)
    for component in ("rubric", "simulation", "playgroup_observed", "synergy"):
        assert weights[component] == 0.0, (name, component)
    # the TopDeck components stay as columns, with weight 0
    assert weights["tournament_lists"] == 0.0
    assert weights["tournament_conversion"] == 0.0


def test_default_weights_are_the_ausgewogen_preset_and_the_rubric_is_zero() -> None:
    assert strength.DEFAULT_WEIGHTS["rubric"] == 0.0
    assert StrengthSettings().weights == strength.PRESETS["Ausgewogen"].weights
    # the component, its label and its data class stay: it is subjective, not an objective signal
    assert strength.RUBRIC in strength.COMPONENTS
    assert "subjektiv" in strength.LABELS[strength.RUBRIC]
    assert "Gewicht 0" in strength.LABELS[strength.RUBRIC]
    assert strength.COMPONENT_DATA_CLASS[strength.RUBRIC] == "SUBJECTIVE_RATING"


def test_the_new_defaults_of_the_empirical_index() -> None:
    settings = StrengthSettings()
    assert settings.share_scale == "log"
    assert settings.separate_lands is True
    assert settings.rank_group == "pool"
    assert settings.tier_cuts == {"S": 54.0, "A": 35.0, "B": 20.0, "C": 5.0}
    assert settings.zero_count_tier == "D"
    assert settings.edhrec_with_corpus is False
    assert settings.rank_other_commanders is True
    # nothing is filled with 0 for a card a source does not list (E4.b)
    assert settings.missing_value == {
        "commander_inclusion": "skip",
        "bracket_inclusion": "skip",
        "deck_universe": "skip",
    }


def test_every_new_component_is_derived_descriptive_and_commander_only() -> None:
    new = (
        strength.CORPUS_TUNED,
        strength.CORPUS_LOG_LIFT,
        strength.CORPUS_BRACKET_SLOPE,
        strength.TOURNAMENT,
        strength.EDHREC_THEME_REACH,
    )
    assert len(new) == 5
    for component in new:
        assert strength.COMPONENT_DATA_CLASS[component] == "DERIVED_DESCRIPTIVE"
        # a commander without the source gets NOT_COLLECTED and no coverage penalty
        assert component in strength.COMMANDER_ONLY_SOURCES
        assert strength.is_commander_specific(component)
        assert strength.signal_for(component, "upgraded")


def test_settings_validate_the_new_keys_and_round_trip() -> None:
    with pytest.raises(ValueError, match="zero_count_tier"):
        StrengthSettings(zero_count_tier="X")
    with pytest.raises(ValueError, match="share_scale"):
        StrengthSettings(share_scale="exp")
    with pytest.raises(ValueError, match="edhrec_with_corpus"):
        StrengthSettings.from_dict({"edhrec_with_corpus": "yes"})
    chosen = StrengthSettings(zero_count_tier="U", edhrec_with_corpus=True, share_scale="share")
    assert StrengthSettings.from_dict(chosen.to_dict()) == chosen


def test_a_profile_saved_before_v3_keeps_its_values_and_takes_new_defaults_for_new_keys() -> None:
    """What changes on reload: every stored value stays (the rubric weight, the sqrt scale, the
    cuts); keys the profile lacks (the new components, ``zero_count_tier``,
    ``edhrec_with_corpus``) take the new defaults, so the E2.a rule applies to the old profile."""
    old = {
        "weights": {"commander_inclusion": 3.0, "deck_universe": 2.0, "rubric": 3.5},
        "share_scale": "share",
        "tier_cuts": {"S": 47.0, "A": 17.0, "B": 9.0, "C": 4.0},
        "missing_value": {"commander_inclusion": "lowest", "bracket_inclusion": "lowest"},
    }
    settings, ignored = StrengthSettings.from_stored(old)
    assert ignored == []
    assert settings.weights["rubric"] == 3.5
    assert settings.weights["deck_universe"] == 2.0
    assert settings.share_scale == "share"
    assert settings.tier_cuts["S"] == 47.0
    assert settings.missing_value["commander_inclusion"] == "lowest"
    assert settings.weights["corpus_tuned"] == strength.DEFAULT_WEIGHTS["corpus_tuned"]
    assert settings.zero_count_tier == "D"
    assert settings.edhrec_with_corpus is False


# ---------- Q1-b0 (#1675): retired settings keys are accepted and dropped ----------

# Probe keys for the filter sites; the real retired keys enter the list with the packages that
# remove them (Q1-b2: ``layer_weights``, ``pod_size``; Q1-b4 next). One probe per group, so a
# mutation at one filter site fails one case.
RETIRED_PROBES = {
    strength.RETIRED_WEIGHTS: "retired_component_probe",
    strength.RETIRED_MIN_DENOMINATORS: "retired_minimum_probe",
    strength.RETIRED_TOP_LEVEL: "retired_setting_probe",
}


def _retire_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        strength,
        "RETIRED_SETTING_KEYS",
        {group: frozenset({key}) for group, key in RETIRED_PROBES.items()},
    )


def _with_key(base: dict[str, object], group: str, key: str, value: object) -> dict[str, object]:
    """``base`` with ``key`` added at the level of ``group``."""
    if group == strength.RETIRED_TOP_LEVEL:
        return {**base, key: value}
    nested = base.get(group, {})
    assert isinstance(nested, dict)
    return {**base, group: {**nested, key: value}}


SAVED = {
    "weights": {"deck_universe": 2.0, "combos": 1.0},
    "min_denominators": {"edhrec": 40},
    "bracket": "optimized",
}


def test_the_retired_list_names_what_fell_and_never_names_a_live_key() -> None:
    """A key moves to the list only in the change that removes it: Q1-b2 (#1677) retired the
    top-level ``layer_weights`` and ``pod_size``; nothing else is retired yet."""
    assert set(strength.RETIRED_SETTING_KEYS) == set(RETIRED_PROBES)
    assert {
        strength.RETIRED_WEIGHTS: frozenset(),
        strength.RETIRED_MIN_DENOMINATORS: frozenset(),
        strength.RETIRED_TOP_LEVEL: frozenset({"layer_weights", "pod_size"}),
    } == strength.RETIRED_SETTING_KEYS
    live = {
        strength.RETIRED_WEIGHTS: set(strength.DEFAULT_WEIGHTS),
        strength.RETIRED_MIN_DENOMINATORS: set(strength.MIN_DENOMINATOR_KEYS),
        strength.RETIRED_TOP_LEVEL: set(StrengthSettings().to_dict()),
    }
    for group, keys in strength.RETIRED_SETTING_KEYS.items():
        assert not keys & live[group]


@pytest.mark.parametrize("group", list(RETIRED_PROBES))
def test_a_profile_with_a_retired_key_loads_with_the_settings_it_has_without_it(
    monkeypatch: pytest.MonkeyPatch, group: str
) -> None:
    _retire_probes(monkeypatch)
    old = _with_key(SAVED, group, RETIRED_PROBES[group], 3)
    expected, _ = StrengthSettings.from_stored(SAVED)
    settings, ignored = StrengthSettings.from_stored(old)
    assert settings == expected
    assert ignored == []  # dropped, not reported as unknown
    assert RETIRED_PROBES[group] not in settings.to_dict()
    assert RETIRED_PROBES[group] not in settings.weights
    assert RETIRED_PROBES[group] not in settings.min_denominators
    # the strict reader (explicit settings, remembered browser settings) accepts it too
    assert StrengthSettings.from_dict(old) == expected


@pytest.mark.parametrize("group", list(RETIRED_PROBES))
def test_an_unknown_key_that_is_not_retired_still_fails(
    monkeypatch: pytest.MonkeyPatch, group: str
) -> None:
    """A typo stays visible: only listed keys are dropped."""
    _retire_probes(monkeypatch)
    typo = _with_key(SAVED, group, "deck_univers", 3)
    with pytest.raises(ValueError, match="deck_univers"):
        StrengthSettings.from_dict(typo)
    if group == strength.RETIRED_TOP_LEVEL:
        # a stored profile ignores and NAMES an unknown top-level key (another version wrote it)
        assert StrengthSettings.from_stored(typo)[1] == ["deck_univers"]
    else:
        with pytest.raises(ValueError, match="deck_univers"):
            StrengthSettings.from_stored(typo)


def test_a_retired_key_is_only_dropped_where_it_is_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A weight probe is not a setting and the other way round: the groups do not mix."""
    _retire_probes(monkeypatch)
    weight_probe = RETIRED_PROBES[strength.RETIRED_WEIGHTS]
    with pytest.raises(ValueError, match=weight_probe):
        StrengthSettings.from_dict({weight_probe: 1})
    with pytest.raises(ValueError, match=weight_probe):
        StrengthSettings.from_dict({"min_denominators": {weight_probe: 1}})
    # constructing settings in code stays strict: the list is for reading only
    with pytest.raises(ValueError, match="unknown component"):
        StrengthSettings(weights={weight_probe: 1.0})


@pytest.mark.parametrize(
    ("raw", "deviating"),
    [
        ({}, []),
        ({"layer_weights": {}, "pod_size": 4}, []),
        ({"layer_weights": {"tempo": 0, "staying": 0.0}, "pod_size": 4.0}, []),
        ({"layer_weights": {"tempo": 0.5}}, ["layer_weights"]),
        ({"pod_size": 3}, ["pod_size"]),
        ({"pod_size": True}, ["pod_size"]),
        ({"layer_weights": {"tempo": False}}, ["layer_weights"]),  # false is not the weight 0
        ({"layer_weights": "x"}, ["layer_weights"]),
        ({"layer_weights": {"tempo": 1}, "pod_size": 6}, ["layer_weights", "pod_size"]),
    ],
)
def test_retired_deviations_name_a_dropped_value_only_when_it_was_not_the_default(
    raw: dict[str, object], deviating: list[str]
) -> None:
    """Defaults when the keys fell: every layer weight 0, pod size 4 (Q1-b2)."""
    assert strength.retired_deviations(raw) == deviating


def test_rank_group_function_stays_a_valid_value() -> None:
    """E2: "Gleiche Funktion" stays; the retired list does not touch values."""
    assert StrengthSettings.from_dict({"rank_group": "function"}).rank_group == "function"
    settings, ignored = StrengthSettings.from_stored({"rank_group": "function"})
    assert settings.rank_group == strength.GROUP_FUNCTION == "function"
    assert ignored == []


# ---------- E5.a: the log share scale ----------


def test_log_scale_is_ln_one_plus_k_v_over_ln_one_plus_k_vmax_with_k_150() -> None:
    assert strength.LOG_SHARE_K == 150.0
    values = {"a": 0.6, "b": 0.1, "c": 0.01, "d": 0.001, "e": 0.0}
    scores = strength.share_scale_values(values, "log")
    top = math.log(1 + 150 * 0.6)
    for card, value in values.items():
        assert scores[card] == pytest.approx(math.log(1 + 150 * value) / top)
    assert scores["a"] == pytest.approx(1.0)
    assert scores["e"] == 0.0
    assert scores["a"] > scores["b"] > scores["c"] > scores["d"] > scores["e"]
    assert strength.StrengthSettings().share_scale == "log"


def test_log_scale_edge_cases_follow_the_share_scale() -> None:
    assert strength.share_scale_values({}, "log") == {}
    assert strength.share_scale_values({"x": 0.3}, "log") == {"x": 0.5}
    assert strength.share_scale_values({"x": 0.0}, "log") == {"x": 0.0}
    assert strength.share_scale_values({"x": 0.0, "y": 0.0}, "log") == {"x": 0.0, "y": 0.0}


def test_log_scale_k_is_a_parameter_for_the_sensitivity_check_only() -> None:
    values = {"a": 0.6, "b": 0.01}
    default = strength.share_scale_values(values, "log")
    explicit = strength.log_share_scores(values, 0.6, k=150.0)
    assert explicit == default
    flatter = strength.log_share_scores(values, 0.6, k=100.0)
    sharper = strength.log_share_scores(values, 0.6, k=200.0)
    # a larger k lifts the small shares towards the top
    assert flatter["b"] < default["b"] < sharper["b"]


# ---------- empirical Bayes ----------


def test_beta_binomial_prior_needs_enough_cards_and_clamps_the_strength() -> None:
    assert strength.beta_binomial_prior([(1, 48)] * 4) is None  # fewer than EB_MIN_CARDS
    counts = [(0, 48), (3, 48), (10, 48), (24, 48), (1, 48), (5, 48), (2, 48), (40, 48)]
    prior = strength.beta_binomial_prior(counts)
    assert prior is not None
    assert prior.mean == pytest.approx(sum(k for k, _ in counts) / (48 * len(counts)))
    assert strength.EB_STRENGTH_MIN <= prior.strength <= strength.EB_STRENGTH_MAX
    assert prior.cards == len(counts)
    # shares that all equal the pooled mean carry no excess variance: the strength is the maximum
    flat = strength.beta_binomial_prior([(5, 50)] * 6)
    assert flat is not None
    assert flat.strength == strength.EB_STRENGTH_MAX
    assert flat.clamped is True
    # a degenerate mean (no deck anywhere) is a maximum-strength prior at 0, never a crash
    none = strength.beta_binomial_prior([(0, 50)] * 6)
    assert none is not None
    assert (none.mean, none.strength) == (0.0, strength.EB_STRENGTH_MAX)


def test_beta_binomial_prior_recovers_a_known_overdispersion() -> None:
    """A true Beta(2, 8) prior (mean 0.2, strength 10) with n = 100 per card: the estimate
    lands near 10 (method of moments, large sample of cards)."""
    import random

    rng = random.Random(7)
    counts = []
    for _ in range(4000):
        p = rng.betavariate(2, 8)
        counts.append((sum(rng.random() < p for _ in range(100)), 100))
    prior = strength.beta_binomial_prior(counts)
    assert prior is not None
    assert prior.mean == pytest.approx(0.2, abs=0.01)
    assert prior.strength == pytest.approx(10.0, rel=0.25)


def test_shrinkage_keeps_zero_of_48_above_zero_and_the_order_of_equal_n() -> None:
    prior = strength.SharePrior(mean=0.2, strength=20.0, cards=10, clamped=False)
    zero = strength.shrunk_share(0, 48, prior)
    assert zero > 0.0
    assert zero == pytest.approx(0.2 * 20 / 68)
    ordered = [strength.shrunk_share(k, 48, prior) for k in range(0, 49)]
    assert ordered == sorted(ordered)
    assert len(set(ordered)) == 49
    # the smaller the sample the stronger the pull to the prior
    assert strength.shrunk_share(0, 10, prior) > strength.shrunk_share(0, 400, prior)
    assert strength.shrunk_share(10, 10, prior) < strength.shrunk_share(400, 400, prior)


def _share_pool(denominator: int, hits: list[int]) -> dict[str, dict[str, Observation]]:
    return {
        f"card{index:02d}": {
            "tournament": Observation(hit / denominator, hit, denominator),
        }
        for index, hit in enumerate(hits)
    }


def _score_one(
    observations: dict[str, dict[str, Observation]],
    *,
    measure: str = "wilson",
    diagnostics: dict[str, object] | None = None,
) -> dict[str, strength.CardStrength]:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"tournament": 1.0},
        share_measure=measure,
        min_coverage=0.0,
        min_components=1,
        require_commander_signal=False,
        min_denominators={"tournament": 0},
    )
    return strength.score_pool(
        settings,
        observations,
        {strength.TOURNAMENT},
        context=PoolContext(),
        diagnostics=diagnostics,
    )


def _row(card: strength.CardStrength, component: str) -> strength.ComponentResult:
    return next(row for row in card["components"] if row["component"] == component)


def test_a_small_denominator_is_shrunk_and_the_prior_is_reported() -> None:
    hits = [0, 0, 0, 1, 2, 3, 5, 8, 13, 21, 30]
    diagnostics: dict[str, object] = {}
    scored = _score_one(_share_pool(48, hits), diagnostics=diagnostics)
    zero = _row(scored["card00"], "tournament")
    assert zero["status"] == "ZERO_COUNT"
    assert zero["shrunk"] is not None
    assert zero["shrunk"] > 0.0  # 0 of 48 is not exactly 0 after shrinkage
    assert zero["wilson"] is None  # the Wilson bound is not what was ranked
    assert zero["prior_mean"] is not None and zero["prior_strength"] is not None
    assert zero["percentile"] is not None
    shrinkage = diagnostics["shrinkage"]
    assert isinstance(shrinkage, dict)
    assert shrinkage["tournament"]["cards"] == len(hits)
    assert shrinkage["tournament"]["prior_mean"] == pytest.approx(
        sum(hits) / (48 * len(hits)), abs=1e-5
    )
    assert shrinkage["tournament"]["max_denominator"] == 500
    # the order of cards with the same denominator is exactly the raw order
    indexes = [scored[f"card{index:02d}"]["index"] or 0.0 for index in range(len(hits))]
    assert indexes == sorted(indexes)
    assert scored["card03"]["index"] < scored["card04"]["index"] < scored["card10"]["index"]


def test_a_large_denominator_keeps_the_wilson_path() -> None:
    hits = [0, 5, 20, 100, 400, 900, 1500, 2000]
    diagnostics: dict[str, object] = {}
    scored = _score_one(_share_pool(2823, hits), diagnostics=diagnostics)
    row = _row(scored["card03"], "tournament")
    assert row["shrunk"] is None
    assert row["wilson"] == pytest.approx(strength.wilson_lower(100, 2823))
    assert diagnostics["shrinkage"] == {}


def test_a_denominator_at_the_limit_is_not_shrunk_one_below_is() -> None:
    hits = [0, 1, 2, 4, 7, 11, 16, 25]
    at_limit = _score_one(_share_pool(strength.EB_MAX_DENOMINATOR, hits))
    below = _score_one(_share_pool(strength.EB_MAX_DENOMINATOR - 1, hits))
    assert _row(at_limit["card03"], "tournament")["shrunk"] is None
    assert _row(below["card03"], "tournament")["shrunk"] is not None


def test_raw_share_measure_is_never_shrunk() -> None:
    scored = _score_one(_share_pool(48, [0, 1, 2, 4, 7, 11, 16, 25]), measure="raw")
    row = _row(scored["card00"], "tournament")
    assert row["shrunk"] is None
    assert row["prior_mean"] is None


def test_too_few_small_cards_fall_back_to_the_wilson_bound() -> None:
    scored = _score_one(_share_pool(48, [0, 3, 9]))
    row = _row(scored["card01"], "tournament")
    assert row["shrunk"] is None
    assert row["wilson"] == pytest.approx(strength.wilson_lower(3, 48))


def test_min_denominator_gate_is_unchanged_by_shrinkage() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"tournament": 1.0},
        min_coverage=0.0,
        min_components=1,
        require_commander_signal=False,
        min_denominators={"tournament": 60},
    )
    observations = _share_pool(48, [0, 1, 2, 4, 7, 11, 16, 25])
    scored = strength.score_pool(settings, observations, {strength.TOURNAMENT})
    row = _row(scored["card03"], "tournament")
    assert row["status"] == "NO_VALUE"
    assert row["reason"] == "BELOW_MIN_DENOMINATOR"
    assert row["shrunk"] is None


# ---------- E3.a: derived corpus values ----------


def test_log_lift_value_definition_and_cap() -> None:
    # 10 of 1000 decks (1 %) against a global share of 0.1 %: lift 10, log10 = 1,
    # damped by 10 / 15, value (0.6667 + 2) / 4
    value = strength.log_lift_value(10, 1000, 0.001)
    assert value == pytest.approx((1 * 10 / 15 + 2) / 4)
    # no difference to the global share: exactly the middle
    assert strength.log_lift_value(50, 1000, 0.05) == pytest.approx(0.5)
    # below the global share: below the middle
    below = strength.log_lift_value(50, 1000, 0.5)
    assert below is not None and below < 0.5
    # damped log ratio capped at +-2 (a factor of 100): the value never leaves 0..1
    assert strength.log_lift_value(500, 1000, 1e-9) == 1.0
    assert strength.log_lift_value(500, 1000, 1e9) == 0.0


def test_log_lift_never_rewards_tiny_counts() -> None:
    """The same lift (100) from one deck and from 200 decks: the damping keeps the single deck
    near the middle, the large count reaches the top."""
    one = strength.log_lift_value(1, 2823, 1 / 2823 / 100)
    many = strength.log_lift_value(200, 2823, 200 / 2823 / 100)
    assert one is not None and many is not None
    assert one < 0.65
    assert many > 0.95
    assert many > one
    # a tiny count with an enormous lift stays below a medium count with a modest lift
    tiny_extreme = strength.log_lift_value(1, 2823, 1e-9)
    medium_modest = strength.log_lift_value(150, 2823, 150 / 2823 / 10)
    assert tiny_extreme is not None and medium_modest is not None
    assert tiny_extreme < medium_modest


def test_log_lift_is_none_without_hits_corpus_or_global_share() -> None:
    assert strength.log_lift_value(0, 2823, 0.01) is None  # lift of a count of 0 is undefined
    assert strength.log_lift_value(5, 0, 0.01) is None
    assert strength.log_lift_value(5, 2823, None) is None
    assert strength.log_lift_value(5, 2823, 0.0) is None
    assert strength.log_lift_value(5, 2823, float("nan")) is None
    assert strength.log_lift_value(3000, 2823, 0.01) is None  # more hits than decks


def test_bracket_slope_needs_five_hits_and_is_symmetric() -> None:
    assert strength.bracket_slope_value(2, 1153, 2, 647) is None  # 4 hits in total
    assert strength.bracket_slope_value(3, 1153, 2, 647) is not None  # 5 hits
    assert strength.bracket_slope_value(5, 0, 5, 647) is None
    up = strength.bracket_slope_value(100, 1153, 10, 647)
    down = strength.bracket_slope_value(10, 1153, 100, 647)
    assert up is not None and down is not None
    assert up > 0.5 > down
    # equal shares in both groups: the middle (hits are damped, the log ratio is ~0)
    flat = strength.bracket_slope_value(115, 1153, 64, 647)
    assert flat is not None and flat == pytest.approx(0.5, abs=0.02)


def test_bracket_slope_is_finite_with_an_empty_group_and_capped() -> None:
    # a card in no bracket-2 deck: the ratio stays finite (half a deck), the value stays in 0..1
    value = strength.bracket_slope_value(40, 1153, 0, 647)
    assert value is not None and 0.5 < value <= 1.0
    extreme = strength.bracket_slope_value(1000, 1153, 0, 10**6)
    assert extreme is not None and extreme <= 1.0
    # more hits at the same ratio move it further from the middle (damping)
    few = strength.bracket_slope_value(4, 1153, 1, 647)
    many = strength.bracket_slope_value(400, 1153, 100, 647)
    assert few is not None and many is not None
    assert abs(many - 0.5) > abs(few - 0.5) or many == few


# ---------- E2.a: the EDHREC weight rule ----------


def test_the_rule_zeroes_edhrec_while_a_counted_corpus_exists() -> None:
    settings = StrengthSettings()
    resolved, rule = strength.apply_corpus_rule(settings, corpus_decks=2823, min_universe=30)
    assert rule["rule"] == "CORPUS_ZERO"
    assert rule["corpus_available"] is True
    assert rule["requested"] == {"commander_inclusion": 3.0, "bracket_inclusion": 2.0}
    assert rule["effective"] == {"commander_inclusion": 0.0, "bracket_inclusion": 0.0}
    assert resolved.weights["commander_inclusion"] == 0.0
    assert resolved.weights["bracket_inclusion"] == 0.0
    # no other weight changes, and the requested settings object is untouched
    for name in strength.COMPONENTS:
        if name not in ("commander_inclusion", "bracket_inclusion"):
            assert resolved.weights[name] == settings.weights[name]
    assert settings.weights["commander_inclusion"] == 3.0
    assert "Korpus" in rule["note"]


def test_the_rule_falls_back_to_the_edhrec_weights_without_a_corpus() -> None:
    settings = StrengthSettings()
    for decks in (0, 29):
        resolved, rule = strength.apply_corpus_rule(settings, corpus_decks=decks, min_universe=30)
        assert rule["rule"] == "EDHREC_FALLBACK"
        assert rule["corpus_available"] is False
        assert resolved is settings
        assert rule["effective"] == {"commander_inclusion": 3.0, "bracket_inclusion": 2.0}
    _, at_minimum = strength.apply_corpus_rule(settings, corpus_decks=30, min_universe=30)
    assert at_minimum["rule"] == "CORPUS_ZERO"


def test_the_setting_keeps_the_edhrec_weights_with_a_corpus() -> None:
    settings = StrengthSettings(edhrec_with_corpus=True)
    resolved, rule = strength.apply_corpus_rule(settings, corpus_decks=2823, min_universe=30)
    assert rule["rule"] == "EDHREC_KEPT"
    assert resolved is settings
    assert rule["effective"] == rule["requested"]


def test_both_paths_change_the_index_of_a_card_with_edhrec_data() -> None:
    """The explicit rule, end to end: the same observations score differently with and without
    a corpus, and only the EDHREC components' weights differ."""
    observations = {
        f"c{index}": {
            "commander_inclusion": Observation(0.9 - 0.1 * index, 90 - 10 * index, 100),
            "deck_universe": Observation(0.1 + 0.1 * index, 10 + 10 * index, 100),
        }
        for index in range(8)
    }
    collected = {strength.COMMANDER_INCLUSION, strength.DECK_UNIVERSE}
    base = StrengthSettings(min_coverage=0.0, min_components=1, require_commander_signal=False)
    with_corpus, _ = strength.apply_corpus_rule(base, corpus_decks=100, min_universe=30)
    without, _ = strength.apply_corpus_rule(base, corpus_decks=5, min_universe=30)
    scored_corpus = strength.score_pool(with_corpus, observations, collected)
    scored_without = strength.score_pool(without, observations, collected)
    # with the corpus only the deck universe counts: the order follows it (rising)
    assert scored_corpus["c7"]["index"] > scored_corpus["c0"]["index"]
    # without it the EDHREC inclusion (falling) carries the index
    assert _row(scored_without["c0"], "commander_inclusion")["weight"] == 3.0
    assert _row(scored_corpus["c0"], "commander_inclusion")["weight"] == 0.0
    assert scored_without["c0"]["index"] != scored_corpus["c0"]["index"]


# ---------- E4: zero counts, not listed, tier D or U ----------


def _zero_pool() -> tuple[dict[str, dict[str, Observation]], set[str]]:
    observations = {
        "zero_plus_global": {
            "deck_universe": Observation(0.0, 0, 2823),
            "global_inclusion": Observation(0.02, 200000, 10000000),
        },
        "positive": {
            "deck_universe": Observation(0.3, 850, 2823),
            "global_inclusion": Observation(0.1, 1000000, 10000000),
        },
        "other": {
            "deck_universe": Observation(0.1, 280, 2823),
            "global_inclusion": Observation(0.05, 500000, 10000000),
        },
        "global_only": {
            "global_inclusion": Observation(0.01, 100000, 10000000),
        },
        "last": {
            "deck_universe": Observation(0.05, 140, 2823),
            "global_inclusion": Observation(0.03, 300000, 10000000),
        },
        "fifth": {
            "deck_universe": Observation(0.02, 56, 2823),
            "global_inclusion": Observation(0.04, 400000, 10000000),
        },
    }
    return observations, {strength.DECK_UNIVERSE, strength.GLOBAL_INCLUSION}


# These tests are about the zero-count rule, not the default cuts: the cuts of Stand #1371 keep a
# card with a counted zero plus global inclusion in tier D in the toy pool (a six card pool has
# no realistic index distribution, so the real-data cuts do not apply to it).
_ZERO_TEST_CUTS = {"S": 72.0, "A": 50.0, "B": 28.0, "C": 14.0}


def _zero_settings(**extra: object) -> StrengthSettings:
    return StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS}
        | {"deck_universe": 4.0, "global_inclusion": 1.0},
        tier_cuts=dict(_ZERO_TEST_CUTS),
        **extra,  # type: ignore[arg-type]
    )


def test_zero_of_n_plus_global_inclusion_is_tier_d_not_u_by_default() -> None:
    observations, collected = _zero_pool()
    scored = strength.score_pool(_zero_settings(), observations, collected)
    card = scored["zero_plus_global"]
    assert card["tier"] == "D"
    assert card["reason"] == "ENOUGH_DATA"
    row = _row(card, "deck_universe")
    assert row["status"] == "ZERO_COUNT"
    assert row["reason"] == "ZERO_COUNT"
    assert row["percentile"] == 0.0
    assert (row["numerator"], row["denominator"]) == (0, 2823)
    assert card["present"] == 2


def test_zero_count_tier_u_gives_e4a_with_a_reason_code() -> None:
    observations, collected = _zero_pool()
    scored = strength.score_pool(_zero_settings(zero_count_tier="U"), observations, collected)
    card = scored["zero_plus_global"]
    assert card["tier"] == "U"
    assert card["reason"] == "ZERO_COUNT_ONLY"
    assert "Nullen" in card["note"]
    # a card with positive commander evidence is unaffected
    assert scored["positive"]["tier"] != "U"
    assert scored["positive"]["reason"] == "ENOUGH_DATA"


def test_not_listed_and_zero_count_are_different_statuses() -> None:
    observations, collected = _zero_pool()
    scored = strength.score_pool(
        _zero_settings(), observations, collected | {strength.COMMANDER_INCLUSION}
    )
    zero = _row(scored["zero_plus_global"], "deck_universe")
    not_listed = _row(scored["global_only"], "deck_universe")
    assert zero["status"] == "ZERO_COUNT"
    assert zero["percentile"] == 0.0
    assert not_listed["status"] == "NO_VALUE"
    assert not_listed["reason"] == "NOT_LISTED"
    assert not_listed["percentile"] is None  # skipped, never filled with 0


def test_edhrec_not_listed_is_skipped_by_default_and_never_filled_with_zero() -> None:
    observations = {
        f"c{index}": {"commander_inclusion": Observation(0.5 - 0.05 * index, 50 - 5 * index, 100)}
        for index in range(6)
    } | {"unlisted": {}}
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"commander_inclusion": 1.0},
        min_coverage=0.0,
        min_components=0,
        require_commander_signal=False,
    )
    scored = strength.score_pool(settings, observations, {strength.COMMANDER_INCLUSION})
    row = _row(scored["unlisted"], "commander_inclusion")
    assert row["status"] == "NO_VALUE"
    assert row["reason"] == "NOT_LISTED"
    assert scored["unlisted"]["index"] is None
    # the Owner can still switch the old behaviour on, and then it is named as such
    lowest = StrengthSettings(
        weights=settings.weights,
        min_coverage=0.0,
        min_components=0,
        require_commander_signal=False,
        missing_value={"commander_inclusion": "lowest"},
    )
    scored = strength.score_pool(lowest, observations, {strength.COMMANDER_INCLUSION})
    assert _row(scored["unlisted"], "commander_inclusion")["status"] == "MISSING_AS_LOWEST"


def test_u_only_comes_with_a_reason_code_for_a_real_gap() -> None:
    observations, collected = _zero_pool()
    scored = strength.score_pool(_zero_settings(), observations, collected)
    for card in scored.values():
        if card["tier"] == "U":
            assert card["reason"] in {
                "TOO_LITTLE_DATA",
                "NO_COMMANDER_SIGNAL",
                "NO_SOURCE_FOR_COMMANDER",
                "NO_POSITIVE_WEIGHT",
                "ZERO_COUNT_ONLY",
            }
    # the card with global inclusion only is a real gap about this commander: U with its code
    assert scored["global_only"]["tier"] == "U"
    assert scored["global_only"]["reason"] == "NO_COMMANDER_SIGNAL"


# ---------- new components in score_pool ----------


def test_a_direct_corpus_component_is_used_as_the_score_without_ranking() -> None:
    observations = {
        f"c{index}": {"corpus_log_lift": Observation(value, 20, 2823)}
        for index, value in enumerate([0.1, 0.5, 0.9, 0.75, 0.3, 0.6])
    }
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"corpus_log_lift": 1.0},
        min_coverage=0.0,
        min_components=1,
        require_commander_signal=False,
    )
    scored = strength.score_pool(settings, observations, {strength.CORPUS_LOG_LIFT})
    # 0.9 is shown as it is; the index counts the part above neutral: max(0, 2 * 0.9 - 1) = 0.8
    assert _row(scored["c2"], "corpus_log_lift")["value"] == 0.9
    assert scored["c2"]["index"] == pytest.approx(80.0)
    assert _row(scored["c2"], "corpus_log_lift")["percentile"] == pytest.approx(0.8)
    # neutral and below neutral score 0, never a positive amount
    assert scored["c1"]["index"] == 0.0 and scored["c0"]["index"] == 0.0
    assert _row(scored["c4"], "corpus_log_lift")["value"] == 0.3
    assert _row(scored["c2"], "corpus_log_lift")["data_class"] == "DERIVED_DESCRIPTIVE"


def test_a_commander_without_the_corpus_has_no_coverage_penalty_for_it() -> None:
    observations = {
        f"c{index}": {"commander_inclusion": Observation(0.9 - 0.1 * index, 90 - 10 * index, 1000)}
        for index in range(6)
    }
    settings = StrengthSettings(min_coverage=0.0, min_components=1)
    scored = strength.score_pool(settings, observations, {strength.COMMANDER_INCLUSION})
    card = scored["c0"]
    row = _row(card, "corpus_tuned")
    assert row["status"] == "NOT_COLLECTED"
    # coverage = the one present weight (3) over the weighted components the source can exist for:
    # commander 3, bracket 2, deck universe 4, global 1, combos 0.5; the corpus signals are not in it
    assert card["coverage"] == pytest.approx(3.0 / 10.5, abs=1e-4)
    uncollected = {
        name: _row(card, name)["status"]
        for name in (
            "corpus_tuned",
            "corpus_log_lift",
            "corpus_bracket_slope",
            "tournament",
            "edhrec_theme_reach",
        )
    }
    assert set(uncollected.values()) == {"NOT_COLLECTED"}


@pytest.mark.parametrize("component", ["corpus_log_lift", "corpus_bracket_slope"])
def test_a_lift_or_slope_below_neutral_never_raises_the_index_or_the_tier(component: str) -> None:
    """The weighted mean would raise a card whose other scores are near 0 by any positive
    score, so the index counts only the part above neutral (0.5)."""
    base = {name: 0.0 for name in strength.COMPONENTS}

    def settings(weight: float) -> StrengthSettings:
        return StrengthSettings(
            weights=base | {"deck_universe": 4.0, component: weight},
            share_scale="share",
            min_coverage=0.0,
            min_components=1,
            require_commander_signal=False,
            separate_lands=False,
        )

    cards = [f"x{i}" for i in range(12)]
    observations: dict[str, dict[str, Observation]] = {}
    for i, card in enumerate(cards):
        share = 0.0 if i == 0 else 0.002 * i  # x0: a counted zero, the others near 0 too
        observations[card] = {"deck_universe": Observation(share, round(share * 2000), 2000)}
    below = [0.0, 0.1, 0.3, 0.49, 0.5]
    for i, value in enumerate(below):
        observations[cards[i]][component] = Observation(value, 20, 2823)
    collected = {strength.DECK_UNIVERSE, component}
    with_weight = strength.score_pool(settings(2.0), observations, collected)
    without = strength.score_pool(settings(0.0), observations, collected)
    order = {tier: rank for rank, tier in enumerate(("S", "A", "B", "C", "D"))}
    for card in cards[: len(below)]:
        low, high = with_weight[card]["index"], without[card]["index"]
        assert low is not None and high is not None
        assert low <= high + 1e-9, (card, low, high)
        assert order[with_weight[card]["tier"]] >= order[without[card]["tier"]]
    # an above-neutral value does raise it
    observations[cards[0]][component] = Observation(0.9, 20, 2823)
    raised = strength.score_pool(settings(2.0), observations, collected)[cards[0]]["index"]
    assert raised is not None and raised > without[cards[0]]["index"]
