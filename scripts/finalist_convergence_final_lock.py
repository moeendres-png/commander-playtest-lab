#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

REPO = "moeendres-png/commander-playtest-lab"
ROOT = Path(__file__).resolve().parents[1]
EXPECTATION_PATH = ROOT / "qualification/finalist_convergence/FINAL_TERMINAL_EXPECTATION.json"
OUT_DIR = ROOT / "qualification/finalist_convergence/final-lock-runtime"
OUT_PATH = OUT_DIR / "FINAL_TERMINAL_LOCK.json"


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def git_show(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def remote_head(branch: str) -> str:
    text = run("git", "ls-remote", "origin", f"refs/heads/{branch}")
    require(bool(text), f"missing remote branch {branch}")
    return text.split()[0]


def api_json(path: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "GITHUB_TOKEN is required for final runtime evidence lock")
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "commander-lab-finalist-lock",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"GitHub API {path} failed: {exc.code} {body}") from exc


def verify_run(run_id: int, expected_head: str, expected_conclusion: str = "success") -> dict:
    payload = api_json(f"/repos/{REPO}/actions/runs/{run_id}")
    require(payload.get("head_sha") == expected_head, f"run {run_id} head mismatch")
    require(payload.get("status") == "completed", f"run {run_id} not completed")
    require(payload.get("conclusion") == expected_conclusion, f"run {run_id} conclusion mismatch")
    return {
        "run_id": run_id,
        "name": payload.get("name"),
        "head_sha": payload.get("head_sha"),
        "status": payload.get("status"),
        "conclusion": payload.get("conclusion"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
    }


def exact_head_run_names(head_sha: str) -> list[str]:
    payload = api_json(f"/repos/{REPO}/actions/runs?head_sha={head_sha}&per_page=100")
    names = [str(item.get("name", "")) for item in payload.get("workflow_runs", [])]
    return sorted(set(names))


def main() -> int:
    expectation_bytes = EXPECTATION_PATH.read_bytes()
    expectation = json.loads(expectation_bytes)
    lock = expectation["source_lock"]

    branches = {
        "main": "main",
        "contract": "program/finalist-convergence-contract",
        "forge_finalist": "program/finalist-convergence-forge",
        "xmage_finalist": "program/finalist-convergence-xmage",
        "differential": "program/finalist-convergence-differential",
    }
    observed_heads = {key: remote_head(branch) for key, branch in branches.items()}
    for key, observed in observed_heads.items():
        require(observed == lock[key], f"source-lock drift for {key}: {observed} != {lock[key]}")

    subprocess.check_call(
        [
            "git", "fetch", "--no-tags", "origin",
            "+refs/heads/program/finalist-convergence-contract:refs/remotes/origin/finalist-contract-lock",
        ],
        cwd=ROOT,
    )
    require(
        run("git", "rev-parse", "refs/remotes/origin/finalist-contract-lock") == lock["contract"],
        "fetched contract commit mismatch",
    )
    contract_tree = run("git", "show", "-s", "--format=%T", lock["contract"])
    require(contract_tree == lock["contract_tree"], "contract tree mismatch")

    report_bytes = git_show(lock["contract"], "qualification/finalist_convergence/SEMANTIC_EXECUTABILITY_REPORT.json")
    union_bytes = git_show(lock["contract"], "qualification/finalist_convergence/KNOWN_PASS_UNION_50_v1_0_1.json")
    program_state_bytes = git_show(lock["contract"], "qualification/finalist_convergence/PROGRAM_STATE.json")
    report = json.loads(report_bytes)
    union = json.loads(union_bytes)
    program_state = json.loads(program_state_bytes)

    frozen = expectation["frozen_contract"]
    require(report["input_bundle_digest"] == frozen["bundle_digest"], "bundle digest mismatch")
    require(report["record_count"] == frozen["record_count"] == 135, "135 denominator mismatch")
    counts = Counter(item["status"] for item in report["records"])
    require(counts["PASS"] == frozen["semantic_executable"] == 72, "semantic PASS denominator mismatch")
    require(counts["SEMANTIC_EXECUTABILITY_DEFECT"] == frozen["semantic_defects"] == 63, "semantic defect denominator mismatch")
    require(report.get("terminal_result_count") == 135, "semantic report not terminally accounting all records")
    require(report.get("unique_fixture_ids") == 135, "semantic report fixture IDs not unique")

    status_by_id = {item["fixture_id"]: item["status"] for item in report["records"]}
    union_ids = union["fixture_ids"]
    require(union["fixture_count"] == len(union_ids) == frozen["known_pass_union_count"] == 50, "Union-50 size mismatch")
    union_pass = sorted(fid for fid in union_ids if status_by_id[fid] == "PASS")
    union_defects = sorted(fid for fid in union_ids if status_by_id[fid] != "PASS")
    require(len(union_pass) == frozen["expected_union_semantic_executable"] == 42, "Union-50 executable count drift")
    require(len(union_defects) == frozen["expected_union_semantic_defects"] == 8, "Union-50 defect count drift")

    card_ids = [f"CARD_{index:02d}" for index in range(1, 30)]
    card_pass = sorted(fid for fid in card_ids if status_by_id[fid] == "PASS")
    card_defects = sorted(fid for fid in card_ids if status_by_id[fid] != "PASS")
    require(card_pass == sorted(frozen["expected_v101_executable_card_records"]), f"v1.0.1 card executable set drift: {card_pass}")
    require(len(card_defects) == 27, "v1.0.1 card defect count drift")

    replay_ids = expectation["required_remaining_gate_terminal_results"]["replay_rng_v101"]["record_ids"]
    require(all(status_by_id[fid] == "PASS" for fid in replay_ids), "replay records must be contract-executable before provider blame")
    require(status_by_id["CARD_02"] == "PASS", "CARD_02 must be contract-executable before provider blame")

    closed = expectation["closed_runtime_evidence"]
    verified_runs = {
        "forge_micro_replacement": verify_run(closed["micro_replacement"]["forge_run"], lock["forge_finalist"]),
        "xmage_micro_replacement": verify_run(closed["micro_replacement"]["xmage_run"], "02481165abb2e409ec0cfe278a591d2478d42e5c"),
        "forge_ws05": verify_run(closed["ws05_mp_combat_4"]["forge_run"], lock["forge_finalist"]),
        "xmage_ws05": verify_run(closed["ws05_mp_combat_4"]["xmage_run"], lock["xmage_finalist"]),
        "ws05_differential": verify_run(closed["ws05_mp_combat_4"]["differential_run"], lock["differential"]),
    }

    forge_head_run_names = exact_head_run_names(lock["forge_finalist"])
    xmage_head_run_names = exact_head_run_names(lock["xmage_finalist"])
    forbidden_runtime_markers = ("replay", "rng", "card_02", "card02", "union-50", "union 50", "current-72", "actual-card", "actual card")
    for provider, names in (("forge", forge_head_run_names), ("xmage", xmage_head_run_names)):
        matching = [name for name in names if any(marker in name.lower() for marker in forbidden_runtime_markers)]
        require(not matching, f"Expectation says corrected remaining gates are NOT_RUN, but current-head workflow names suggest otherwise for {provider}: {matching}")

    af = expectation["architecture_freeze"]
    for gate in ("AF00", "AF01", "AF02", "AF03", "AF11"):
        require(af[gate]["forge"] == "PASS" and af[gate]["xmage"] == "PASS", f"{gate} baseline changed")
    for gate in ("AF04", "AF05", "AF06", "AF07", "AF08", "AF09"):
        require(af[gate]["forge"] == "FAIL" and af[gate]["xmage"] == "FAIL", f"{gate} must remain fail-closed")
    require(expectation["terminal_abc"]["definition_status"] == "CONTRACT_DEFECT", "Terminal A/B/C definitions must not be invented")
    require(expectation["final_verdict"]["architecture_freeze"] == "NO", "architecture freeze must remain NO")
    require(expectation["final_verdict"]["production_provider"] == "NONE_QUALIFIED", "production provider must remain none")

    result = {
        "schema_version": "commander-lab.finalist-convergence-final-lock/1.0.0",
        "lock_status": "PASS",
        "meaning": "Evidence accounting and terminal classifications are internally consistent. This is not a production-qualification PASS.",
        "program_status": expectation["program_status"],
        "current_commit": run("git", "rev-parse", "HEAD"),
        "expectation_sha256": sha256(expectation_bytes),
        "source_heads": observed_heads,
        "contract_tree": contract_tree,
        "contract_artifacts": {
            "semantic_executability_report_sha256": sha256(report_bytes),
            "known_pass_union_50_sha256": sha256(union_bytes),
            "program_state_sha256": sha256(program_state_bytes),
            "bundle_digest": report["input_bundle_digest"],
            "program_state_contract_commit": program_state.get("contract_commit") or program_state.get("contract_head") or lock["contract"],
        },
        "denominators": {
            "all_records": 135,
            "semantic_executable": 72,
            "semantic_defects": 63,
            "union_50_total": 50,
            "union_50_semantic_executable": len(union_pass),
            "union_50_semantic_defects": len(union_defects),
            "union_50_defect_ids": union_defects,
            "actual_card_records_total": 29,
            "v101_actual_card_semantic_executable": len(card_pass),
            "v101_actual_card_executable_ids": card_pass,
            "v101_actual_card_semantic_defects": len(card_defects),
        },
        "verified_runtime_runs": verified_runs,
        "current_head_workflow_names": {
            "forge": forge_head_run_names,
            "xmage": xmage_head_run_names,
        },
        "remaining_gates": expectation["required_remaining_gate_terminal_results"],
        "risk_audit": expectation["risk_audit"],
        "architecture_freeze": {
            **af,
            "AF10": {"forge": "PASS", "xmage": "PASS"},
            "verdict": "NO",
        },
        "terminal_abc": expectation["terminal_abc"],
        "final_verdict": expectation["final_verdict"],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "lock_status": result["lock_status"],
        "program_status": result["program_status"],
        "union_50": [len(union_pass), len(union_defects)],
        "current_72": counts["PASS"],
        "card_29_v101_executable": card_pass,
        "architecture_freeze": result["final_verdict"]["architecture_freeze"],
        "production_provider": result["final_verdict"]["production_provider"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FINAL_TERMINAL_LOCK_FAILED: {exc}", file=sys.stderr)
        raise
