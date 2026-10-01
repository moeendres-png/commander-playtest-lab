#!/usr/bin/env python3
"""Run the AF07 actual-card campaign on the current production midgame lane.

For each frozen actual-card identity this runner:

1. derives the row from the frozen manifests and the current effective
   materialization (never from a restated list);
2. executes the row on its own fresh production midgame-lane process, using the
   engine's own construction verdict, offered options and event tape;
3. evaluates the row against its obligation plan and classifies every non-PASS
   row with exactly one blocker class, surface and owner;
4. persists the per-row measurement, any runner-bound positive receipt, and the
   machine-readable 29-row matrix.

Heavy runtime is isolated: ``ENGINE_RUNTIME_DIRECTORY`` is pointed at a
run-scoped directory outside every candidate worktree, and each row runs in its
own engine process. The lane workspace is this worktree's ``engine-bridge``
build, so no other writer's worktree is read or written.

Usage:
    python scripts/run_actual_card_campaign.py --out <dir> [--rows CARD_01 ...]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    actual_card_campaign as campaign,
)
from commander_lab.qualification.current_boundary import bridge_launcher  # noqa: E402
from commander_lab.qualification.current_boundary import (  # noqa: E402
    midgame_rows as midgame_rows_mod,
)
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402


def _default_runtime_dir() -> Path:
    run_dir = os.environ.get("FOUNDRY_RUN_DIR")
    if run_dir:
        return Path(run_dir) / "af07-engine-runtime"
    return Path(tempfile.gettempdir()) / "af07-actual-card-engine-runtime"


def _workspace_identity(workspace: Path) -> dict[str, Any]:
    classes = workspace / "target" / "classes"
    classpath = workspace / "target" / "cp-wsr22.txt"
    return {
        "workspace": str(workspace),
        "classes_present": classes.is_dir(),
        "classpath_manifest": str(classpath),
        "classpath_manifest_present": classpath.is_file(),
        "classpath_manifest_sha256": (
            receipt_mod.document_digest({"classpath": classpath.read_text(encoding="utf-8")})
            if classpath.is_file()
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "docs" / "af07_actual_card_campaign_20261001" / "artifacts",
        help="campaign output directory (matrix, measurements, receipts)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=REPO_ROOT / "engine-bridge",
        help="the Lab engine-bridge module that carries target/classes",
    )
    parser.add_argument(
        "--rows",
        nargs="*",
        default=None,
        help="fixture ids to execute (default: every derived corpus row)",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=None,
        help="run-scoped engine runtime directory (isolation boundary)",
    )
    parser.add_argument("--seed", type=int, default=campaign.SEED)
    args = parser.parse_args()

    runtime_dir = args.runtime_dir or _default_runtime_dir()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.environ["ENGINE_RUNTIME_DIRECTORY"] = str(runtime_dir)

    workspace = args.workspace.resolve()
    classpath_manifest = workspace / "target" / "cp-wsr22.txt"
    if not classpath_manifest.is_file():
        print(
            f"missing {classpath_manifest}; build the bridge module first "
            "(mvn -DskipTests compile dependency:build-classpath "
            "-Dmdep.outputFile=target/cp-wsr22.txt)",
            file=sys.stderr,
        )
        return 2

    runner = receipt_mod.capture_runner_identity(REPO_ROOT)
    receipt_mod.require_clean_runner(runner)

    corpus = campaign.derive_corpus(REPO_ROOT)
    selected = (
        [row.fixture_id for row in corpus.rows]
        if args.rows is None
        else [str(fixture_id) for fixture_id in args.rows]
    )
    known = {row.fixture_id for row in corpus.rows}
    unknown = [fixture_id for fixture_id in selected if fixture_id not in known]
    if unknown:
        print(f"unknown AF07 fixture ids: {unknown}", file=sys.stderr)
        return 2

    candidate_commit = bridge_launcher.canonical_xmage_engine_pin()
    probe = midgame_rows_mod.probe_module()
    # The production probe's own declared causal entries: rows whose position the
    # lane can reach causally even though the direct native load refuses them.
    causal_entry_rows = frozenset(getattr(probe, "CAUSAL_ROWS", {}) or {})

    args.out.mkdir(parents=True, exist_ok=True)
    measurements_dir = args.out / "measurements"
    receipts_dir = args.out / "receipts" / receipt_mod.POSITIVE_RECEIPT_SUBDIR
    measurements_dir.mkdir(parents=True, exist_ok=True)
    receipts_dir.mkdir(parents=True, exist_ok=True)

    campaign_identity = {
        "workstream": "AF07-ACTUAL-CARD-CAMPAIGN-20261001",
        "execution_mode": campaign.EXECUTION_MODE,
        "test_identity_prefix": campaign.TEST_IDENTITY_PREFIX,
        "runner": runner.to_document(),
        "runner_digest": runner.digest(),
        "candidate": "xmage",
        "candidate_commit": candidate_commit,
        "engine_runtime_directory": str(runtime_dir),
        "workspace": _workspace_identity(workspace),
        "selected_rows": selected,
        "causal_entry_rows": sorted(causal_entry_rows),
        "seed": args.seed,
    }
    (args.out / "CAMPAIGN_IDENTITY.json").write_text(
        json.dumps(campaign_identity, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    evaluations: dict[str, dict[str, Any]] = {}
    measurements: dict[str, campaign.RowMeasurement] = {}
    engine_artifact: dict[str, Any] | None = None
    for fixture_id in selected:
        row = corpus.row(fixture_id)
        plan = campaign.plan_for(fixture_id)
        with probe.open_client(workspace) as client:
            measurement = campaign.measure_row(client, row, plan, seed=args.seed)
            if client.engine_artifact:
                engine_artifact = dict(client.engine_artifact)
        measurement.runtime_error = None
        measurements[fixture_id] = measurement
        evaluation = campaign.evaluate_row(
            row,
            measurement,
            expected_engine_commit=candidate_commit,
            foreign_owned_surfaces=campaign.DEFAULT_FOREIGN_OWNED_SURFACES,
            causal_entry_rows=causal_entry_rows,
        )
        if evaluation.get("outcome") == campaign.OUTCOME_DIRECT_PASS:
            receipt = campaign.positive_receipt(
                row,
                evaluation,
                measurement,
                candidate="xmage",
                candidate_commit=candidate_commit,
                runner_digest=runner.digest(),
            )
            receipt_mod.persist(receipts_dir / f"{fixture_id}.json", receipt)
            evaluation["receipt_digest"] = receipt["receipt_digest"]
        else:
            stale = receipts_dir / f"{fixture_id}.json"
            if stale.is_file():
                stale.unlink()
        evaluations[fixture_id] = evaluation
        campaign.write_measurement(measurements_dir / f"{fixture_id}.json", measurement)
        detail = evaluation.get("blocker_detail") or ""
        print(
            f"{fixture_id} {row.card_identity}: {evaluation.get('outcome')} "
            f"{evaluation.get('blocker_class') or ''} {detail[:140]}"
        )

    matrix = campaign.build_matrix(
        corpus,
        evaluations,
        measurements,
        campaign_identity=campaign_identity,
    )
    matrix["campaign"]["engine_artifact"] = engine_artifact
    matrix["campaign"]["matrix_digest"] = campaign.matrix_digest(
        {key: value for key, value in matrix.items() if key != "campaign"}
    )
    campaign.write_matrix(args.out / "AF07_ACTUAL_CARD_MATRIX.json", matrix)
    print(json.dumps(matrix["summary"], indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
