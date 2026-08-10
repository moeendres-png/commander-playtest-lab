from pathlib import Path

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
from commander_lab.opponent_ensembles import OpponentEnsembleStore


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


def test_seed_ensembles_unweighted_and_no_confirmed_assumptions(repo_root: Path):
    s = OpponentEnsembleStore(repo_root)
    ens = s.list()
    assert len(ens) == 3
    assert all(e.weight_mode == EnsembleWeightMode.UNWEIGHTED for e in ens)
    assert all(
        not any(
            c.status == ObservationStatus.DIRECTLY_OBSERVED
            for v in e.variants
            for c in v.assumed_cards
        )
        for e in ens
    )
    assert all(not e.automatic_profile_overwrite for e in ens)


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


def test_ensemble_versioning_retains_old_variant_set(tmp_path: Path):
    store = OpponentEnsembleStore(tmp_path)
    original = OpponentEnsemble(
        ensemble_id="versioned-ensemble-v1",
        name="e",
        commander="C",
        commander_color_identity=frozenset({"U"}),
        variants=[v("a")],
    )
    store.save(original)
    updated = store.add_variant("versioned-ensemble-v1", v("b"), "versioned-ensemble-v2")
    assert updated.version == 2
    assert updated.supersedes_ensemble_id == "versioned-ensemble-v1"
    assert [variant.variant_id for variant in store.load("versioned-ensemble-v1").variants] == ["a"]
    assert [variant.variant_id for variant in updated.variants] == ["a", "b"]


def test_seed_reports_disclose_uncertainty(repo_root: Path):
    store = OpponentEnsembleStore(repo_root)
    report = store.report("cosmic-spiderman-ensemble-v1")
    assert "Synthetic:" in report
    assert "Known cards:" in report
    assert "Assumed cards:" in report
    assert "Roles:" in report
    assert "Sources:" in report
