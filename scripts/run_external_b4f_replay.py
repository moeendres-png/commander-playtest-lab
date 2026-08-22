from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from commander_lab.evals import configured_backend_command, load_differential_cases

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/evals/differential/rules_cases.json"
OUTPUT = ROOT / "artifacts/external-engine/XMAGE_B4F_PHASE6_REPLAY.json"
SCENARIO_MODE = "provider_state_injection_v1"
REPLAY_ROUNDS = 3


def _sha256_json(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _invoke_case(
    *,
    command_template: tuple[str, ...],
    case_id: str,
    description: str,
    input_state: dict[str, object],
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="commander-lab-b4f-replay-") as temp_dir:
        input_path = Path(temp_dir) / "input.json"
        output_path = Path(temp_dir) / "output.json"
        input_path.write_text(
            json.dumps(
                {
                    "case_id": case_id,
                    "description": description,
                    "input_state": input_state,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
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
            timeout=120.0,
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(
                f"B4-F replay provider process failed for {case_id}: "
                f"rc={completed.returncode}, stderr={completed.stderr.strip()}"
            )
        if not output_path.exists():
            raise SystemExit(f"B4-F replay provider produced no output for {case_id}")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit(f"B4-F replay output is not an object for {case_id}")
        return payload


def main() -> None:
    command = configured_backend_command("xmage")
    if command is None:
        raise SystemExit("B4-F replay requires COMMANDER_LAB_XMAGE_DIFFERENTIAL_CMD")

    xmage_commit = os.getenv("XMAGE_COMMIT", "").strip()
    if len(xmage_commit) != 40 or any(char not in "0123456789abcdef" for char in xmage_commit):
        raise SystemExit("B4-F replay requires a full lowercase XMAGE_COMMIT pin")

    cases = load_differential_cases(FIXTURES)
    case_evidence: list[dict[str, object]] = []
    for case in cases:
        observations: list[dict[str, object]] = []
        hashes: list[str] = []
        for round_number in range(1, REPLAY_ROUNDS + 1):
            payload = _invoke_case(
                command_template=command,
                case_id=case.case_id,
                description=case.description,
                input_state=dict(case.input_state),
            )
            if payload.get("provider") != "xmage":
                raise SystemExit(f"B4-F replay provider mismatch for {case.case_id}")
            if payload.get("provider_commit") != xmage_commit:
                raise SystemExit(f"B4-F replay provider pin mismatch for {case.case_id}")
            if payload.get("scenario_mode") != SCENARIO_MODE:
                raise SystemExit(f"B4-F replay scenario contract mismatch for {case.case_id}")
            normalized = payload.get("normalized_output")
            if not isinstance(normalized, dict):
                raise SystemExit(f"B4-F replay normalized output missing for {case.case_id}")
            mismatches = {
                key: {
                    "expected": case.expected_normalized.get(key),
                    "observed": normalized.get(key),
                }
                for key in case.comparison_keys
                if case.expected_normalized.get(key) != normalized.get(key)
            }
            if mismatches:
                raise SystemExit(
                    f"B4-F replay fixture mismatch for {case.case_id}: {mismatches}"
                )
            stable_payload = {
                "backend_version": payload.get("backend_version"),
                "provider": payload.get("provider"),
                "provider_commit": payload.get("provider_commit"),
                "scenario_mode": payload.get("scenario_mode"),
                "normalized_output": normalized,
            }
            observation_hash = _sha256_json(stable_payload)
            hashes.append(observation_hash)
            observations.append(
                {
                    "round": round_number,
                    "observation_sha256": observation_hash,
                    "normalized_output": normalized,
                }
            )
        if len(set(hashes)) != 1:
            raise SystemExit(
                f"B4-F replay is nondeterministic across fresh provider processes for {case.case_id}: {hashes}"
            )
        case_evidence.append(
            {
                "case_id": case.case_id,
                "critical": case.critical,
                "rounds": observations,
                "stable_observation_sha256": hashes[0],
                "deterministic_across_fresh_processes": True,
            }
        )

    evidence = {
        "schema_version": "1.0.0",
        "evidence_class": "external_rules_engine",
        "scope": "xmage_b4f_frozen_phase6_fixture_reconstruction_replay_4p",
        "provider": "xmage",
        "provider_commit": xmage_commit,
        "scenario_contract": SCENARIO_MODE,
        "replay_rounds_per_fixture": REPLAY_ROUNDS,
        "process_model": "fresh_xmage_jvm_per_observation",
        "full_seeded_game_replay_claimed": False,
        "seed_controlled": False,
        "all_fixtures_deterministic": True,
        "cases": case_evidence,
        "status": "passed",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
