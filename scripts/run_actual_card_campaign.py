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

    candidate_commit = bridge_launcher.canonical_xmage_engine_pin()
    args.out.mkdir(parents=True, exist_ok=True)
    campaign_identity = {
        "workstream": "AF07-ACTUAL-CARD-CAMPAIGN-20261001",
        "runner": runner.to_document(),
        "engine_runtime_directory": str(runtime_dir),
        "workspace": _workspace_identity(workspace),
    }

    def report(row: campaign.CardRow, evaluation: dict[str, Any]) -> None:
        detail = evaluation.get("blocker_detail") or ""
        print(
            f"{row.fixture_id} {row.card_identity}: {evaluation.get('outcome')} "
            f"{evaluation.get('blocker_class') or ''} {detail[:140]}"
        )

    try:
        matrix = campaign.execute_and_persist(
            workspace=workspace,
            candidate_commit=candidate_commit,
            runner_digest=runner.digest(),
            receipts_dir=args.out / "receipts" / campaign.RECEIPT_SUBDIR,
            fixtures=args.rows,
            seed=args.seed,
            root=REPO_ROOT,
            measurements_dir=args.out / "measurements",
            campaign_identity=campaign_identity,
            on_row=report,
        )
    except campaign.ActualCardCampaignError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    (args.out / "CAMPAIGN_IDENTITY.json").write_text(
        json.dumps(matrix["campaign"], indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    campaign.write_matrix(args.out / "AF07_ACTUAL_CARD_MATRIX.json", matrix)
    print(json.dumps(matrix["summary"], indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
