#!/usr/bin/env python3
"""Run qualification rows against the real engines from a Lab worktree; one line per row.

Run from the Lab worktree root with its venv active (PYTHONPATH=src is set here):

    real_rows.py build                         package engine-bridge (offline) + classpath manifest
    real_rows.py midgame FIXTURE...            XMage mid-game lane rows (midgame_rows.execute_and_persist)
    real_rows.py cardinality CAND [--forge P]  PLAYER_COUNT_2P..5P on a keyed and an unkeyed launch
    real_rows.py pregame CAND [--forge P]      the scripted pregame rows, keyed and unkeyed
    real_rows.py af04 CAND PKG [--forge P]     fresh keyed 2P..6P cardinality + AF04 derivation
                                               against a PB-03 packet's AF01/identity (PKG dir)

CAND is xmage or forge; Forge needs --forge (a forge checkout at the pinned bridge
source) and an X display (wrap the call in ``xvfb-run -a``). LOCAL_OBSERVED only:
nothing here is credit; PB-03 on an exact head plus a sealed epoch is.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
M2 = os.environ.get("LAB_M2_REPO", str(Path.home() / ".m2" / "repository"))


def _records() -> dict[str, dict]:
    from commander_lab.qualification.current_boundary.materialization import (
        load_effective_materialization,
    )

    return {r["fixture_id"]: r for r in load_effective_materialization(ROOT).denominator_records()}


def _plan(cand: str, forge: str | None):
    from commander_lab.qualification.current_boundary import bridge_launcher as bl

    return bl.build_launch_plan(
        cand,
        lane="compat",
        xmage_workspace=(ROOT / "engine-bridge").resolve(),
        forge_workspace=Path(forge).resolve() if forge else None,
    )


def cmd_build(_: argparse.Namespace) -> None:
    for goal in (
        ["package", "-DskipTests"],
        ["dependency:build-classpath", "-Dmdep.outputFile=target/cp-wsr22.txt"],
    ):
        subprocess.run(
            ["mvn", "-o", "-B", "-q", *goal, f"-Dmaven.repo.local={M2}"],
            cwd=ROOT / "engine-bridge",
            check=True,
        )
    print("engine-bridge packaged; classpath at engine-bridge/target/cp-wsr22.txt")


def cmd_midgame(a: argparse.Namespace) -> None:
    from commander_lab.qualification.current_boundary import midgame_rows

    out = Path(a.out or "/tmp/real-rows-midgame")
    doc = midgame_rows.execute_and_persist(
        workspace=(ROOT / "engine-bridge").resolve(),
        records=_records(),
        candidate_commit=a.commit,
        runner_digest="local-dev",
        out_dir=out,
        fixtures=tuple(a.args),
    )
    print(f"verified {doc['rows_verified']}/{doc['rows_declared']} (full document: {out})")
    for fixture, row in doc["rows"].items():
        print(
            f"  {fixture} verified={row['verified']} missing={row['missing_tokens']} :: {str(row['detail'])[:160]}"
        )


def _keyed_and_unkeyed(cand: str, forge: str | None):
    from commander_lab.qualification.current_boundary import bridge_launcher as bl

    plan = _plan(cand, forge)
    return (("keyed", bl.orchestration_plan(plan)), ("unkeyed", plan))


def cmd_cardinality(a: argparse.Namespace) -> None:
    from commander_lab.qualification.current_boundary import bridge_launcher as bl
    from commander_lab.qualification.current_boundary import full107

    by_id = _records()
    for label, plan in _keyed_and_unkeyed(a.args[0], a.forge):
        with bl.launch(plan, timeout_s=300.0) as proc:
            for n in (2, 3, 4, 5):
                fixture = f"PLAYER_COUNT_{n}P"
                res = full107.run_cardinality(
                    proc,
                    candidate=a.args[0],
                    player_count=n,
                    runtime_identity={},
                    record=by_id[fixture],
                )
                row = full107.cardinality_row(
                    by_id[fixture], res, candidate=a.args[0], runtime_identity={}
                )
                print(f"{label} {fixture} {row.outcome} :: {row.reason[:150]}", flush=True)


def cmd_pregame(a: argparse.Namespace) -> None:
    from commander_lab.qualification.current_boundary import bridge_launcher as bl
    from commander_lab.qualification.current_boundary import full107

    by_id = _records()
    for label, plan in _keyed_and_unkeyed(a.args[0], a.forge):
        with bl.launch(plan, timeout_s=300.0) as proc:
            for fixture in full107.SCRIPTED_PREGAME_ROWS:
                row = full107.scripted_pregame_row(
                    by_id[fixture], proc, candidate=a.args[0], runtime_identity={}
                )
                ev = row.evidence
                print(
                    f"{label} {fixture} {row.outcome} performed={ev.get('engine_performed_mulligans')} "
                    f"unmet={ev.get('unmet_required_events')} :: {row.reason[:120]}",
                    flush=True,
                )


def cmd_af04(a: argparse.Namespace) -> None:
    from commander_lab.qualification.current_boundary import bridge_launcher as bl
    from commander_lab.qualification.current_boundary import decision_boundary as db
    from commander_lab.qualification.current_boundary import full107

    cand, pkg = a.args[0], Path(a.args[1])
    old = json.loads((pkg / f"PLAYER_CARDINALITY_{cand.upper()}.json").read_text())
    af01 = json.loads((pkg / f"AF01_{cand.upper()}.json").read_text())
    identity, by_id, results = old["runtime_identity"], _records(), {}
    with bl.launch(bl.orchestration_plan(_plan(cand, a.forge)), timeout_s=300.0) as keyed:
        for n in (2, 3, 4, 5, 6):
            res = full107.run_cardinality(
                keyed,
                candidate=cand,
                player_count=n,
                runtime_identity=identity,
                record=by_id.get(f"PLAYER_COUNT_{n}P"),
            )
            results[f"{n}P"] = res.to_document()
    boundary = db.derive_decision_boundary(cand, {**old, "results": results}, af01, identity)
    print(
        f"AF04 {boundary['verdict']} contradictions={len(boundary['contradictions'])} gaps={len(boundary['gaps'])}"
    )
    for finding in (boundary["contradictions"] + boundary["gaps"])[:10]:
        print(f"  {finding}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["build", "midgame", "cardinality", "pregame", "af04"])
    parser.add_argument("args", nargs="*")
    parser.add_argument("--forge", help="Forge checkout at the pinned bridge source")
    parser.add_argument("--out", help="midgame: output directory")
    parser.add_argument(
        "--commit",
        default="b479fe74fd1eaf899ff16c6a9203e74a91c0f339",
        help="midgame: candidate commit recorded in the document",
    )
    a = parser.parse_args()
    globals()[f"cmd_{a.command}"](a)


if __name__ == "__main__":
    main()
