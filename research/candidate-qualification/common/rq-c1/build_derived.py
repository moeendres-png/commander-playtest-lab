#!/usr/bin/env python3
"""RQ-C1 derived-artifact builder. Reads scenarios/*.json, writes manifest + matrices.

Deterministic: all outputs sorted by scenario_id. No candidate execution.
"""
import csv
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCEN_DIR = BASE / "scenarios"


def load_scenarios():
    out = []
    for f in sorted(SCEN_DIR.glob("RQ-C1-*.json")):
        out.append(json.loads(f.read_text()))
    out.sort(key=lambda d: d["scenario_id"])
    return out


def main():
    scenarios = load_scenarios()

    manifest = {
        "schema": "rq-c1.scenario-manifest.v1",
        "workstream": "RQ-C1-CANDIDATE-NEUTRAL-ACTUAL-CARD-ARCHITECTURE-REVERSER-CORPUS",
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }
    (BASE / "RQ_C1_SCENARIO_MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=False) + "\n"
    )

    with open(BASE / "RQ_C1_SCENARIO_MANIFEST.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "scenario_id", "title", "status", "player_count", "actual_cards",
            "reverser_axes", "decision_kinds", "decision_criticality",
            "information_gain", "execution_complexity", "first_wave",
            "native_setup_boundary", "authority_status", "commander_relevance",
        ])
        for s in scenarios:
            w.writerow([
                s["scenario_id"], s["title"], s["status"], s["player_count"],
                "|".join(c["name"] for c in s["actual_cards"]),
                "|".join(s["architecture_reverser_axes"]),
                "|".join(s["decision_kinds"]),
                s["decision_criticality"], s["information_gain"],
                s["execution_complexity"], str(s["first_wave"]).upper(),
                s["native_setup_boundary"], s["authority_status"],
                str(s["commander_relevance"]).upper(),
            ])

    all_kinds = sorted({k for s in scenarios for k in s["decision_kinds"]})
    with open(BASE / "RQ_C1_DECISION_SURFACE_MATRIX.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario_id"] + all_kinds)
        for s in scenarios:
            have = set(s["decision_kinds"])
            w.writerow([s["scenario_id"]] + ["1" if k in have else "0" for k in all_kinds])

    all_axes = sorted({a for s in scenarios for a in s["architecture_reverser_axes"]})
    with open(BASE / "RQ_C1_RULES_AXIS_MATRIX.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario_id"] + all_axes)
        for s in scenarios:
            have = set(s["architecture_reverser_axes"])
            w.writerow([s["scenario_id"]] + ["1" if a in have else "0" for a in all_axes])

    hidden = {
        "schema": "rq-c1.hidden-info-expectations.v1",
        "note": "Per-scenario principal-scoped observation checkpoints. Adversarial rule: any principal not listed for a fact must observe zero bytes of that fact.",
        "scenarios": [
            {
                "scenario_id": s["scenario_id"],
                "title": s["title"],
                "checkpoints": s["hidden_information_checkpoints"],
            }
            for s in scenarios
        ],
    }
    (BASE / "RQ_C1_HIDDEN_INFO_EXPECTATIONS.json").write_text(
        json.dumps(hidden, indent=1) + "\n"
    )

    rng = {
        "schema": "rq-c1.rng-expectations.v1",
        "journal_contract": "Each RNG operation requires: purpose, valid domain, candidate-set fingerprint, sampled result, Rules event, replay assertion. RNG originates in the Rules Core with explicit seed authority; no harness-side randomness.",
        "unspecified_placeholder_policy": "Domains marked EXECUTION_PRESCRIBED are fixed at future execution time by the execution contract (seed authority + journal), never invented by the corpus.",
        "scenarios": [
            {
                "scenario_id": s["scenario_id"],
                "title": s["title"],
                "rng_operations": s["rng_operations"],
                "rng_starting_contract": (
                    s["neutral_initial_state"].get("rng_starting_contract")
                ),
            }
            for s in scenarios
            if s["rng_operations"]
        ],
    }
    (BASE / "RQ_C1_RNG_EXPECTATIONS.json").write_text(json.dumps(rng, indent=1) + "\n")

    boundaries = {
        "schema": "rq-c1.native-setup-boundaries.v1",
        "ws51_rule": "RESTORE_PATH_REJECTED: no scenario may restore into a decision-bearing step and pretend native lifecycle entry occurred. Restore-as-construction strictly before the first decision-bearing step is preserved; native progression thereafter is required.",
        "scenarios": [
            {
                "scenario_id": s["scenario_id"],
                "title": s["title"],
                "native_setup_boundary": s["native_setup_boundary"],
            }
            for s in scenarios
        ],
    }
    (BASE / "RQ_C1_NATIVE_SETUP_BOUNDARIES.json").write_text(
        json.dumps(boundaries, indent=1) + "\n"
    )

    print(f"scenarios={len(scenarios)} kinds={len(all_kinds)} axes={len(all_axes)}")


if __name__ == "__main__":
    main()
