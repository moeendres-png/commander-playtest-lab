#!/usr/bin/env python3
"""Build the exact-main recovery PROVENANCE and CLOSEOUT documents.

The recovery bundle records what exact main *is* and what this run *observed*.
It must not carry a stale engine identity or an unproven runtime claim:

* the XMage pin is read from ``config/rules_engines.json`` (``primary_engine.commit``),
  the repository's sole machine-readable pin authority, never from a literal;
* design declarations are labelled as declarations (``declared_architecture``);
* facts this workflow run checked at this commit are listed with how they were
  checked (``observed_in_this_run``);
* runtime claims this run does not check (hidden-information scoping, one JVM
  per game, real-engine conformance) are ``NOT_BOUND``: a recovery bundle has no
  same-commit receipt for them, so it must not assert them.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PROVENANCE_SCHEMA = "exact-main-recovery-provenance-2.0.0"
CLOSEOUT_SCHEMA = "commander-lab-architecture-closeout-2.0.0"
NOT_BOUND = "NOT_BOUND"

# Runtime claims the full-game lane makes elsewhere. This workflow executes no
# full game, so it can only say it does not bind them.
UNBOUND_RUNTIME_CLAIMS = (
    "full_game_hidden_information_actor_scoped",
    "full_game_one_isolated_jvm_per_game",
    "full_game_real_engine_conformance",
)


class RecoveryPayloadError(ValueError):
    """The payload cannot be built truthfully; the workflow must fail."""


def current_xmage_pin(root: Path) -> str:
    """The current XMage pin from the repository's pin authority, fail closed."""
    path = root / "config" / "rules_engines.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RecoveryPayloadError(f"cannot read the pin authority {path}: {exc}") from exc
    commit = str(((document.get("primary_engine") or {}).get("commit")) or "")
    if not SHA_RE.match(commit):
        raise RecoveryPayloadError(
            f"primary_engine.commit in {path} is not a 40-hex commit: {commit!r}"
        )
    return commit


def _identity(commit: str, tree: str, version: str) -> None:
    for name, value in (("commit", commit), ("tree", tree)):
        if not SHA_RE.match(value):
            raise RecoveryPayloadError(f"{name} is not a 40-hex git object id: {value!r}")
    if not version.strip():
        raise RecoveryPayloadError("package version is empty")


def build_provenance(*, commit: str, tree: str, version: str, xmage_pin: str) -> dict[str, Any]:
    _identity(commit, tree, version)
    return {
        "schema_version": PROVENANCE_SCHEMA,
        "git_commit": commit,
        "git_tree": tree,
        "package_version": version,
        "xmage_pinned_commit": xmage_pin,
        "xmage_pin_source": "config/rules_engines.json#primary_engine.commit",
        "contract_versions": {
            "candidate_pipeline_runtime": "candidate-pipeline-1.0.0",
            "candidate_set_schema": "deck-candidate-set-1.0.0",
            "candidate_validation_report_schema": "candidate-validation-report-1.0.0",
            "simulation_queue_schema": "simulation-candidate-queue-1.0.0",
            "pre_simulation_invariant_report_schema": "pre-simulation-invariant-report-1.0.0",
            "future_xmage_scenario_contract": "future-xmage-scenario-contract-1.0.0",
            "xmage_full_game_lane": "xmage_full_game_external_pilots",
            "xmage_full_game_decision_protocol": "xmage-external-decision-protocol-1.0.0",
        },
        "declared_architecture": {
            "note": "design declarations of the architecture contract, not runtime evidence",
            "primary_decision_pod_size": 4,
            "xmage_rules_authority": True,
            "our_pilots_decision_authority": True,
            "structural_decision_authority": False,
            "tactical_decision_authority": False,
            "random_or_default_discretionary_fallback": False,
        },
        "run_facts": {
            "note": "what this recovery workflow itself does",
            "official_gameplay_evidence_consumed": False,
            "sealed_holdout_opened": False,
            "canonical_mutation_performed": False,
        },
    }


def build_closeout(
    *, commit: str, tree: str, version: str, focused_tests: list[str]
) -> dict[str, Any]:
    _identity(commit, tree, version)
    return {
        "schema_version": CLOSEOUT_SCHEMA,
        "final_main_commit": commit,
        "final_main_tree": tree,
        "package_version": version,
        "declared_architecture": {
            "note": "design declarations of the architecture contract, not runtime evidence",
            "pre_simulation_architecture_reset_complete": True,
            "external_candidate_set_supported": True,
            "hard_validation_only_before_gameplay": True,
            "pre_simulation_heuristic_elimination": False,
            "structural_decision_authority": False,
            "tactical_decision_authority": False,
            "full_xmage_lane": "xmage_full_game_external_pilots",
            "xmage_rules_authority": True,
            "our_pilots_decision_policy_authority": True,
            "full_game_primary_decision_pod_size": 4,
            "full_game_state_injection": False,
            "full_game_default_fallback": False,
        },
        "observed_in_this_run": {
            "note": "checked by this workflow at final_main_commit; a failure stops the run before this document exists",
            "focused_architecture_tests": {"status": "PASS", "commands": focused_tests},
            "recovery_bundle_clone": "checked after this document is written; see VALIDATION.txt",
        },
        "runtime_claims": {
            claim: {
                "status": NOT_BOUND,
                "reason": "this recovery run executes no full game and carries no same-commit "
                "receipt for this claim",
            }
            for claim in UNBOUND_RUNTIME_CLAIMS
        },
        "canonical_deck_changed": False,
        "inventory_changed": False,
        "allocation_changed": False,
        "purchase_changed": False,
        "opponent_truth_changed": False,
        "official_gameplay_evidence_consumed": False,
        "sealed_holdout_opened": False,
        "recovery_created": True,
        "drive_upload": "PENDING_EXTERNAL_READBACK",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--inner", type=Path, required=True, help="the recovery bundle's inner directory"
    )
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--focused-test",
        action="append",
        default=[],
        help="a focused test command this job ran and passed at --commit (repeatable)",
    )
    args = parser.parse_args(argv)
    pin = current_xmage_pin(args.root)
    provenance = build_provenance(
        commit=args.commit, tree=args.tree, version=args.version, xmage_pin=pin
    )
    closeout = build_closeout(
        commit=args.commit,
        tree=args.tree,
        version=args.version,
        focused_tests=list(args.focused_test),
    )
    args.inner.mkdir(parents=True, exist_ok=True)
    for name, document in (
        ("PROVENANCE.json", provenance),
        ("EXACT_MAIN_FINAL_CLOSEOUT.json", closeout),
    ):
        (args.inner / name).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
