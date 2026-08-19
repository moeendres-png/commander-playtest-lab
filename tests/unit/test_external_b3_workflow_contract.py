from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_external_xmage_workflow_uses_current_b3_regression_runner() -> None:
    workflow = (ROOT / ".github/workflows/external-engine-integration.yml").read_text(
        encoding="utf-8"
    )

    assert "run_external_phase851.py" not in workflow
    assert "python scripts/run_external_b3_regression.py" in workflow
    assert '[[ "$XMAGE_COMMIT" =~ ^[0-9a-f]{40}$ ]]' in workflow
    assert "COMMANDER_LAB_XMAGE_BRIDGE_JAR" in workflow
    assert "COMMANDER_LAB_XMAGE_BRIDGE_CMD=java -jar" in workflow
    assert "mvn -B -ntp verify" in workflow


def test_external_b3_runner_preserves_provider_and_evidence_boundaries() -> None:
    runner = (ROOT / "scripts/run_external_b3_regression.py").read_text(encoding="utf-8")

    assert '"scope": "b3_regression_only"' in runner
    assert '"evidence_class": "external_rules_engine"' in runner
    assert '"provider_decision": "NO_PROVIDER_READY"' in runner
    assert '"production_ready": False' in runner
    assert '"canonical_mutation_performed": False' in runner
    assert '"tactical_oracle_substitution": False' in runner
    assert '"post_b3_capabilities_claimed": False' in runner

    for capability in (
        "mulligan_supported",
        "legal_actions_supported",
        "action_submission_supported",
        "event_log_supported",
        "replay_supported",
        "target_selection_supported",
        "mode_selection_supported",
        "trigger_order_supported",
    ):
        assert f'"{capability}"' in runner
