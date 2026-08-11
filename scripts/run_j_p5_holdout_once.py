from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from commander_lab.decision_statistics import (
    holm_adjust,
    monte_carlo_standard_error,
    paired_bootstrap_interval,
    paired_randomization_p_value,
    paired_standardized_effect,
    quantile_summary,
)
from commander_lab.models import PilotConfig, VariantSwap
from commander_lab.optimization import build_search_candidate, run_paired_structural_comparison
from commander_lab.optimization.jp5 import build_recommendation_trace, scenario_heterogeneity
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT_PATH = ROOT / 'data/evals/holdout/J_P5_OPTIMIZER_HOLDOUT_v1.json'
SEAL_PATH = ROOT / 'docs/J_P5_HOLDOUT_SEAL.json'
FREEZE_PATH = ROOT / 'docs/J_P5_DEVELOPMENT_FREEZE.json'
FINALISTS_PATH = ROOT / 'docs/J_P5_FROZEN_FINALISTS.json'
OUTPUT_PATH = ROOT / 'docs/J_P5_HOLDOUT_FIRST_EVALUATION.json'
POLICY_PATH = ROOT / 'config/J_P5_SEARCH_POLICY_v1.json'
HOLDOUT_SHA = 'b75e8622097221b00ad51322e2ad13fe5158cfd8647e92d2cb21a0d65b447203'


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pilot_mode_adapter(label: str) -> tuple[str, str]:
    # The sealed corpus used "heuristic" as an execution-policy label. The model's
    # actual PilotDecisionMode enum is deterministic/stochastic; heuristic strength
    # is encoded separately by PilotStrength. This mapping is fixed before outcomes.
    if label == 'heuristic':
        return 'deterministic', 'sealed heuristic label maps to deterministic decision mode; heuristic quality is represented by pilot_strength'
    if label in {'deterministic', 'stochastic'}:
        return label, 'direct model enum mapping'
    raise ValueError(f'unsupported sealed pilot mode label: {label}')


def validate_preconditions() -> dict[str, object]:
    if OUTPUT_PATH.exists():
        raise RuntimeError('J-P5 optimizer holdout has already been evaluated; rerun refused')
    if _sha(HOLDOUT_PATH) != HOLDOUT_SHA:
        raise RuntimeError('sealed J-P5 optimizer holdout hash mismatch')
    seal = json.loads(SEAL_PATH.read_text(encoding='utf-8'))
    if seal.get('sha256') != HOLDOUT_SHA or seal.get('outcomes_evaluated') is not False or seal.get('first_evaluation_status') != 'not_run':
        raise RuntimeError('holdout seal does not permit a first evaluation')
    freeze = json.loads(FREEZE_PATH.read_text(encoding='utf-8'))
    if seal.get('development_freeze_sha256') != _sha(FREEZE_PATH):
        raise RuntimeError('holdout seal is not bound to the current development freeze')
    if freeze.get('holdout_sha256') != HOLDOUT_SHA or freeze.get('holdout_outcomes_seen') is not False:
        raise RuntimeError('development freeze does not bind the untouched holdout')
    for rel, expected in freeze['file_sha256'].items():
        actual = _sha(ROOT / rel)
        if actual != expected:
            raise RuntimeError(f'development freeze mismatch for {rel}: {actual} != {expected}')
    finalists = json.loads(FINALISTS_PATH.read_text(encoding='utf-8'))
    if finalists.get('status') != 'frozen_pre_holdout' or finalists.get('holdout_outcomes_seen') is not False:
        raise RuntimeError('finalists are not frozen pre-holdout')
    holdout = json.loads(HOLDOUT_PATH.read_text(encoding='utf-8'))
    if holdout.get('status') != 'sealed_untouched' or holdout.get('outcomes_evaluated_at_seal') is not False:
        raise RuntimeError('holdout corpus is not untouched')
    service = CommanderToolService(ROOT)
    for scenario in holdout['scenarios']:
        service._deck(scenario['deck_id'])
        for opponent_id in scenario['opponent_deck_ids']:
            service._deck(opponent_id)
        _pilot_mode_adapter(scenario['pilot_mode'])
        seat = int(scenario['starting_player_seat'])
        if not 0 <= seat < int(scenario['pod_size']):
            raise RuntimeError(f'invalid seat in {scenario["scenario_id"]}')
    return {
        'holdout_sha256': HOLDOUT_SHA,
        'scenario_count': len(holdout['scenarios']),
        'development_freeze_sha256': _sha(FREEZE_PATH),
        'pilot_mode_adapter': {'heuristic': 'deterministic'},
    }


