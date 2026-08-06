from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.tactical import TacticalRuleOracle
from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.models import (
    CompiledPilotPolicy,
    ConditionOperator,
    FormatBand,
    PilotConfig,
    PilotRule,
    PilotRuleCondition,
    PolicyEvalScenario,
    PrimerEvidenceType,
    PrimerRuleStatus,
)
from commander_lab.primer import PrimerToPilotCompiler, RuleDslError

ROOT = Path(__file__).resolve().parents[2]


def _rules(path: str) -> tuple[PilotRule, ...]:
    payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return tuple(PilotRule.model_validate(row) for row in payload["rules"])


def test_inferred_rule_cannot_be_activated_without_manual_approval() -> None:
    row = _rules("data/primer_rules/rules/automatic_candidates.json")[0].model_dump(mode="json")
    row["status"] = "active"
    with pytest.raises(ValidationError, match="manual approval"):
        PilotRule.model_validate(row)


def test_safe_dsl_rejects_unknown_field() -> None:
    compiler = PrimerToPilotCompiler(ROOT)
    rule = _rules("data/primer_rules/rules/korvold_current_rules.json")[0]
    unsafe = rule.model_copy(
        update={"condition": PilotRuleCondition(op=ConditionOperator.TRUTHY, field="context.__class__")}
    )
    report = compiler.validate_rules((unsafe,))
    assert report.valid is False
    assert any(issue.code == "unsafe_condition" for issue in report.issues)


def test_automatic_extraction_remains_disabled() -> None:
    rules = _rules("data/primer_rules/rules/automatic_candidates.json")
    assert len(rules) == 8
    assert all(rule.status == PrimerRuleStatus.NEEDS_REVIEW for rule in rules)
    assert all(rule.evidence_type == PrimerEvidenceType.PRIMER_INFERRED for rule in rules)


def test_conflicts_are_detected_and_not_silently_merged() -> None:
    compiler = PrimerToPilotCompiler(ROOT)
    rule = _rules("data/primer_rules/rules/korvold_current_rules.json")[0]
    opposing = rule.model_copy(
        update={
            "rule_id": "korvold.current.commander-immediate-value.synthetic-opposite",
            "source_id": "synthetic-conflict-fixture",
            "score_adjustment": 2.0,
        }
    )
    conflicts = compiler.detect_conflicts((rule, opposing))
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "opposing_adjustment"
    with pytest.raises(RuleDslError, match="unresolved rule conflicts"):
        compiler.compile_policy(
            policy_id="conflict-test",
            version="1.0.0",
            commander=rule.commander,
            deck_hash=rule.deck_hash,
            format_band=rule.format_band,
            base_pilot_name="KorvoldPilot",
            rules=(rule, opposing),
        )


def test_deck_hash_scope_is_enforced() -> None:
    compiler = PrimerToPilotCompiler(ROOT)
    rules = _rules("data/primer_rules/rules/korvold_current_rules.json")
    with pytest.raises(RuleDslError, match="deck version"):
        compiler.compile_policy(
            policy_id="wrong-deck",
            version="1.0.0",
            commander="Korvold, Fae-Cursed King",
            deck_hash="0" * 64,
            format_band=FormatBand.NORMAL_FOUR_PLAYER,
            base_pilot_name="KorvoldPilot",
            rules=rules,
        )


def test_policy_overlay_improves_controlled_counter_decision() -> None:
    compiler = PrimerToPilotCompiler(ROOT)
    policy = CompiledPilotPolicy.model_validate_json(
        (ROOT / "data/primer_rules/policies/rogshai_current_policy-1.0.1.json").read_text(encoding="utf-8")
    )
    payload = json.loads((ROOT / "data/primer_rules/evals/golden_scenarios.json").read_text(encoding="utf-8"))
    scenario = next(
        PolicyEvalScenario.model_validate(row)
        for row in payload["scenarios"]
        if row["scenario_id"] == "rogshai-save-counter"
    )
    decks = load_project_structural_decks(ROOT, include_synthetic_fixtures=True, include_current_opponents=True)
    deck = decks["rogshai/current"]
    pilot = build_pilot(PilotConfig(pilot_name="RogShaiPilot"), strategy="rogshai")
    result = compiler.evaluate_policy(
        base_pilot=pilot,
        policy=policy,
        scenarios=(scenario,),
        deck_cards=tuple(card.oracle_name for card in deck.cards),
    )[0]
    assert result.baseline_action_id == "counter-value"
    assert result.overlay_action_id == "pass"
    assert result.improved is True


def test_tactical_oracle_semantics_used_by_curated_rules() -> None:
    oracle = TacticalRuleOracle()
    kediss = oracle.evaluate("kediss_trigger", {"commander_combat_damage": 7, "opponent_count": 3})
    assert kediss["normal_damage_each"] == 7
    assert kediss["additional_commander_damage"] == 0
    jeska = oracle.evaluate("jeska_triple", {"combat_damage": 6, "is_commander": True})
    assert jeska["commander_damage"] == 18
    silence = oracle.evaluate("silence_restriction", {"silence_resolved": True, "same_turn": True})
    assert silence["can_cast_spell"] is False
    assert silence["can_activate_ability"] is True


def test_primer_layer_does_not_mutate_decks() -> None:
    before = {
        name: (ROOT / name).read_bytes()
        for name in ("data/decks/korvold_current.json", "data/decks/rogshai_current.json")
    }
    compiler = PrimerToPilotCompiler(ROOT)
    compiler.validate_rules(_rules("data/primer_rules/rules/korvold_current_rules.json"))
    after = {name: (ROOT / name).read_bytes() for name in before}
    assert after == before


