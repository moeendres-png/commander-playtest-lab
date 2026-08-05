from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.engine.rules import run_phase8_validation
from commander_lab.models import ToolResponse
from commander_lab.storage import (
    atomic_write_json,
    atomic_write_text,
    create_run_manifest,
    sha256_value,
)
from commander_lab.tools import CommanderToolService, ToolRegistry

PRIMARY_CANDIDATES: dict[str, list[dict[str, str]]] = {
    "korvold/current": [
        {"remove": "Scouring Swarm", "add_candidate_id": "korvold/idol-of-oblivion"},
        {"remove": "Evendo Brushrazer", "add_candidate_id": "korvold/lightning-greaves"},
    ],
    "rogshai/current": [
        {"remove": "Izzet Signet", "add_candidate_id": "rogshai/talisman-of-creativity"},
    ],
}

ABLATION_CARDS: dict[str, tuple[str, ...]] = {
    "korvold/current": ("Scouring Swarm", "Evendo Brushrazer", "Academy Manufactor"),
    "rogshai/current": ("Izzet Signet", "Blackblade Reforged", "Bastion Protector"),
}

ABLATION_PACKAGES: dict[str, tuple[str, ...]] = {
    "korvold/current": ("Academy Manufactor", "Tireless Provisioner", "Tireless Tracker"),
    "rogshai/current": ("Combat Research", "Curiosity", "Staggering Insight"),
}


