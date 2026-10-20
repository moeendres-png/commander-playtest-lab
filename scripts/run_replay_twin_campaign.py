#!/usr/bin/env python3
"""AF09 clean-process semantic replay twin campaign.

Runs the twin contract for XMage, applies the mandatory adversarial controls, and
writes one evidence document. A lane that cannot expose a required channel is
recorded as UNKNOWN with the exact missing capability instead of a workaround.

The campaign never selects a Production Provider and never claims Architecture
Freeze. It is safe to run while other writers own shared qualification
surfaces: it only writes under its own evidence/docs directory and its own
runtime scratch directory.

Usage:
    python scripts/run_replay_twin_campaign.py
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import bridge_launcher  # noqa: E402
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402
from commander_lab.qualification.current_boundary import replay_twins as twins  # noqa: E402

DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "af09_replay_twins_20261001" / "evidence"
CONFORMANCE_SCRIPT = REPO_ROOT / "scripts" / "run_external_full_game_conformance.py"
XMAGE_MAGE_JAR_NAME = "mage-1.4.62.jar"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=("xmage",), default="xmage")
    parser.add_argument("--player-count", type=int, default=4)
    parser.add_argument("--seed", type=int, default=424242)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--evidence-name",
        default=None,
        help="evidence file stem (default AF09_REPLAY_TWIN_<CANDIDATE>[ _<N>P])",
    )
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--xmage-workspace", type=Path, default=None)
    parser.add_argument(
        "--xmage-mage-jar",
        type=Path,
        default=None,
        help=(
            "replace the classpath's org.mage:mage:1.4.62 jar with this exact "
            "artifact (used to run the pinned candidate build locally); the "
            "provider's observed artifact digest is still bound from the engine"
        ),
    )
    parser.add_argument("--xmage-max-decisions", type=int, default=120)
    return parser.parse_args()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _work_dir(argument: Path | None) -> Path:
    if argument is not None:
        return argument
    run_dir = os.environ.get("FOUNDRY_RUN_DIR")
    if run_dir:
        return Path(run_dir) / "replay-twin-campaign"
    return REPO_ROOT / ".runtime" / "af09-replay-twins"


def _lab_source() -> dict[str, Any]:
    commit = receipt_mod.git_fact(REPO_ROOT, "rev-parse", "HEAD", sha=True)
    tree = receipt_mod.git_fact(REPO_ROOT, "rev-parse", "HEAD^{tree}", sha=True)
    dirty = sorted(receipt_mod._git_porcelain(REPO_ROOT))
    return {"commit": commit, "tree": tree, "clean": not dirty, "dirty_paths": dirty}


def _engine_pins() -> dict[str, Any]:
    return {"xmage_candidate_commit": bridge_launcher.canonical_xmage_engine_pin()}


def _load_conformance_module() -> Any:
    if not CONFORMANCE_SCRIPT.is_file():
        raise SystemExit(f"missing conformance fixture builder: {CONFORMANCE_SCRIPT}")
    spec = importlib.util.spec_from_file_location(
        "af09_full_game_conformance_fixture", CONFORMANCE_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load conformance fixture builder: {CONFORMANCE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply_mage_jar_override(command: tuple[str, ...], jar: Path) -> tuple[str, ...]:
    if not jar.is_file():
        raise SystemExit(f"--xmage-mage-jar is not a file: {jar}")
    replaced = []
    hits = 0
    for part in command:
        if part.endswith(XMAGE_MAGE_JAR_NAME):
            replaced.append(str(jar))
            hits += 1
        else:
            replaced.append(part)
    if hits == 0:
        raise SystemExit(
            f"--xmage-mage-jar was given but no classpath entry ends with {XMAGE_MAGE_JAR_NAME}"
        )
    return tuple(replaced)


def _write(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")


def _base_document(candidate: str, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema_version": "commander-lab.af09-replay-twin-campaign/1.0.0",
        "candidate": candidate,
        "generated_at": _now(),
        "lab_source": _lab_source(),
        "engine_pins": _engine_pins(),
        "fixture_request": {
            "player_count": args.player_count,
            "seed": args.seed,
        },
        "verdict": "UNKNOWN",
        "clean_process_twin": None,
        "adversarial_controls": [],
        "missing_capability": None,
        "failure": None,
    }


def run_xmage(args: argparse.Namespace, work_dir: Path) -> dict[str, Any]:
    document = _base_document("xmage", args)
    workspace = args.xmage_workspace or (REPO_ROOT / "engine-bridge")
    classpath = workspace / "target" / "cp-wsr22.txt"
    if not classpath.is_file():
        document["verdict"] = "UNKNOWN"
        document["missing_capability"] = {
            "channel": "xmage_full_game_bridge_build",
            "detail": (
                f"the Lab XMage bridge is not built in this checkout: {classpath} is absent; "
                "the full-game lane cannot be launched"
            ),
            "evidence_channel": str(classpath),
        }
        return document
    try:
        conformance = _load_conformance_module()
        scenario, decks, pilots = conformance.build_setup(args.player_count)
    except SystemExit:
        raise
    except Exception as exc:
        document["failure"] = f"fixture construction failed: {type(exc).__name__}: {exc}"
        document["verdict"] = "FAIL"
        return document
    plan = bridge_launcher.build_launch_plan("xmage", lane="full-game", xmage_workspace=workspace)
    command = plan.argv
    if args.xmage_mage_jar is not None:
        command = _apply_mage_jar_override(command, args.xmage_mage_jar)
        document["mage_jar_override"] = {
            "path": str(args.xmage_mage_jar),
            "sha256": hashlib_sha256(args.xmage_mage_jar),
        }
    document["fixture"] = {
        "scenario_id": scenario.scenario_id,
        "player_count": scenario.player_count,
        "seed": scenario.seed,
        "xmage_commit": scenario.xmage_commit,
        "deck_hashes": [deck.deck_hash for deck in decks],
    }
    try:
        (
            run_a,
            run_b,
            comparison,
            replay_check,
            tape_comparison,
            processes,
        ) = twins.run_xmage_tape_twin(
            scenario=scenario,
            decks=tuple(decks),
            pilots=tuple(pilots),
            command=command,
            cwd=plan.cwd,
            work_dir=work_dir / "xmage",
            max_decisions=args.xmage_max_decisions,
        )
    except twins.TwinChannelUnavailable as exc:
        document["missing_capability"] = exc.to_document()
        document["verdict"] = "UNKNOWN"
        return document
    except Exception as exc:
        document["failure"] = f"{type(exc).__name__}: {exc}"
        document["verdict"] = "UNKNOWN"
        return document

    controls = twins.run_adversarial_controls(run_a, run_b)
    twin = twins.clean_process_twin_document(
        record=run_a,
        replay=run_b,
        comparison=comparison,
        replay_check=replay_check,
        adversarial_controls=controls,
    )
    twin["process_identity"] = [
        *twin["process_identity"],
        *[identity.to_document() for identity in processes[2:]],
    ]
    twin["tape_comparison"] = tape_comparison
    document["clean_process_twin"] = twin
    document["adversarial_controls"] = controls
    document["verdict"] = twin["verdict"]
    if not replay_check.get("pass"):
        document["consumer_divergence"] = replay_check
    return document


def hashlib_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = _parse_args()
    work_dir = _work_dir(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    candidates = (args.candidate,)
    results: dict[str, str] = {}
    for candidate in candidates:
        print(f"=== AF09 replay twin: {candidate} ===")
        document = run_xmage(args, work_dir)
        suffix = f"_{args.player_count}P" if args.player_count != 4 else ""
        name = args.evidence_name or f"AF09_REPLAY_TWIN_{candidate.upper()}{suffix}"
        _write(args.out_dir / f"{name}.json", document)
        results[candidate] = str(document["verdict"])
        print(f"{candidate}: {document['verdict']}")
    print(json.dumps({"verdicts": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
