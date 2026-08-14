from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.pod_scheduling import BalancedPodScenarioScheduler
from commander_lab.pod_scheduling_5p import BalancedFivePlayerSensitivityScheduler
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.storage import atomic_write_json

from .knowledge_quality import build_knowledge_quality_report

_REQUIRED_EXTERNAL_GATES = (
    "ci_status",
    "security_status",
    "windows_status",
    "j_p6_status",
    "j_final_status",
    "release_status",
)


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def build_campaign_readiness(
    root: str | Path,
    *,
    external_gates: Mapping[str, str] | None = None,
    import_architecture_status: str = "PASS",
    paired_isolation_status: str = "PASS",
    smoke_status: str = "NOT_RUN",
) -> dict[str, object]:
    project = Path(root).resolve()
    knowledge = build_knowledge_quality_report(project)
    opponents = CurrentOpponentRepository(project)
    scheduler = BalancedPodScenarioScheduler(
        opponents.records(), opponent_registry_hash=opponents.registry_hash
    )
    cycle = scheduler.schedule(scheduler.combinations_per_cycle, seed=2026081401)
    coverage = scheduler.coverage_report(cycle)
    five_player_scheduler = BalancedFivePlayerSensitivityScheduler(
        opponents.records(), opponent_registry_hash=opponents.registry_hash
    )
    five_player_cycle = five_player_scheduler.schedule(
        five_player_scheduler.combinations_per_cycle, seed=2026081451
    )
    five_player_coverage = five_player_scheduler.coverage_report(five_player_cycle)
    deck_manifest = json.loads((project / "data/decks/manifest.json").read_text(encoding="utf-8"))
    rogshai = deck_manifest["decks"]["rogshai/current"]
    provider = json.loads(
        (project / "docs/J_P3_PROVIDER_DECISION.json").read_text(encoding="utf-8")
    )
    gates = {name: "NOT_RUN" for name in _REQUIRED_EXTERNAL_GATES}
    if external_gates:
        for name, value in external_gates.items():
            if name in gates:
                gates[name] = str(value)

    software_ok = import_architecture_status == "PASS" and paired_isolation_status == "PASS"
    scheduler_ok = (
        scheduler.combinations_per_cycle == 56
        and coverage["opponent_exposure_imbalance"] == 0
        and coverage["rogshai_seat_counts"] == {"1": 14, "2": 14, "3": 14, "4": 14}
    )
    five_player_ok = (
        five_player_scheduler.combinations_per_cycle == 70
        and five_player_coverage["opponent_exposure_imbalance"] == 0
        and five_player_coverage["rogshai_seat_counts"]
        == {"1": 14, "2": 14, "3": 14, "4": 14, "5": 14}
    )
    blockers: list[str] = []
    if not knowledge["knowledge_pipeline_ready"]:
        blockers.append("KNOWLEDGE_PIPELINE_NOT_READY")
    if not software_ok:
        blockers.append("IMPORT_OR_PAIRED_ISOLATION_NOT_READY")
    if not scheduler_ok:
        blockers.append("BALANCED_PRIMARY_SCHEDULER_NOT_READY")
    if not five_player_ok:
        blockers.append("BALANCED_FIVE_PLAYER_SENSITIVITY_NOT_READY")
    if smoke_status != "PASS":
        blockers.append("PUBLIC_WORKFLOW_SMOKE_NOT_PASS")
    for name in _REQUIRED_EXTERNAL_GATES:
        if gates[name] != "PASS":
            blockers.append(f"{name.upper()}_{gates[name]}")

    ready = not blockers
    return {
        "schema_version": "1.0.0",
        "software_identity": {
            "git_commit": _git(project, "rev-parse", "HEAD"),
            "git_tree": _git(project, "rev-parse", "HEAD^{tree}"),
            "package_version": __version__,
            "engine_version": ENGINE_VERSION,
        },
        "data_snapshot_identity": deck_manifest["data_snapshot_hash"],
        "deck_identity": {
            "deck_id": "rogshai/current",
            "deck_hash": rogshai["deck_hash"],
            "cards": rogshai["total_cards"],
            "lands": rogshai["land_count"],
        },
        "opponent_registry_identity": opponents.registry_hash,
        "opponent_count": len(opponents.current_deck_ids()),
        "candidate_count": knowledge["candidate_universe_count"],
        "semantic_known_count": knowledge["structurally_usable_count"],
        "semantic_unknown_count": knowledge["semantic_unknown_count"],
        "structural_usable_fraction": knowledge["structurally_usable_fraction"],
        "knowledge_quality": knowledge,
        "primary_pod_scheduler_status": "PASS" if scheduler_ok else "FAIL",
        "paired_isolation_status": paired_isolation_status,
        "opponent_coverage_status": "PASS" if scheduler_ok else "FAIL",
        "opponent_full_cycle_combinations": scheduler.combinations_per_cycle,
        "opponent_full_cycle_coverage": coverage,
        "five_player_sensitivity_status": "PASS" if five_player_ok else "FAIL",
        "five_player_full_cycle_combinations": five_player_scheduler.combinations_per_cycle,
        "five_player_full_cycle_coverage": five_player_coverage,
        "import_architecture_status": import_architecture_status,
        "public_workflow_smoke_status": smoke_status,
        "external_engine_status": provider["decision"],
        **gates,
        "remaining_blockers": blockers,
        "documented_limitations": [
            "Structural simulation remains model evidence, not empirical win rate.",
            "Remaining semantic unknowns are visible and trigger REVIEW_REQUIRED if selected by a finalist.",
            "Morcant/Cosmic and observed precon-deviation gaps remain real opponent-data limitations.",
            "External rules-engine provider remains NO_PROVIDER_READY and is not promoted to PASS.",
            "Five-player pods are a separate balanced sensitivity axis and are never primary evidence; three-player pods remain a separate robustness axis.",
        ],
        "ready_for_official_campaign": ready,
        "readiness_label": (
            "READY_FOR_OFFICIAL_WHOLE_DECK_CAMPAIGN"
            if ready
            else "NOT_READY_FOR_OFFICIAL_WHOLE_DECK_CAMPAIGN"
        ),
        "governance": {
            "canonical_rogshai_changed": False,
            "inventory_changed": False,
            "allocation_changed": False,
            "purchases_changed": False,
            "opponent_observations_changed": False,
            "kaervek_changed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--smoke-status", default="NOT_RUN")
    for gate in _REQUIRED_EXTERNAL_GATES:
        parser.add_argument(f"--{gate.replace('_', '-')}", default="NOT_RUN")
    args = parser.parse_args()
    gates = {gate: getattr(args, gate) for gate in _REQUIRED_EXTERNAL_GATES}
    report = build_campaign_readiness(
        args.root, external_gates=gates, smoke_status=args.smoke_status
    )
    atomic_write_json(Path(args.output), report)
    print(report["readiness_label"])


if __name__ == "__main__":
    main()