def test_opening_hand_overlay_applies_curated_mulligan_rule() -> None:
    from commander_lab.models import PilotActionView
    from commander_lab.primer import PilotPolicyOverlay

    policy = CompiledPilotPolicy.model_validate_json(
        (ROOT / "data/primer_rules/policies/korvold_current_policy-1.0.1.json").read_text(encoding="utf-8")
    )
    decks = load_project_structural_decks(ROOT, include_synthetic_fixtures=True, include_current_opponents=True)
    deck = decks["korvold/current"]
    pilot = build_pilot(PilotConfig(pilot_name="KorvoldPilot"), strategy="korvold")
    overlay = PilotPolicyOverlay(pilot, policy, deck_cards=tuple(card.oracle_name for card in deck.cards))
    hand = (
        PilotActionView(action_id="land-a", action_kind="card", card_name="Forest", metadata={"is_land": True}),
        PilotActionView(action_id="land-b", action_kind="card", card_name="Swamp", metadata={"is_land": True}),
        PilotActionView(action_id="ramp", action_kind="card", card_name="Nature's Lore", mana_cost=2),
    )
    baseline = pilot.opening_hand_score(hand, commander_names=("Korvold, Fae-Cursed King",))
    adjusted, traces = overlay.opening_hand_score_with_trace(
        hand,
        commander_names=("Korvold, Fae-Cursed King",),
        context={"always": True, "ramp_count": 1, "sacrifice_material_count": 0},
    )
    assert adjusted < baseline
    assert any(trace.rule_id == "korvold.current.mulligan-ramp-without-sacrifice" for trace in traces)


def test_tool_service_policy_eval_is_scoped_and_does_not_change_decks() -> None:
    from commander_lab.models import RunPolicyEvalInput, ToolStatus
    from commander_lab.tools import CommanderToolService

    before = {
        name: (ROOT / name).read_bytes()
        for name in ("data/decks/korvold_current.json", "data/decks/rogshai_current.json")
    }
    response = CommanderToolService(ROOT).run_policy_eval(
        RunPolicyEvalInput(
            policy_path="data/primer_rules/policies/rogshai_current_policy-1.0.1.json",
            scenario_path="data/primer_rules/evals/golden_scenarios.json",
            deck_id="rogshai/current",
            strategy="rogshai",
            output_name="test_policy_eval.json",
        )
    )
    assert response.status == ToolStatus.COMPLETED
    assert response.result["scenario_count"] == 3
    assert response.result["improved_count"] >= 1
    after = {name: (ROOT / name).read_bytes() for name in before}
    assert after == before


def test_rule_with_missing_required_card_does_not_trigger() -> None:
    from commander_lab.primer import PilotPolicyOverlay

    policy = CompiledPilotPolicy.model_validate_json(
        (ROOT / "data/primer_rules/policies/rogshai_current_policy-1.0.1.json").read_text(encoding="utf-8")
    )
    payload = json.loads((ROOT / "data/primer_rules/evals/golden_scenarios.json").read_text(encoding="utf-8"))
    scenario = next(
        PolicyEvalScenario.model_validate(row)
        for row in payload["scenarios"]
        if row["scenario_id"] == "rogshai-independent-axis"
    )
    pilot = build_pilot(PilotConfig(pilot_name="RogShaiPilot"), strategy="rogshai")
    overlay = PilotPolicyOverlay(pilot, policy, deck_cards=("Ishai, Ojutai Dragonspeaker",))
    action = next(action for action in scenario.actions if action.action_id == "cast-whirlwind")
    _, traces = overlay.evaluate_action_with_trace(scenario.state, action, context=scenario.context)
    assert all(trace.rule_id != "rogshai.current.independent-spellslinger-axis" for trace in traces)


def test_saved_replay_evidence_is_structural_and_parseable() -> None:
    replay = ROOT / "data/runs/tool_runs/matchup-2d03c57b/events/matchup-2d03c57b-00000000.jsonl"
    rows = [json.loads(line) for line in replay.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    assert all(row["estimate_type"] == "structural_model_estimates" for row in rows)
    assert any(row["event_type"] == "london_mulligan" for row in rows)


def test_replay_audit_reports_coverage_without_counterfactual_claim() -> None:
    compiler = PrimerToPilotCompiler(ROOT)
    policy = CompiledPilotPolicy.model_validate_json(
        (ROOT / "data/primer_rules/policies/rogshai_current_policy-1.0.1.json").read_text(encoding="utf-8")
    )
    report = compiler.audit_replay_coverage(
        policy=policy,
        replay_path="data/runs/tool_runs/matchup-2d03c57b/events/matchup-2d03c57b-00000000.jsonl",
    )
    assert report["event_count"] > 0
    assert report["estimate_types"] == ["structural_model_estimates"]
    assert report["counterfactual_redecision_status"].startswith("not_run")


def test_rule_activation_creates_reviewed_version_without_mutating_candidate() -> None:
    compiler = PrimerToPilotCompiler(ROOT)
    candidate = _rules("data/primer_rules/rules/automatic_candidates.json")[0]
    activated = compiler.activate_rule(
        candidate,
        version="1.0.1",
        approved_by="manual-review",
        approval_reason="Golden scenario and current deck hash reviewed",
    )
    assert candidate.status == PrimerRuleStatus.NEEDS_REVIEW
    assert activated.status == PrimerRuleStatus.ACTIVE
    assert activated.manually_approved is True
    assert activated.version == "1.0.1"
