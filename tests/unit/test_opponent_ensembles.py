import pytest

from commander_lab.models import (
    EnsembleWeightMode,
    ObservationStatus,
    ObservedConstraint,
    OpponentCardAssumption,
    OpponentEnsemble,
    OpponentVariant,
    VariantWeight,
)


def v(vid="v", known=(), assumed=(), weight=None, colors=frozenset({"U"})):
    return OpponentVariant(
        variant_id=vid,
        name=vid,
        commander="C",
        commander_color_identity=colors,
        known_cards=known,
        assumed_cards=assumed,
        weight=VariantWeight(mode=EnsembleWeightMode.UNWEIGHTED, value=weight),
    )


def test_empty_and_weight_sum_rejected():
    with pytest.raises(ValueError):
        OpponentEnsemble(
            ensemble_id="e",
            name="e",
            commander="C",
            commander_color_identity=frozenset({"U"}),
            variants=[],
        )
    a = v("a")
    b = v("b")
    a = a.model_copy(update={"weight": VariantWeight(mode=EnsembleWeightMode.MANUAL, value=0.8)})
    b = b.model_copy(update={"weight": VariantWeight(mode=EnsembleWeightMode.MANUAL, value=0.3)})
    with pytest.raises(ValueError):
        OpponentEnsemble(
            ensemble_id="e",
            name="e",
            commander="C",
            commander_color_identity=frozenset({"U"}),
            variants=[a, b],
            weight_mode=EnsembleWeightMode.MANUAL,
        )


def test_color_identity_and_known_assumed_separation():
    c = OpponentCardAssumption(
        card_name="x",
        status=ObservationStatus.SYNTHETIC_ASSUMPTION,
        color_identity=frozenset({"R"}),
    )
    with pytest.raises(ValueError):
        v(assumed=(c,))
    k = OpponentCardAssumption(card_name="x", status=ObservationStatus.REPORTED_BY_PLAYER)
    a = OpponentCardAssumption(card_name="x", status=ObservationStatus.SYNTHETIC_ASSUMPTION)
    with pytest.raises(ValueError):
        v(known=(k,), assumed=(a,))


def test_observed_constraint_enforced():
    c = ObservedConstraint(constraint_id="c", kind="card_present", value="Known")
    with pytest.raises(ValueError):
        OpponentEnsemble(
            ensemble_id="e",
            name="e",
            commander="C",
            commander_color_identity=frozenset({"U"}),
            variants=[v()],
            observed_constraints=(c,),
        )


def test_equal_and_worst_case_modes_need_no_fake_percentages():
    for mode in (EnsembleWeightMode.EQUAL, EnsembleWeightMode.WORST_CASE):
        ensemble = OpponentEnsemble(
            ensemble_id=f"e-{mode.value}",
            name="e",
            commander="C",
            commander_color_identity=frozenset({"U"}),
            variants=[v("a"), v("b")],
            weight_mode=mode,
        )
        assert ensemble.weight_mode == mode


def test_variant_default_confidence_is_unknown_not_fabricated():
    assert v("confidence-unknown").confidence is None


def test_variant_cannot_expand_ensemble_color_identity():
    variant = v("bad", colors=frozenset({"U", "R"}))
    with pytest.raises(ValueError, match="color identity"):
        OpponentEnsemble(
            ensemble_id="e-colors",
            name="e",
            commander="C",
            commander_color_identity=frozenset({"U"}),
            variants=[variant],
        )


def test_observed_absence_rejects_assumed_card():
    assumed = OpponentCardAssumption(
        card_name="Absent",
        status=ObservationStatus.SYNTHETIC_ASSUMPTION,
    )
    constraint = ObservedConstraint(
        constraint_id="absent",
        kind="card_absent",
        value="Absent",
    )
    with pytest.raises(ValueError, match="observed absence"):
        OpponentEnsemble(
            ensemble_id="e-absence",
            name="e",
            commander="C",
            commander_color_identity=frozenset({"U"}),
            variants=[v("a", assumed=(assumed,))],
            observed_constraints=(constraint,),
        )
