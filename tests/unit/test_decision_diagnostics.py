from pathlib import Path

from commander_lab.diagnostics import DecisionDiagnosticEngine, run_integrated_extension_smoke
from commander_lab.models import FailureCause

ROOT=Path(__file__).resolve().parents[2]


def _load(name): return DecisionDiagnosticEngine.load(ROOT/f'data/diagnostics/synthetic_cases/{name}.json')


def test_known_cause_poor_pilot():
    result=DecisionDiagnosticEngine().classify(_load('poor_pilot'),'WeakPilot')
    assert result.hypothesis==FailureCause.PILOT_DOES_NOT_RECOGNIZE_LINE
    assert result.cut_release_gate.startswith('blocked')


def test_known_cause_bad_card_passes_only_model_cut_gate():
    result=DecisionDiagnosticEngine().classify(_load('bad_card'),'Weak Card')
    assert result.hypothesis==FailureCause.GENUINE_DECK_CONSTRUCTION_ISSUE
    assert result.cut_release_gate=='model_supported_cut_candidate'
    assert result.empirically_proven is False


def test_known_cause_incomplete_package():
    assert DecisionDiagnosticEngine().classify(_load('incomplete_package'),'Support Card').hypothesis==FailureCause.PACKAGE_IS_INCOMPLETE


def test_known_cause_wrong_opponent():
    assert DecisionDiagnosticEngine().classify(_load('wrong_opponent'),'Test Card').hypothesis==FailureCause.OPPONENT_MODEL_IS_WRONG


def test_known_cause_random_variance():
    assert DecisionDiagnosticEngine().classify(_load('high_variance'),'Test Card').hypothesis==FailureCause.RANDOM_VARIANCE


def test_known_cause_wrong_structural_abstraction():
    assert DecisionDiagnosticEngine().classify(_load('wrong_structural'),'Test Card').hypothesis==FailureCause.SIMULATION_ABSTRACTION_IS_WRONG


def test_factor_comparison_and_next_experiment():
    engine=DecisionDiagnosticEngine(); dataset=_load('poor_pilot')
    comparison=engine.compare_effects(dataset)
    assert comparison.dominant_factor in {'pilot','action'}
    diagnosis=engine.classify(dataset,'WeakPilot')
    assert engine.next_experiment(diagnosis)['automatic_deck_change'] is False


def test_integrated_ten_step_smoke(tmp_path):
    report=run_integrated_extension_smoke(ROOT,tmp_path/'smoke.json')
    assert report.passed_steps==10
    assert report.status=='passed_with_limitations'
    assert [row.step for row in report.steps]==list(range(1,11))
    assert all(row.source_paths and row.source_hashes and row.validation_level for row in report.steps)
    assert report.external_engine_used is False
