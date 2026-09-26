from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from .models import (
    DifferentialCase,
    DifferentialObservation,
    EvalCaseResult,
    EvalStatus,
    EvalTier,
)


class DifferentialBackendUnavailable(RuntimeError):
    pass


def load_differential_cases(path: str | Path) -> tuple[DifferentialCase, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(DifferentialCase.model_validate(item) for item in payload["cases"])


def configured_backend_command(backend: str) -> tuple[str, ...] | None:
    env_name = {
        "forge": "COMMANDER_LAB_FORGE_DIFFERENTIAL_CMD",
        "xmage": "COMMANDER_LAB_XMAGE_DIFFERENTIAL_CMD",
    }[backend]
    raw = os.getenv(env_name)
    return tuple(shlex.split(raw)) if raw else None


def run_external_case(
    case: DifferentialCase,
    *,
    backend: str,
    command_template: tuple[str, ...],
    timeout_seconds: float = 60.0,
) -> DifferentialObservation:
    with tempfile.TemporaryDirectory(prefix="commander-lab-diff-") as temp_dir:
        input_path = Path(temp_dir) / "input.json"
        output_path = Path(temp_dir) / "output.json"
        input_path.write_text(
            json.dumps(
                {
                    "case_id": case.case_id,
                    "description": case.description,
                    "input_state": case.input_state,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        command = tuple(
            part.replace("{input}", str(input_path)).replace("{output}", str(output_path))
            for part in command_template
        )
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"{backend} differential command failed with {completed.returncode}: "
                f"{completed.stderr.strip()}"
            )
        if not output_path.exists():
            raise RuntimeError(f"{backend} differential command did not create {output_path}")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        return DifferentialObservation(
            case_id=case.case_id,
            backend=backend,
            normalized_output=dict(payload["normalized_output"]),
            backend_version=payload.get("backend_version"),
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def compare_observation(
    case: DifferentialCase,
    observation: DifferentialObservation,
) -> EvalCaseResult:
    mismatches: list[str] = []
    for key in case.comparison_keys:
        expected = case.expected_normalized.get(key)
        observed = observation.normalized_output.get(key)
        if expected != observed:
            mismatches.append(f"{key}: expected {expected!r}, observed {observed!r}")
    passed = not mismatches
    return EvalCaseResult(
        case_id=case.case_id,
        tier=EvalTier.DIFFERENTIAL,
        status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
        passed=passed,
        critical=case.critical,
        score=1.0 if passed else 0.0,
        expected={key: case.expected_normalized.get(key) for key in case.comparison_keys},
        observed={key: observation.normalized_output.get(key) for key in case.comparison_keys},
        details=tuple(mismatches) or (f"matched external {observation.backend} observation",),
        source=f"external:{observation.backend}:{observation.backend_version or 'unknown'}",
    )


def run_configured_differential_cases(
    cases: tuple[DifferentialCase, ...],
) -> list[EvalCaseResult]:
    results: list[EvalCaseResult] = []
    for case in cases:
        backends = (case.backend,) if case.backend != "either" else ("forge", "xmage")
        selected = next(
            (
                (backend, configured_backend_command(backend))
                for backend in backends
                if configured_backend_command(backend)
            ),
            None,
        )
        if selected is None:
            results.append(
                EvalCaseResult(
                    case_id=case.case_id,
                    tier=EvalTier.DIFFERENTIAL,
                    status=EvalStatus.BLOCKED,
                    passed=False,
                    critical=case.critical,
                    score=0.0,
                    expected=case.expected_normalized,
                    observed=None,
                    details=(
                        "no XMage or Forge differential command configured; set "
                        "COMMANDER_LAB_FORGE_DIFFERENTIAL_CMD or "
                        "COMMANDER_LAB_XMAGE_DIFFERENTIAL_CMD",
                    ),
                    source="pending_external_backend",
                )
            )
            continue
        backend, command = selected
        assert command is not None
        try:
            observation = run_external_case(case, backend=backend, command_template=command)
            results.append(compare_observation(case, observation))
        except Exception as exc:
            results.append(
                EvalCaseResult(
                    case_id=case.case_id,
                    tier=EvalTier.DIFFERENTIAL,
                    status=EvalStatus.FAILED,
                    passed=False,
                    critical=case.critical,
                    score=0.0,
                    expected=case.expected_normalized,
                    observed=None,
                    details=(f"{type(exc).__name__}: {exc}",),
                    source=f"external:{backend}",
                )
            )
    return results