def _build_variant(service: CommanderToolService, row: dict[str, object]):
    deck_id = str(row['deck_id'])
    baseline = service._deck(deck_id)
    swap = VariantSwap(remove=str(row['remove']), add_candidate_id=str(row['add_candidate_id']))
    built = build_search_candidate(
        baseline,
        (swap,),
        service.candidates,
        service._optimization_constraints(deck_id),
        inventory=service.candidate_inventory,
        verified_physical_names=service.verified_candidate_names,
    )
    if not built.constraint_report.valid:
        raise RuntimeError(f'frozen finalist failed constraints: {deck_id}: {built.constraint_report.issues}')
    if built.variant.deck_hash != row['variant_hash']:
        raise RuntimeError(f'frozen finalist identity drift for {deck_id}')
    return baseline, built


def _aggregate(deck_rows: list[dict[str, object]], all_effects: list[float]) -> dict[str, object]:
    scenario_effects = [float(row['paired']['placement_improvement']) for row in deck_rows]
    q = quantile_summary(scenario_effects)
    return {
        'scenario_count': len(deck_rows),
        'pair_count': len(all_effects),
        'central_effect': fmean(scenario_effects),
        'scenario_quantiles': q,
        'worst_scenario_effect': min(scenario_effects),
        'scenario_heterogeneity': scenario_heterogeneity(scenario_effects),
        'all_pair_effect_mean': fmean(all_effects),
        'all_pair_effect_size': paired_standardized_effect(all_effects),
        'all_pair_monte_carlo_standard_error': monte_carlo_standard_error(all_effects),
        'all_pair_confidence_interval': paired_bootstrap_interval(all_effects, seed=2026081105),
        'all_pair_randomization_p_value': paired_randomization_p_value(all_effects, seed=2026081106),
        'confidence_interval_interpretation': 'model-internal Monte Carlo uncertainty only; not an empirical Commander confidence interval',
        'pod_size_effects': {str(size): fmean(float(row['paired']['placement_improvement']) for row in deck_rows if int(row['pod_size']) == size) for size in (3,4,5)},
        'seat_effects': {str(seat): fmean(float(row['paired']['placement_improvement']) for row in deck_rows if int(row['starting_player_seat']) == seat) for seat in sorted({int(row['starting_player_seat']) for row in deck_rows})},
        'opponent_uncertainty_effects': [float(row['paired']['placement_improvement']) for row in deck_rows if row['uncertainty_axis'] == 'opponent_uncertainty'],
    }


