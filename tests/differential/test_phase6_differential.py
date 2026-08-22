from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from commander_lab.evals import (
    EvalStatus,
    compare_observation,
    configured_backend_command,
    load_differential_cases,
    run_external_case,
)


def test_differential_subprocess_adapter_with_normalized_fake_backend(
    tmp_path: Path, repo_root: Path
) -> None:
    case = load_differential_cases(repo_root / "data/evals/differential/rules_cases.json")[0]
    script = tmp_path / "fake_backend.py"
    script.write_text(
        """
import json, sys
from pathlib import Path
input_path, output_path = map(Path, sys.argv[1:3])
payload = json.loads(input_path.read_text())
assert payload['case_id'] == 'commander_tax_third_cast'
output_path.write_text(json.dumps({
  'backend_version': 'fake-1',
  'normalized_output': {'total_cast_cost': 9, 'commander_tax': 4, 'legal': True}
}))
""".strip(),
        encoding="utf-8",
    )
    observation = run_external_case(
        case,
        backend="forge",
        command_template=(sys.executable, str(script), "{input}", "{output}"),
    )
    result = compare_observation(case, observation)
    assert result.status == EvalStatus.PASSED


def test_external_differential_gate_is_explicitly_unavailable_without_configuration() -> None:
    if configured_backend_command("forge") or configured_backend_command("xmage"):
        pytest.skip("real external backend configured in this environment")
    assert os.getenv("COMMANDER_LAB_FORGE_DIFFERENTIAL_CMD") is None
    assert os.getenv("COMMANDER_LAB_XMAGE_DIFFERENTIAL_CMD") is None


@pytest.mark.external
@pytest.mark.skipif(
    not (configured_backend_command("forge") or configured_backend_command("xmage")),
    reason="requires configured XMage or Forge differential command",
)
def test_real_xmage_or_forge_differential_cases(repo_root: Path) -> None:
    from commander_lab.evals import run_configured_differential_cases

    cases = load_differential_cases(repo_root / "data/evals/differential/rules_cases.json")
    results = run_configured_differential_cases(cases)
    assert len(results) >= 3
    failures = [
        result.model_dump(mode="json")
        for result in results
        if result.status != EvalStatus.PASSED
    ]
    assert not failures, failures
