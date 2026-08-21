from __future__ import annotations

import json

import pytest

from commander_lab.models.roles import CardRole, StructuralMechanic
from commander_lab.whole_deck.mechanics_fidelity import (
    STRUCTURAL_SEMANTIC_MODEL_VERSION,
    MechanicsFidelityTier,
    changed_card_multiset,
    classify_card_semantics,
    require_confirmatory_mechanics_artifact,
)
from commander_lab.whole_deck.search_context import SEMANTIC_UNKNOWN


def test_semantic_unknown_is_never_decision_safe() -> None:
    tier, reasons = classify_card_semantics(
        "Unknown Card",
        semantic_state=SEMANTIC_UNKNOWN,
        roles=(),
        mechanic_tags=(),
    )
    assert tier == MechanicsFidelityTier.UNSUPPORTED
    assert reasons == ("semantic_unknown",)


def test_silence_is_tactical_not_a_structural_counter() -> None:
    tier, reasons = classify_card_semantics(
        "Silence",
        semantic_state="structurally_modeled",
        roles=(CardRole.COUNTER,),
        mechanic_tags=(StructuralMechanic.STACK_INTERACTION,),
    )
    assert tier == MechanicsFidelityTier.TACTICAL_REQUIRED
    assert reasons == ("explicit_tactical_contract",)


def test_restricted_interaction_fails_to_higher_fidelity_layer() -> None:
    tier, reasons = classify_card_semantics(
        "Generic Restricted Removal",
        semantic_state="structurally_modeled",
        roles=(CardRole.REMOVAL,),
        mechanic_tags=(),
    )
    assert tier == MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED
    assert "target_wipe_or_combat_legality_not_mechanistic" in reasons


def test_mana_and_engine_abstractions_are_screening_only() -> None:
    ramp_tier, _ = classify_card_semantics(
        "Generic Mana Rock",
        semantic_state="structurally_modeled",
        roles=(CardRole.RAMP,),
        mechanic_tags=(),
    )
    engine_tier, _ = classify_card_semantics(
        "Generic Trigger Engine",
        semantic_state="structurally_modeled",
        roles=(CardRole.ENGINE,),
        mechanic_tags=(StructuralMechanic.TOKEN_ENGINE,),
    )
    assert ramp_tier == MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY
    assert engine_tier == MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY


def test_simple_known_draw_can_be_approximated_decision_safe() -> None:
    tier, _ = classify_card_semantics(
        "Simple Draw",
        semantic_state="structurally_modeled",
        roles=(CardRole.DRAW,),
        mechanic_tags=(),
    )
    assert tier == MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE


def test_variant_delta_is_multiset_aware() -> None:
    assert changed_card_multiset(
        ("Island", "Island", "Silence"),
        ("Island", "Plains", "Light of Hope"),
    ) == (
        ("Island", 1, "removed"),
        ("Light of Hope", 1, "added"),
        ("Plains", 1, "added"),
        ("Silence", 1, "removed"),
    )


def test_confirmatory_artifact_requires_current_semantic_model(tmp_path) -> None:
    path = tmp_path / "confirmatory-report.json"
    path.write_text(json.dumps({"decision": "PROMOTE"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="predates the mechanics fidelity contract"):
        require_confirmatory_mechanics_artifact(path)

    path.write_text(
        json.dumps(
            {
                "mechanics_fidelity": {
                    "pass": True,
                    "semantic_model_version": "old-model",
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="STALE_MODEL_VERSION"):
        require_confirmatory_mechanics_artifact(path)

    path.write_text(
        json.dumps(
            {
                "mechanics_fidelity": {
                    "pass": True,
                    "semantic_model_version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
                }
            }
        ),
        encoding="utf-8",
    )
    loaded = require_confirmatory_mechanics_artifact(path)
    assert loaded["pass"] is True