def run() -> dict[str, object]:
    pre = validate_preconditions()
    holdout = json.loads(HOLDOUT_PATH.read_text(encoding='utf-8'))
    finalists_doc = json.loads(FINALISTS_PATH.read_text(encoding='utf-8'))
    finalists = {row['deck_id']: row for row in finalists_doc['finalists']}
    policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    gate = policy['holdout_recommendation_gate']
    service = CommanderToolService(ROOT)
    rows_by_deck: dict[str, list[dict[str, object]]] = defaultdict(list)
    pair_effects_by_deck: dict[str, list[float]] = defaultdict(list)

    for scenario in holdout['scenarios']:
        finalist = finalists[scenario['deck_id']]
        baseline, built = _build_variant(service, finalist)
        actual_mode, mapping_note = _pilot_mode_adapter(scenario['pilot_mode'])
        metrics, pairs = run_paired_structural_comparison(
            baseline=baseline,
            variant=built.variant,
            opponents=tuple(service._deck(x) for x in scenario['opponent_deck_ids']),
            iterations=int(scenario['paired_seed_count']),
            seed=int(scenario['paired_seed_master']),
            pilot_config=PilotConfig(strength=scenario['pilot_strength'], mode=actual_mode),
            max_turns=14,
            pair_id=f"jp5-holdout-{scenario['scenario_id']}",
            starting_player_seat=int(scenario['starting_player_seat']),
        )
        pair_effects = [float(row['baseline_placement']) - float(row['variant_placement']) for row in pairs]
        pair_effects_by_deck[scenario['deck_id']].extend(pair_effects)
        rows_by_deck[scenario['deck_id']].append({
            'scenario_id': scenario['scenario_id'],
            'pod_size': scenario['pod_size'],
            'starting_player_seat': scenario['starting_player_seat'],
            'opponent_deck_ids': scenario['opponent_deck_ids'],
            'pilot_strength': scenario['pilot_strength'],
            'sealed_pilot_mode_label': scenario['pilot_mode'],
            'executed_pilot_mode': actual_mode,
            'pilot_mode_mapping_note': mapping_note,
            'uncertainty_axis': scenario['uncertainty_axis'],
            'paired': metrics.as_dict(),
        })

    aggregate = {deck: _aggregate(rows, pair_effects_by_deck[deck]) for deck, rows in rows_by_deck.items()}
    decks = sorted(aggregate)
    raw_ps = [float(aggregate[deck]['all_pair_randomization_p_value']) for deck in decks]
    adjusted = holm_adjust(raw_ps)
    recommendation_traces: list[dict[str, object]] = []
    for deck_id, adj_p in zip(decks, adjusted, strict=True):
        agg = aggregate[deck_id]
        finalist = finalists[deck_id]
        passed = (
            float(agg['central_effect']) >= float(gate['central_paired_effect_minimum'])
            and float(agg['scenario_quantiles']['q25']) >= float(gate['scenario_q25_effect_minimum'])
            and float(agg['worst_scenario_effect']) >= float(gate['worst_scenario_effect_minimum'])
            and adj_p <= float(gate['holm_adjusted_model_internal_p_value_maximum'])
        )
        agg['holm_adjusted_model_internal_p_value'] = adj_p
        agg['holdout_recommendation_gate_pass'] = passed
        status = 'passed_first_evaluation' if passed else 'first_evaluation_not_supportive'
        seeds = [seed for row in rows_by_deck[deck_id] for seed in row['paired']['seeds']]
        recommendation_traces.append(build_recommendation_trace(
            candidate_change=({'remove': finalist['remove'], 'add_candidate_id': finalist['add_candidate_id']},),
            constraint_status={'valid': True, 'canonical_mutation': False},
            baseline_identity={'deck_id': deck_id, 'deck_hash': service._deck(deck_id).deck_hash},
            variant_identity={'variant_id': finalist['id'], 'deck_hash': finalist['variant_hash']},
            paired_seeds=tuple(int(seed) for seed in seeds),
            affected_roles=(),
            central_effect={
                'placement_improvement': agg['central_effect'],
                'effect_size': agg['all_pair_effect_size'],
                'monte_carlo_standard_error': agg['all_pair_monte_carlo_standard_error'],
                'confidence_interval': agg['all_pair_confidence_interval'],
                'confidence_interval_interpretation': agg['confidence_interval_interpretation'],
                'paired_randomization_p_value': agg['all_pair_randomization_p_value'],
                'holm_adjusted_model_internal_p_value': adj_p,
            },
            worst_case_effect=float(agg['worst_scenario_effect']),
            sensitivity={
                'scenario_heterogeneity': agg['scenario_heterogeneity'],
                'pod_size_effects': agg['pod_size_effects'],
                'seat_effects': agg['seat_effects'],
                'opponent_uncertainty_effects': agg['opponent_uncertainty_effects'],
            },
            holdout_status=status,
            recommendation_confidence_value='holdout_supported_model_internal' if passed else 'not_supported_by_holdout',
        ))

    output = {
        'schema_version': '1.0',
        'phase': 'J-P5-holdout-first-evaluation',
        'evidence_type': 'structural_model_estimates',
        'truth_boundary': 'first and only intended optimizer holdout evaluation; simulation/model evidence, not empirical Commander winrates',
        'holdout_identity': {'id': holdout['holdout_id'], 'sha256': HOLDOUT_SHA, 'scenario_count': holdout['scenario_count']},
        'preconditions': pre,
        'first_and_only_intended_evaluation': True,
        'evaluation_count': 1,
        'post_holdout_tuning_performed': False,
        'no_finalist_reselection_after_holdout': True,
        'holdout_multiple_comparisons': policy['holdout_multiple_comparisons'],
        'holdout_gate': gate,
        'scenario_results': {deck: rows_by_deck[deck] for deck in decks},
        'aggregate_results': aggregate,
        'recommendation_traces': recommendation_traces,
        'automatic_canonical_mutation': False,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    seal = json.loads(SEAL_PATH.read_text(encoding='utf-8'))
    seal.update({
        'outcomes_evaluated': True,
        'first_evaluation_status': 'completed',
        'evaluation_count': 1,
        'first_evaluation_artifact': OUTPUT_PATH.relative_to(ROOT).as_posix(),
        'first_evaluation_artifact_sha256': _sha(OUTPUT_PATH),
        'post_holdout_tuning_performed': False,
    })
    SEAL_PATH.write_text(json.dumps(seal, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'holdout': 'completed_once',
        'aggregate_results': aggregate,
        'recommendation_gate': {trace['baseline_identity']['deck_id']: trace['holdout_status'] for trace in recommendation_traces},
        'post_holdout_tuning_performed': False,
    }, indent=2, sort_keys=True))
    return output


if __name__ == '__main__':
    run()
