from __future__ import annotations

import json
from pathlib import Path

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.models import CompiledPilotPolicy, PilotConfig, PolicyEvalScenario
from commander_lab.primer import PrimerToPilotCompiler

ROOT = Path(__file__).resolve().parents[2]


def test_curated_policy_golden_scenarios_do_not_regress() -> None:
    compiler = PrimerToPilotCompiler(ROOT)
    payload = json.loads(
        (ROOT / "data/primer_rules/evals/golden_scenarios.json").read_text(encoding="utf-8")
    )
    all_scenarios = tuple(PolicyEvalScenario.model_validate(row) for row in payload["scenarios"])
    decks = load_project_structural_decks(
        ROOT, include_synthetic_fixtures=True, include_current_opponents=True
    )
    cases = (
        (
            "rogshai/current",
            "rogshai",
            "data/primer_rules/policies/rogshai_current_policy-1.0.1.json",
        ),
    )
    improved = 0
    for deck_id, strategy, policy_path in cases:
        policy = CompiledPilotPolicy.model_validate_json(
            (ROOT / policy_path).read_text(encoding="utf-8")
        )
        scenarios = tuple(item for item in all_scenarios if item.commander == policy.commander)
        pilot = build_pilot(PilotConfig(pilot_name=policy.base_pilot_name), strategy=strategy)
        results = compiler.evaluate_policy(
            base_pilot=pilot,
            policy=policy,
            scenarios=scenarios,
            deck_cards=tuple(card.oracle_name for card in decks[deck_id].cards),
        )
        assert all(result.overlay_correct for result in results)
        improved += sum(result.improved for result in results)
    assert improved >= 1
