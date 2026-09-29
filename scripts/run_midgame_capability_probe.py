#!/usr/bin/env python3
"""End-to-end runtime probe for the production-reachable mid-game lane.

Launches the pinned engine's real ``midgame`` Protocol-2 process, submits only
decisions the engine itself offered, and writes a receipt containing the
engine's own capability manifest, the engine's own construction verdict and the
engine's own rejection codes.

The probe never computes legality, never invents an option and never converts a
rejection into a pass. A row is reported as reachable only when the engine
accepted the explicit frozen starting state and its field-level readback compare
reported no mismatch outside the documented declaration-step priority
allowance.

Usage:
    python scripts/run_midgame_capability_probe.py --out <receipt.json>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import midgame_lane as ml  # noqa: E402

MATERIALIZATION = (
    REPO_ROOT / "qualification" / "ws47" / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"
)

# Rows chosen to span the mechanism classes the current-boundary XMage column
# fails closed on one coarse capability bit. Each is a real frozen record with
# real card identities.
PROBE_ROWS: tuple[str, ...] = (
    "WS05-MP-COMBAT-4",
    "WS05-MP-COMBAT-5",
    "WS05-MP-BLOCK-4",
    "WS05-MP-ELIM-PRIO-3",
    "WS05-MP-TURN-5",
    "WS05-CMD-ELIM-4",
    "WS05-CMD-DMG-SPLIT",
    "WS05-CMD-PARTNER-ZONE",
    "WS05-CMD-TAX-2",
    "MICRO_REPLACEMENT",
    "MICRO_COMBAT",
    "CARD_02",
    "WS05-MP-PRIO-3",
    "WS05-CMD-DMG-CONTROL",
    "WS05-CMD-ZONE-GY-YES",
    "MICRO_ZONE_CHANGES",
)

SEED = 424242


def launch_argv(workspace: Path, classpath: str) -> tuple[str, ...]:
    return (
        "java",
        "-Djava.awt.headless=true",
        f"-Dcommanderlab.repoRoot={REPO_ROOT}",
        "-cp",
        f"{workspace / 'target' / 'classes'}:{classpath}",
        "org.commanderlab.xmage.Main",
        "midgame",
    )


def option_of_type(decision: dict[str, Any], option_type: str) -> str | None:
    for option in decision.get("legal_options") or ():
        if option.get("option_type") == option_type:
            return str(option.get("option_id"))
    return None


def option_by_label_suffix(decision: dict[str, Any], suffix: str) -> str | None:
    for option in decision.get("legal_options") or ():
        label = str(option.get("label") or "")
        if label.endswith(suffix):
            return str(option.get("option_id"))
    return None


def seat_label(principal_id: str) -> str:
    return "Full Game Seat " + principal_id.removeprefix("P")


# The frozen record addresses a checkpoint by (phase, step) pair; the engine's
# readback names the same point by a single step token. The mapping is the
# engine seam's own, reproduced here so the probe compares the engine's live
# reading against the record's own request rather than against a guess.
_ENGINE_STEP_BY_POINT: dict[tuple[str, str], str] = {
    ("beginning", "upkeep"): "UPKEEP",
    ("beginning", "draw"): "DRAW",
    ("precombat_main", "main"): "PRECOMBAT_MAIN",
    ("combat", "declare_attackers"): "DECLARE_ATTACKERS",
    ("combat", "declare_blockers"): "DECLARE_BLOCKERS",
    ("combat", "combat_damage"): "COMBAT_DAMAGE",
    ("postcombat_main", "main"): "POSTCOMBAT_MAIN",
}


def engine_temporal_point(phase: str, step: str, fixture_id: str) -> tuple[str, str]:
    try:
        return phase.upper(), _ENGINE_STEP_BY_POINT[(phase, step)]
    except KeyError as exc:
        raise ml.MidgameLaneError(
            f"{fixture_id}: the probe does not know the engine step for {phase}/{step}"
        ) from exc


def drive_arrival(client: ml.MidgameLaneClient, record: dict[str, Any]) -> ml.RowVerdict | None:
    """Drive the engine to the record's own temporal checkpoint.

    Every step is an external pilot answer selected from the engine's own
    offered options. The function answers nothing on the pilot's behalf and
    fails closed on a decision class it does not recognise.
    """
    temporal = record["temporal_state"]
    target_phase, target_step = engine_temporal_point(
        str(temporal["phase"]), str(temporal["step"]), str(record["fixture_id"])
    )
    active_label = seat_label(str(temporal["active_player"]))

    for _ in range(120):
        decision = client.pending_decision()
        if decision is None:
            break
        decision_class = str(decision.get("decision_class"))
        if decision_class == "mulligan":
            keep = option_of_type(decision, "keep")
            if keep is None:
                raise ml.MidgameLaneError("the engine offered no keep option for the mulligan")
            client.submit_options(decision, [keep])
        elif decision_class in {"choice", "choose_object"}:
            chosen = option_by_label_suffix(decision, active_label)
            if chosen is None:
                raise ml.MidgameLaneError(
                    f"the engine offered no option for the record's active principal {active_label}"
                )
            client.submit_options(decision, [chosen])
        elif decision_class == "priority":
            probe = client.complete_arrival().get("readback") or {}
            if str(probe.get("phase")) == target_phase and str(probe.get("step")) == target_step:
                return ml.classification_from_arrival(
                    str(record["fixture_id"]),
                    ml.MIDGAME_LANE,
                    client.complete_arrival(),
                    engine_commit=client.engine_commit,
                )
            passed = option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError("the engine offered no pass-priority option")
            client.submit_options(decision, [passed])
        elif decision_class in {"declare_attacker", "declare_blocker"}:
            # A declaration checkpoint: the engine has reached the record's
            # temporal point. Stop and let the caller decide whether to
            # execute the obligation.
            probe = client.complete_arrival().get("readback") or {}
            if str(probe.get("phase")) == target_phase and str(probe.get("step")) == target_step:
                return ml.classification_from_arrival(
                    str(record["fixture_id"]),
                    ml.MIDGAME_LANE,
                    client.complete_arrival(),
                    engine_commit=client.engine_commit,
                )
            raise ml.MidgameLaneError(
                f"the engine reached {probe.get('phase')}/{probe.get('step')} before the "
                f"record's requested {target_phase}/{target_step} checkpoint"
            )
        else:
            raise ml.MidgameLaneError(
                f"the probe refuses to answer an unrecognised decision class: {decision_class}"
            )
    raise ml.MidgameLaneError("the engine did not reach the record's temporal checkpoint")


def probe_row(workspace: Path, classpath: str, fixture_id: str) -> dict[str, Any]:
    record = ml.frozen_record(MATERIALIZATION, fixture_id)
    game_id = f"probe-{fixture_id}"
    request = {
        "game_id": game_id,
        "plan_id": game_id,
        "seed": SEED,
        "requested_starting_state": record,
    }
    started = time.time()
    with ml.MidgameLaneClient(launch_argv(workspace, classpath), workspace) as client:
        client.request("get_provider_version", None)
        client.read_dimension_manifest()
        created = client.request("create_midgame_game", request)
        if not created.get("success"):
            errors = created.get("errors") or []
            code = errors[0].get("code") if errors else None
            detail = errors[0].get("message") if errors else None
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code=code,
                detail=detail,
                engine_commit=client.engine_commit,
            )
            return verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}
        start = client.request("start_midgame_game", None)
        if not start.get("success"):
            errors = start.get("errors") or []
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code=errors[0].get("code") if errors else None,
                detail=errors[0].get("message") if errors else None,
                engine_commit=client.engine_commit,
            )
            return verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}
        try:
            row_verdict = drive_arrival(client, record)
        except ml.MidgameLaneError as exc:
            # The engine accepted the explicit starting state; the probe only
            # failed to execute the row's own scripted obligation. Recorded
            # distinctly so an accepted starting state is never reported as an
            # engine rejection, and never as a row-level pass either.
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code="OBLIGATION_NOT_EXECUTED",
                detail=str(exc),
                engine_commit=client.engine_commit,
                state_accepted=True,
            )
            return verdict.as_dict() | {
                "outcome": "ENGINE_STATE_ACCEPTED",
                "elapsed_s": round(time.time() - started, 3),
            }
        if row_verdict is None:
            verdict = ml.rejected_verdict(
                fixture_id,
                ml.MIDGAME_LANE,
                code="OBLIGATION_NOT_EXECUTED",
                detail="the engine went terminal before the record's temporal checkpoint",
                engine_commit=client.engine_commit,
                state_accepted=True,
            )
            return verdict.as_dict() | {
                "outcome": "ENGINE_STATE_ACCEPTED",
                "elapsed_s": round(time.time() - started, 3),
            }
        return row_verdict.as_dict() | {"elapsed_s": round(time.time() - started, 3)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=REPO_ROOT / "engine-bridge",
        help="the Lab engine-bridge module that carries target/classes",
    )
    parser.add_argument("--rows", nargs="*", default=list(PROBE_ROWS))
    args = parser.parse_args()

    classpath_file = args.workspace / "target" / "cp-wsr22.txt"
    if not classpath_file.is_file():
        print(
            f"missing {classpath_file}; build the bridge module and regenerate the classpath "
            f"manifest first",
            file=sys.stderr,
        )
        return 2
    classpath = classpath_file.read_text(encoding="utf-8").strip()

    manifest_payload: dict[str, Any] | None = None
    engine_commit: str | None = None
    with ml.MidgameLaneClient(launch_argv(args.workspace, classpath), args.workspace) as client:
        client.request("get_provider_version", None)
        manifest = client.read_dimension_manifest()
        manifest_payload = manifest.as_dict()
        engine_commit = client.engine_commit

    rows: list[dict[str, Any]] = []
    for fixture_id in args.rows:
        rows.append(probe_row(args.workspace, classpath, fixture_id))

    reachable = [row["fixture_id"] for row in rows if row["outcome"] == "ENGINE_NATIVE_REACHABLE"]
    accepted_only = [row["fixture_id"] for row in rows if row["outcome"] == "ENGINE_STATE_ACCEPTED"]
    mismatched = [row["fixture_id"] for row in rows if row["outcome"] == "CONSTRUCTION_MISMATCH"]
    rejected = [
        {"fixture_id": row["fixture_id"], "code": row["code"]}
        for row in rows
        if row["outcome"] == "ENGINE_REJECTED"
    ]

    receipt = {
        "schema_version": "commander-lab.midgame-capability-probe/1.0.0",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probe_run_id": str(uuid.uuid4()),
        "evidence_class": "FRESH_RUNTIME_PROTOCOL2_PROCESS",
        "rules_core": "xmage",
        "engine_commit": engine_commit,
        "lane": ml.MIDGAME_LANE,
        "protocol_version": ml.PROTOCOL_VERSION,
        "seed": SEED,
        "materialization": {
            "path": str(MATERIALIZATION.relative_to(REPO_ROOT)),
            "version": "commander-lab.semantic-fixture-materialization/1.0.5",
        },
        "starting_state_dimensions_manifest": manifest_payload,
        "counts": {
            "probed": len(rows),
            "engine_native_reachable": len(reachable),
            "engine_state_accepted_obligation_not_executed": len(accepted_only),
            "construction_mismatch": len(mismatched),
            "engine_rejected": len(rejected),
        },
        "engine_native_reachable": reachable,
        "engine_state_accepted_obligation_not_executed": accepted_only,
        "construction_mismatch": mismatched,
        "engine_rejected": rejected,
        "rows": rows,
        "notes": [
            "Every decision was submitted from the engine's own offered option set.",
            "Reachability requires the engine's own field-level readback compare to report no "
            "mismatch outside the documented declaration-step priority allowance. The engine's own "
            "raw construction_match bit is reported alongside the classification.",
            "ENGINE_STATE_ACCEPTED means the engine accepted the explicit starting state and this "
            "probe did not execute the row's own scripted obligation. It is not a row-level pass.",
            "Engine-rejected rows are reported with the engine's own code and stay fail closed.",
            "This probe is technical capability evidence. It is not provider selection and does "
            "not establish Architecture Freeze.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "engine_commit": engine_commit,
                "counts": receipt["counts"],
                "engine_native_reachable": reachable,
                "engine_state_accepted_obligation_not_executed": accepted_only,
                "engine_rejected": rejected,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