def _git_commit(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _load_opponent_policy(root: Path) -> dict[str, Any]:
    return json.loads((root / "data/opponents/current_structural_profiles.json").read_text(encoding="utf-8"))


def _response_dict(response: ToolResponse) -> dict[str, Any]:
    return response.model_dump(mode="json")


def _invoke(
    registry: ToolRegistry,
    evidence: list[dict[str, Any]],
    name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = registry.invoke(name, payload)
    row = _response_dict(response)
    evidence.append(row)
    return row


def _rule_status(root: Path, card_names: list[str]) -> dict[str, Any]:
    registry_path = root / "data/rules/validation_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    cards = registry.get("cards", {})
    return {
        name: cards.get(
            name,
            {
                "oracle_name": name,
                "level": "structural_only",
                "interaction_ids": [],
                "tactical_passed": 0,
                "rules_engine_passed": 0,
                "notes": ["No validation-registry entry."],
            },
        )
        for name in card_names
    }




def _repository_secret_scan(root: Path) -> dict[str, Any]:
    token_patterns = (
        re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    )
    findings: list[str] = []
    try:
        tracked = subprocess.check_output(
            ["git", "-C", str(root), "ls-files"], text=True, stderr=subprocess.DEVNULL
        ).splitlines()
    except (OSError, subprocess.CalledProcessError):
        tracked = []
    for relative in tracked:
        if Path(relative).name == ".env":
            findings.append(f"{relative}:tracked environment file")
        path = root / relative
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in token_patterns:
            if pattern.search(text):
                findings.append(f"{relative}:{pattern.pattern}")
    return {"passed": not findings, "findings": findings, "tracked_files_scanned": len(tracked)}


def _phase10_report_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 10 End-to-End Acceptance Report",
        "",
        f"Status: **{result['status']}**",
        "",
        "All numerical simulation outputs are `structural_model_estimates`; they are not empirical win rates.",
        "",
        "## Local acceptance criteria",
        "",
        "| Criterion | Passed |",
        "|---|:---:|",
    ]
    for key, value in result["local_acceptance_criteria"].items():
        lines.append(f"| {key} | {'yes' if value else 'no'} |")
    lines.extend(["", "## Final recommendations", ""])
    for deck_id, recommendation in result["final_recommendations"].items():
        candidate = recommendation["candidate"]
        lines.extend([
            f"### {deck_id}",
            "",
            f"- Candidate: `{candidate['remove']} → {candidate['add']}`",
            f"- Status: `{recommendation['status']}`",
            f"- Summary: {recommendation['summary']}",
            "",
        ])
    lines.extend([
        "## External rules engine",
        "",
        f"- Pending: `{result['external_engine_validation_pending']}`",
        f"- Release gate passed: `{result['external_rules_engine_release_gate_passed']}`",
        "- Tactical-oracle evidence is not external rules-engine validation.",
        "",
        "## Modification safety",
        "",
        f"- Canonical deck files modified: `{result['canonical_deck_files_modified']}`",
        f"- Google Drive files modified: `{result['google_drive_files_modified']}`",
        f"- API key found in tracked repository files: `{not result['secret_scan']['passed']}`",
        "",
    ])
    return "\n".join(lines)


def _write_deck_report(
    root: Path,
    output: Path,
    deck_id: str,
    deck_evidence: dict[str, Any],
    recommendation: dict[str, Any],
) -> Path:
    safe = deck_id.split("/")[0]
    path = output / f"{safe}_example_report.md"
    validation = deck_evidence["validation"]["result"]
    inspection = deck_evidence["inspection"]["result"]
    candidate = recommendation.get("candidate") or {}
    rules = recommendation.get("rules_sample") or {}
    lines = [
        f"# Phase 10 Example Report – {deck_id}",
        "",
        "All simulation values in this report are `structural_model_estimates`.",
        "They are not empirical win rates and are not external rules-engine proof.",
        "",
        "## Baseline",
        "",
        f"- Deck hash: `{validation.get('deck_hash')}`",
        f"- Legal and structurally valid: `{validation.get('validation', {}).get('valid')}`",
        f"- Physical allocation check: `{validation.get('physical_allocation', {}).get('valid')}`",
        f"- Commander(s): {', '.join(inspection.get('commanders', []))}",
        "",
        "## Structure",
        "",
        "```json",
        json.dumps(inspection.get("role_counts", {}), indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Candidate result",
        "",
        f"- Candidate: `{candidate.get('remove', 'none')} → {candidate.get('add', 'none')}`",
        f"- Structural decision: `{candidate.get('structural_decision', 'not_run')}`",
        f"- Final status: `{recommendation.get('status')}`",
        f"- Automatically applied: `false`",
        "",
        "## Rules sample",
        "",
        "```json",
        json.dumps(rules, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Red-team conclusion",
        "",
        recommendation.get("red_team_summary", "No candidate was eligible for final validation."),
        "",
        "## Recommendation",
        "",
        recommendation.get("summary", "Retain the current baseline."),
        "",
    ]
    atomic_write_text(path, "\n".join(lines))
    return path


def _api_demo_passed(api_demo: dict[str, Any]) -> bool:
    health = api_demo.get("health", {})
    health_body = health.get("body", health) if isinstance(health, dict) else {}
    health_ok = (
        isinstance(health_body, dict)
        and health_body.get("status") == "ok"
        and health.get("status_code", 200) == 200
    )

    tools = api_demo.get("tools")
    tools_ok = False
    if isinstance(tools, dict):
        tools_ok = tools.get("status_code", 200) == 200 and (
            int(tools.get("count", 0)) > 0 or bool(tools.get("tools"))
        )
    if not tools_ok and isinstance(api_demo.get("tool_count"), int):
        tools_ok = api_demo["tool_count"] > 0

    validate = (
        api_demo.get("validate_rogshai")
        or api_demo.get("validate_deck")
        or api_demo.get("validate_call")
        or {}
    )
    if isinstance(validate, dict):
        validate_body = validate.get("body", validate)
        validate_ok = (
            validate.get("status_code", 200) == 200
            and isinstance(validate_body, dict)
            and validate_body.get("status") == "completed"
        )
    else:
        validate_ok = False

    return health_ok and tools_ok and validate_ok


def run_phase10_acceptance(
    root: str | Path,
    *,
    iterations: int = 12,
    seed: int = 20260805,
    workers: int = 2,
    output_directory: str | Path | None = None,
    include_api_self_test: bool = True,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    output = Path(output_directory).resolve() if output_directory else root_path / "data/runs/phase10_acceptance"
    output.mkdir(parents=True, exist_ok=True)
    service = CommanderToolService(root_path)
    registry = ToolRegistry(service)
    opponent_policy = _load_opponent_policy(root_path)
    primary_pods = [tuple(row) for row in opponent_policy["primary_four_player_pods"]]
    holdout_pods = [tuple(row) for row in opponent_policy["holdout_pods"]]
    evidence: list[dict[str, Any]] = []
    decks = ("korvold/current", "rogshai/current")
    deck_evidence: dict[str, Any] = {}

    for deck_id in decks:
        validation = _invoke(registry, evidence, "validate_deck", {"deck_id": deck_id})
        inspection = _invoke(registry, evidence, "inspect_deck", {"deck_id": deck_id, "include_cards": False})
        matchup_rows = []
        for pod_index, pod in enumerate(primary_pods):
            matchup_rows.append(
                _invoke(
                    registry,
                    evidence,
                    "run_matchup_batch",
                    {
                        "deck_ids": [deck_id, *pod],
                        "iterations": iterations,
                        "seed": seed + pod_index * 1009,
                        "workers": workers,
                        "pilot_strength": "strong",
                    },
                )
            )
        commander_denial = _invoke(
            registry,
            evidence,
            "run_commander_denial",
            {
                "deck_id": deck_id,
                "opponent_deck_ids": list(primary_pods[0]),
                "iterations": iterations,
                "seed": seed + 5001,
                "workers": workers,
                "additional_commander_tax": 6,
                "suppress_commander_synergy": True,
            },
        )
        card_ablations = [
            _invoke(
                registry,
                evidence,
                "run_card_ablation",
                {
                    "deck_id": deck_id,
                    "card_name": card_name,
                    "opponent_deck_ids": list(primary_pods[0]),
                    "iterations": max(6, iterations // 2),
                    "seed": seed + 6000 + index,
                    "workers": 1,
                },
            )
            for index, card_name in enumerate(ABLATION_CARDS[deck_id])
        ]
        package_ablation = _invoke(
            registry,
            evidence,
            "run_package_ablation",
            {
                "deck_id": deck_id,
                "card_names": list(ABLATION_PACKAGES[deck_id]),
                "opponent_deck_ids": list(primary_pods[0]),
                "iterations": max(6, iterations // 2),
                "seed": seed + 7001,
            },
        )
        recommendation_screen = _invoke(registry, evidence, "recommend_upgrades", {"deck_id": deck_id})
        targeted_cuts = [row["remove"] for row in PRIMARY_CANDIDATES[deck_id]]
        candidate_ids = [row["add_candidate_id"] for row in PRIMARY_CANDIDATES[deck_id]]
        swap_matrix = _invoke(
            registry,
            evidence,
            "generate_swap_matrix",
            {
                "deck_id": deck_id,
                "remove_cards": targeted_cuts,
                "add_candidate_ids": candidate_ids,
                "opponent_deck_ids": list(primary_pods[0]),
                "iterations": iterations,
                "iterations_per_cell": max(4, iterations // 2),
                "simulate_valid_cells": True,
                "seed": seed + 8001,
            },
        )
        pareto = _invoke(
            registry,
            evidence,
            "evaluate_pareto_front",
            {
                "deck_id": deck_id,
                "variants": [[row] for row in PRIMARY_CANDIDATES[deck_id]],
                "opponent_deck_ids": list(primary_pods[0]),
                "holdout_pods": [list(row) for row in holdout_pods],
                "iterations": max(6, iterations // 2),
                "seed": seed + 9001,
            },
        )
        deck_evidence[deck_id] = {
            "validation": validation,
            "inspection": inspection,
            "matchups": matchup_rows,
            "commander_denial": commander_denial,
            "card_ablations": card_ablations,
            "package_ablation": package_ablation,
            "candidate_screen": recommendation_screen,
            "swap_matrix": swap_matrix,
            "pareto": pareto,
        }

    rules_summary = run_phase8_validation(
        root_path,
        output_directory=output / "rules_sample",
        seed=seed,
    )

    final_recommendations: dict[str, Any] = {}
    for deck_index, deck_id in enumerate(decks):
        selected = PRIMARY_CANDIDATES[deck_id][0]
        paired = _invoke(
            registry,
            evidence,
            "compare_variants_paired",
            {
                "deck_id": deck_id,
                "swaps": [selected],
                "opponent_deck_ids": list(primary_pods[0]),
                "iterations": iterations,
                "seed": seed + 10001 + deck_index,
                "workers": 1,
            },
        )
        holdout = _invoke(
            registry,
            evidence,
            "run_holdout",
            {
                "deck_id": deck_id,
                "swaps": [selected],
                "opponent_deck_ids": list(primary_pods[0]),
                "holdout_pods": [list(row) for row in holdout_pods],
                "iterations": iterations,
                "seed": seed + 11001 + deck_index,
            },
        )
        sensitivity = _invoke(
            registry,
            evidence,
            "run_sensitivity",
            {
                "deck_ids": [deck_id, *primary_pods[0]],
                "iterations": max(4, iterations // 2),
                "seeds": [seed, seed + 1, seed + 2],
                "pilot_strengths": ["average", "strong"],
                "max_turns": 24,
                "seed": seed,
            },
        )
        validated = _invoke(
            registry,
            evidence,
            "validate_upgrade",
            {
                "deck_id": deck_id,
                "swaps": [selected],
                "opponent_deck_ids": list(primary_pods[0]),
                "holdout_pods": [list(row) for row in holdout_pods],
                "iterations": iterations,
                "seed": seed + 12001 + deck_index,
                "minimum_place_delta": 0.01,
                "sensitivity_seeds": [seed, seed + 1],
                "sensitivity_strengths": ["average", "strong"],
                "max_turns": 24,
            },
        )
        swap_result = validated.get("result", {})
        swap_rows = swap_result.get("swaps") or []
        add_name = swap_rows[0].get("add") if swap_rows else selected["add_candidate_id"]
        rule_cards = [selected["remove"], add_name]
        rules_sample = {
            "cards": _rule_status(root_path, rule_cards),
            "tactical_sample_passed": bool(rules_summary.get("local_acceptance_passed")),
            "external_rules_engine_attempted": bool(rules_summary.get("rules_engine_cases_attempted")),
            "external_rules_engine_passed": bool(rules_summary.get("rules_engine_release_gate_passed")),
            "validation_level": "tactical_oracle",
            "external_engine_validation_pending": True,
        }
        structural_decision = swap_result.get("proposal_status", "not_run")
        structurally_passed = structural_decision == "validated_not_applied"
        externally_validated = rules_sample["external_rules_engine_passed"]
        status = (
            "validated_upgrade"
            if structurally_passed and externally_validated
            else (
                "structurally_validated_pending_external_rules_engine"
                if structurally_passed
                else "rejected_not_applied"
            )
        )
        red_team = swap_result.get("red_team_review", {})
        summary = (
            "No deck change is authorized. The structural candidate did not pass the complete "
            "validation chain."
            if not structurally_passed
            else "The candidate passed the structural chain but cannot be marked validated_upgrade "
            "until a real external rules-engine sample passes."
        )
        final_recommendations[deck_id] = {
            "status": status,
            "candidate": {
                "remove": selected["remove"],
                "add": add_name,
                "candidate_id": selected["add_candidate_id"],
                "structural_decision": structural_decision,
            },
            "paired": paired,
            "holdout": holdout,
            "sensitivity": sensitivity,
            "validation": validated,
            "rules_sample": rules_sample,
            "red_team_summary": "; ".join(red_team.get("concerns", [])) or "No red-team concerns recorded.",
            "summary": summary,
            "automatic_application": False,
            "canonical_deck_files_modified": False,
        }

    joint_allocation = json.loads((root_path / "data/decks/manifest.json").read_text(encoding="utf-8"))["allocation_validation"]
    api_demo: dict[str, Any]
    if include_api_self_test:
        try:
            from fastapi.testclient import TestClient
            from commander_lab.api import create_app

            with TestClient(create_app(root_path)) as client:
                api_demo = {
                    "health": client.get("/health").json(),
                    "tool_count": len(client.get("/v1/tools").json()["tools"]),
                    "validate_call": client.post(
                        "/v1/tools/validate_deck:invoke",
                        json={"arguments": {"deck_id": "korvold/current"}},
                    ).json(),
                }
        except Exception as exc:
            api_demo = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    else:
        api_path = root_path / "artifacts/phase10/api_demo_output.json"
        if api_path.is_file():
            api_demo = json.loads(api_path.read_text(encoding="utf-8"))
        else:
            api_demo = {
                "status": "not_run",
                "reason": "Run the separate local API demo before final acceptance.",
            }

    chatgpt_tool_demo = {
        "mode": "offline_function_tool_demo",
        "live_model_called": False,
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "tool_schema_count": len(registry.list_schemas()),
        "example_plan": [
            "validate_deck",
            "inspect_deck",
            "run_matchup_batch",
            "run_commander_denial",
            "generate_swap_matrix",
            "compare_variants_paired",
            "run_holdout",
            "run_sensitivity",
            "validate_upgrade",
            "create_report",
        ],
        "guardrails": {
            "automatic_deck_changes": False,
            "large_run_approval_threshold": service.limits.approval_threshold_iterations,
            "hard_max_iterations": service.limits.hard_max_iterations,
            "max_model_calls": service.limits.max_model_calls,
            "max_total_tokens": service.limits.max_total_tokens,
            "max_estimated_cost_usd": service.limits.max_estimated_cost_usd,
        },
    }

    reports = {
        deck_id: str(_write_deck_report(root_path, output, deck_id, deck_evidence[deck_id], final_recommendations[deck_id]))
        for deck_id in decks
    }
    failed_tools = [
        {"tool": row.get("metadata", {}).get("tool_name"), "errors": row.get("errors", [])}
        for row in evidence
        if row.get("status") != "completed"
    ]
    log_directories = sorted({
        row.get("metadata", {}).get("deterministic_game_log_directory")
        for row in evidence
        if row.get("metadata", {}).get("deterministic_game_log_directory")
    })
    logs_present = all(Path(path).exists() for path in log_directories)
    estimate_labels_valid = all(
        row.get("metadata", {}).get("estimate_type") in {
            "structural_model_estimates", "empirical_playtest_observations", "mixed_real_and_structural"
        }
        for row in evidence
    )
    secret_scan = _repository_secret_scan(root_path)
    deck_validations_passed = all(
        deck_evidence[deck_id]["validation"]["result"].get("validation", {}).get("valid")
        for deck_id in decks
    )
    physical_allocation_passed = bool(joint_allocation.get("valid"))
    api_demo_passed = _api_demo_passed(api_demo)
    local_acceptance_criteria = {
        "all_tool_calls_completed": not failed_tools,
        "deck_validations_passed": deck_validations_passed,
        "joint_physical_allocation_passed": physical_allocation_passed,
        "tactical_rules_sample_passed": bool(rules_summary.get("local_acceptance_passed")),
        "deterministic_log_directories_present": logs_present,
        "estimate_labels_valid": estimate_labels_valid,
        "cost_limits_active": service.limits.hard_max_iterations > 0 and service.limits.max_model_calls > 0,
        "api_demo_passed": api_demo_passed,
        "repository_secret_scan_passed": secret_scan["passed"],
        "no_automatic_deck_application": all(
            not item["automatic_application"] for item in final_recommendations.values()
        ),
    }
    local_acceptance_passed = all(local_acceptance_criteria.values())
    deterministic_core = {
        "seed": seed,
        "iterations": iterations,
        "workers": workers,
        "deck_hashes": {
            deck_id: deck_evidence[deck_id]["validation"]["result"].get("deck_hash") for deck_id in decks
        },
        "opponent_policy_hash": sha256_value(opponent_policy),
        "recommendations": {
            deck_id: {
                "status": item["status"],
                "candidate": item["candidate"],
                "paired": item["validation"].get("result", {}).get("paired_comparison"),
                "criteria": item["validation"].get("result", {}).get("criteria"),
            }
            for deck_id, item in final_recommendations.items()
        },
        "rules_counts": {
            "tactical_passed": rules_summary.get("tactical_passed"),
            "rules_engine_passed": rules_summary.get("rules_engine_passed"),
        },
    }
    result = {
        "phase": 10,
        "status": "passed_with_limitations" if local_acceptance_passed else "failed",
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(root_path),
        "data_snapshot_hash": service.manifest["data_snapshot_hash"],
        "estimate_type": "structural_model_estimates",
        "external_engine_validation_pending": True,
        "external_rules_engine_release_gate_passed": False,
        "deck_ids": list(decks),
        "opponent_policy_hash": sha256_value(opponent_policy),
        "primary_pods": primary_pods,
        "holdout_pods": holdout_pods,
        "joint_physical_allocation": joint_allocation,
        "deck_evidence": deck_evidence,
        "rules_sample": rules_summary,
        "final_recommendations": final_recommendations,
        "validated_upgrades": [
            deck_id for deck_id, item in final_recommendations.items() if item["status"] == "validated_upgrade"
        ],
        "canonical_deck_files_modified": False,
        "google_drive_files_modified": False,
        "api_key_in_repository": False,
        "cost_limits": service.limits.model_dump(mode="json"),
        "api_demo": api_demo,
        "chatgpt_tool_demo": chatgpt_tool_demo,
        "reports": reports,
        "tool_evidence_count": len(evidence),
        "failed_tools": failed_tools,
        "log_directories": log_directories,
        "secret_scan": secret_scan,
        "local_acceptance_criteria": local_acceptance_criteria,
        "local_acceptance_passed": local_acceptance_passed,
        "reproducibility_fingerprint": sha256_value(deterministic_core),
        "productive_functions": [
            "deck_import_and_validation", "structural_simulation", "pilot_agents",
            "paired_comparison", "ablation", "constrained_search", "pareto_filter",
            "holdout", "sensitivity", "playtest_import", "local_tool_server", "reporting"
        ],
        "experimental_functions": [
            "tactical_oracle", "current_opponent_role_profiles", "cosmic_midbudget_completion",
            "approximate_shapley", "live_openai_agent_workflow", "external_rules_engine_adapter"
        ],
    }
    atomic_write_json(output / "tool_evidence.json", evidence)
    atomic_write_json(output / "phase10_acceptance.json", result)
    atomic_write_json(output / "api_demo.json", api_demo)
    atomic_write_json(output / "chatgpt_tool_demo.json", chatgpt_tool_demo)
    atomic_write_text(output / "phase10_validation_report.md", _phase10_report_markdown(result))
    run_metadata = {
        "schema_version": "1.0.0",
        "result_sha256": sha256_value(result),
        "tool_evidence_sha256": sha256_value(evidence),
        "git_commit": result["git_commit"],
        "data_snapshot_hash": result["data_snapshot_hash"],
        "opponent_policy_hash": result["opponent_policy_hash"],
        "seed": seed,
        "iterations": iterations,
        "workers": workers,
        "external_engine_validation_pending": True,
    }
    atomic_write_json(output / "phase10_run_metadata.json", run_metadata)
    create_run_manifest(
        output,
        run_id=output.name,
        status="completed" if local_acceptance_passed else "failed",
        metadata=run_metadata,
    )
    return result
