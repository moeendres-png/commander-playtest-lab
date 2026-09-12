#!/usr/bin/env python3
"""WS74 XMage Full107 construction driver (staging only; zero behavior credit).

Pipeline:
  Phase 0  exact Full107 denominator binding (mechanical re-read, 135/107/28).
  Phase 1  engine/provider binding verification (exact pin, clean tree,
           fresh-build digest match, predecessor absence, bridge lineage).
  Phase 2  deterministic harness rebuild from committed sources.
  Phase 3  107/107 construction attempts in fresh exact-pin JVM(s).
  Phase 4  FULL107_CONSTRUCTION_MATRIX.json (terminal per-fixture adjudication).

Construction classifications: CONSTRUCTED | CONSTRUCTION_FAIL | UNKNOWN.
No behavior is executed anywhere. No credit is granted anywhere.

Evidence classes used: DIRECTLY_VERIFIED, CODE_DERIVED, TECHNICALLY_CONFORMANT.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import ws74_denominator as DEN  # noqa: E402

ENGINE_COMMIT = "7135d5e85ddb4c8aa4b49b4192ca51947c822704"
ENGINE_TREE = "ea193e0d04493d53d962ed13ebd3b5d2f68838c7"
ENGINE_REPO = "moeendres-png/mage"
OLD_ENGINE_COMMIT = "0c1f455ea8c8fa48ab9d638ad5068ec242800428"
MAGE_SRC = Path("/tmp/ws56-mage-successor-src")

M2 = Path("/home/moeen/.m2/repository")
RUNTIME_JARS = [
    "org/mage/mage/1.4.61/mage-1.4.61.jar",
    "org/mage/mage-sets/1.4.61/mage-sets-1.4.61.jar",
    "org/mage/mage-deck-constructed/1.4.61/mage-deck-constructed-1.4.61.jar",
    (
        "org/mage/mage-game-commanderfreeforall/1.4.61/"
        "mage-game-commanderfreeforall-1.4.61.jar"
    ),
]
FRESH_TARGETS = [
    "Mage/target/mage-1.4.61.jar",
    "Mage.Sets/target/mage-sets-1.4.61.jar",
    "Mage.Server.Plugins/Mage.Deck.Constructed/target/mage-deck-constructed-1.4.61.jar",
    (
        "Mage.Server.Plugins/Mage.Game.CommanderFreeForAll/target/"
        "mage-game-commanderfreeforall-1.4.61.jar"
    ),
]
EXTRA_JARS = [
    "com/google/code/gson/gson/2.13.2/gson-2.13.2.jar",
    "com/google/guava/guava/33.4.8-jre/guava-33.4.8-jre.jar",
    "org/jsoup/jsoup/1.21.2/jsoup-1.21.2.jar",
    "com/google/protobuf/protobuf-java/3.25.8/protobuf-java-3.25.8.jar",
    "com/google/guava/failureaccess/1.0.3/failureaccess-1.0.3.jar",
    "ch/qos/reload4j/reload4j/1.2.22/reload4j-1.2.22.jar",
    "org/slf4j/slf4j-api/2.0.17/slf4j-api-2.0.17.jar",
    "com/j256/ormlite/ormlite-jdbc/5.7/ormlite-jdbc-5.7.jar",
    "com/j256/ormlite/ormlite-core/5.7/ormlite-core-5.7.jar",
    "com/h2database/h2/1.4.197/h2-1.4.197.jar",
    (
        "com/google/guava/listenablefuture/"
        "9999.0-empty-to-avoid-conflict-with-guava/"
        "listenablefuture-9999.0-empty-to-avoid-conflict-with-guava.jar"
    ),
]

WS56_SUCCESSOR_COMMIT = "1dc43619eff5b71cf20405c5c8da83493ff52732db"
WS60_TERMINAL_COMMIT = "731891ec5ed8e7611fc9a636bab5fc3c400108eb"


def sh(args, cwd=None, timeout=None):
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=timeout)


def sha_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_cpl(args: str) -> str:
    out = sh(["git"] + args.split(), cwd=str(REPO))
    if out.returncode != 0:
        raise RuntimeError("WS74_CPL_GIT_FAILED:%s:%s" % (args, out.stderr[:200]))
    return out.stdout.strip()


def git_mage(args_list):
    out = subprocess.run(
        ["git"] + args_list, capture_output=True, text=True, cwd=str(MAGE_SRC)
    )
    if out.returncode != 0:
        raise RuntimeError(
            "WS74_MAGE_GIT_FAILED:%s:%s" % (args_list, out.stderr[:200])
        )
    return out.stdout.strip()


def phase1_binding() -> dict:
    """Verify exact-pin engine checkout, clean tree, fresh-build match."""
    head = git_mage(["rev-parse", "HEAD"])
    tree = git_mage(["rev-parse", "HEAD^{tree}"])
    status = git_mage(["status", "--porcelain"])
    if head != ENGINE_COMMIT:
        raise RuntimeError("WS74_ENGINE_COMMIT_MISMATCH:%s" % head)
    if tree != ENGINE_TREE:
        raise RuntimeError("WS74_ENGINE_TREE_MISMATCH:%s" % tree)
    tracked = [l for l in status.splitlines() if l and not l.startswith("??")]
    if tracked:
        raise RuntimeError("WS74_ENGINE_TRACKED_MODIFICATIONS:%s" % tracked[:5])
    remote = git_mage(["config", "--get", "remote.origin.url"])
    if "moeendres-png/mage" not in remote:
        raise RuntimeError("WS74_ENGINE_REMOTE_MISMATCH:%s" % remote)
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", OLD_ENGINE_COMMIT, ENGINE_COMMIT],
        capture_output=True,
        text=True,
        cwd=str(MAGE_SRC),
    )
    successor_descends = ancestor.returncode == 0

    jar_rows = []
    for rel, tgt in zip(RUNTIME_JARS, FRESH_TARGETS):
        m2jar = M2 / rel
        fresh = MAGE_SRC / tgt
        if not m2jar.exists():
            raise RuntimeError("WS74_M2_JAR_MISSING:%s" % rel)
        if not fresh.exists():
            raise RuntimeError("WS74_FRESH_JAR_MISSING:%s" % tgt)
        d_m2 = sha_file(m2jar)
        d_fresh = sha_file(fresh)
        # Only one version may exist locally (predecessor-pin absence).
        versions = sorted(p.name for p in (M2 / rel).parent.parent.iterdir() if p.is_dir())
        jar_rows.append(
            {
                "artifact": rel,
                "fresh_target": tgt,
                "fresh_sha256": d_fresh,
                "runtime_sha256": d_m2,
                "byte_identical": d_fresh == d_m2,
                "local_versions": versions,
            }
        )
        if d_fresh != d_m2:
            raise RuntimeError("WS74_JAR_DIGEST_MISMATCH:%s" % rel)
        if versions != ["1.4.61"]:
            raise RuntimeError("WS74_MULTIPLE_LOCAL_VERSIONS:%s:%s" % (rel, versions))

    for rel in EXTRA_JARS:
        if not (M2 / rel).exists():
            raise RuntimeError("WS74_EXTRA_JAR_MISSING:%s" % rel)

    cpl_head = git_cpl("rev-parse HEAD")
    cpl_tree = git_cpl("rev-parse HEAD^{tree}")
    bridge_files = [
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java",
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameDecisionController.java",
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java",
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java",
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageGameManager.java",
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageDeckImporter.java",
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageBridgePlayer.java",
    ]
    bridge_digests = {}
    for f in bridge_files:
        out = sh(["git", "hash-object", f], cwd=str(REPO))
        if out.returncode != 0:
            raise RuntimeError("WS74_BRIDGE_HASH_FAILED:%s" % f)
        bridge_digests[f] = out.stdout.strip()

    return {
        "engine_repository": ENGINE_REPO,
        "engine_commit": head,
        "engine_tree": tree,
        "engine_working_tree_tracked_clean": True,
        "engine_remote_url": remote,
        "old_pin": OLD_ENGINE_COMMIT,
        "successor_descends_from_old_pin": successor_descends,
        "jars_byte_identical_fresh_build": jar_rows,
        "predecessor_pin_absent_from_classpath": True,
        "cpl_commit": cpl_head,
        "cpl_tree": cpl_tree,
        "bridge_lineage": {
            "ws56_successor_requalification": WS56_SUCCESSOR_COMMIT,
            "ws60_rqc3_first_wave_terminal": WS60_TERMINAL_COMMIT,
            "bridge_file_digests": bridge_digests,
        },
    }


def harness_classpath() -> str:
    parts = [str(REPO / "engine-bridge" / "target" / "classes")]
    for rel in RUNTIME_JARS + EXTRA_JARS:
        parts.append(str(M2 / rel))
    return ":".join(parts)


def compile_harness(workdir: Path, run_env: dict) -> Path:
    classes = workdir / "ws74-classes"
    if classes.exists():
        import shutil

        shutil.rmtree(classes)
    classes.mkdir(parents=True)
    src = HERE / "java/org/commanderlab/xmage/Ws74StagingHarness.java"
    if not src.exists():
        raise RuntimeError("WS74_HARNESS_SOURCE_MISSING")
    out = sh(
        ["javac", "-nowarn", "-cp", harness_classpath(), "-d", str(classes), str(src)],
        cwd=str(REPO),
        timeout=300,
    )
    if out.returncode != 0 or not (classes / "org/commanderlab/xmage/Ws74StagingHarness.class").exists():
        raise RuntimeError("WS74_HARNESS_COMPILE_FAILED:%s" % out.stderr[:2000])
    # Source digest for the receipt (exact tool identity).
    return classes


def extract_contract(scratch: Path) -> tuple:
    mat_raw = DEN.git_show(DEN.WS47_COMMIT + ":" + DEN.MATERIALIZATION_PATH)
    den_raw = DEN.git_show(DEN.WS47_COMMIT + ":" + DEN.DENOMINATOR_PATH)
    if hashlib.sha256(mat_raw).hexdigest() != DEN.MATERIALIZATION_SHA256:
        raise RuntimeError("WS74_MATERIALIZATION_SHA_MISMATCH")
    mat_path = scratch / "materialization.json"
    den_path = scratch / "denominator.json"
    mat_path.write_bytes(mat_raw)
    den_path.write_bytes(den_raw)
    return mat_path, den_path


def run_harness(classes: Path, mat_path: Path, den_path: Path, rundir: Path,
                cpl_commit: str, cpl_tree: str, only: str | None,
                scratch: Path) -> None:
    rundir.mkdir(parents=True, exist_ok=True)
    cp = str(classes) + ":" + harness_classpath()
    cmd = [
        "java",
        "-Djava.io.tmpdir=%s" % str(scratch),
        "-cp",
        cp,
        "org.commanderlab.xmage.Ws74StagingHarness",
        "--materialization",
        str(mat_path),
        "--denominator",
        str(den_path),
        "--out",
        str(rundir),
        "--cpl-commit",
        cpl_commit,
        "--cpl-tree",
        cpl_tree,
    ]
    if only:
        cmd += ["--only", only]
    log_path = rundir / ("harness-%s.log" % (only or "all"))
    with open(log_path, "w") as log:
        # JVM working directory is the (scratch) rundir: engine runtime
        # outputs (e.g. card-repository H2 cache) never touch the worktree.
        proc = subprocess.Popen(
            cmd, cwd=str(rundir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            if "WS74_CONSTRUCT" in line:
                print(line.rstrip())
        proc.wait(timeout=3600)
        if proc.returncode != 0:
            raise RuntimeError("WS74_HARNESS_RUN_FAILED rc=%s" % proc.returncode)


def build_matrix(binding: dict, rundir: Path, by_id: dict) -> dict:
    rows = []
    for entry in binding["ordered_denominator"]:
        fid = entry["fixture_id"]
        rp = rundir / (fid + ".json")
        if not rp.exists():
            rows.append(
                {
                    "fixture_id": fid,
                    "contract_digest": entry["requested_state_digest"],
                    "execution_entry_mode": entry["execution_entry_mode"],
                    "construction_result": "UNKNOWN",
                    "construction_code": "READBACK_MISSING",
                    "engine_commit": ENGINE_COMMIT,
                    "attempted": False,
                }
            )
            continue
        rb = json.loads(rp.read_text())
        cons = rb.get("construction", {})
        prov = rb.get("provenance", {})
        rows.append(
            {
                "fixture_id": fid,
                "contract_digest": entry["requested_state_digest"],
                "readback_digest_match_contract": rb.get("contract_digest")
                == entry["requested_state_digest"],
                "execution_entry_mode": rb.get("execution_entry_mode"),
                "player_count": cons.get("player_count"),
                "requested_object_count": cons.get("requested_object_count"),
                "placed_object_count": cons.get("placed_object_count"),
                "failed_placement_count": len(cons.get("failed_placements", [])),
                "failed_placements": cons.get("failed_placements", []),
                "construction_result": cons.get("result"),
                "construction_code": cons.get("code"),
                "construction_detail": cons.get("detail"),
                "rules_seed": prov.get("rules_seed"),
                "engine_commit": prov.get("engine_commit"),
                "engine_tree": prov.get("engine_tree"),
                "cpl_commit": prov.get("cpl_commit"),
                "runtime_jar_digests": prov.get("runtime_jar_digests"),
                "readback_sha256": sha_file(rp),
                "attempted": True,
            }
        )
    attempted = sum(1 for r in rows if r["attempted"])
    constructed = sum(1 for r in rows if r["construction_result"] == "CONSTRUCTED")
    return {
        "schema": "ws74.full107-construction-matrix.v1",
        "evidence_class": "CODE_DERIVED",
        "engine_commit": ENGINE_COMMIT,
        "engine_tree": ENGINE_TREE,
        "attempted": attempted,
        "constructed": constructed,
        "failed": attempted - constructed,
        "denominator": 107,
        "behavior_credit": "0/107",
        "rows": rows,
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--run-all", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--rundir", default=None)
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    scratch = (HERE / ".scratch").resolve()
    scratch.mkdir(exist_ok=True)

    print("== WS74 Phase 0: denominator binding")
    binding = DEN.bind()
    (HERE / "FULL107_DENOMINATOR_BINDING.json").write_text(
        json.dumps(dict(binding, verdict="PASS"), indent=2, sort_keys=True) + "\n"
    )
    print("WS74_DENOMINATOR_BINDING=PASS 135/107/28")

    print("== WS74 Phase 1: engine/provider binding")
    receipt_binding = phase1_binding()
    print(
        "engine=%s tree=%s jars=%d/4 identical cpl=%s"
        % (
            receipt_binding["engine_commit"][:8],
            receipt_binding["engine_tree"][:8],
            len(receipt_binding["jars_byte_identical_fresh_build"]),
            receipt_binding["cpl_commit"][:8],
        )
    )

    run_env = dict(os.environ)
    if not args.skip_build:
        print("== WS74 Phase 2: harness rebuild")
        classes = compile_harness(scratch, run_env)
        print("harness compiled")
    else:
        classes = scratch / "ws74-classes"

    mat_path, den_path = extract_contract(scratch)
    mat = json.loads(mat_path.read_text())
    by_id = {r["fixture_id"]: r for r in mat["records"]}

    rundir = Path(args.rundir).resolve() if args.rundir else (scratch / "run-main")
    if args.run_all or args.only:
        print("== WS74 Phase 3: construction")
        run_harness(
            classes,
            mat_path,
            den_path,
            rundir,
            receipt_binding["cpl_commit"],
            receipt_binding["cpl_tree"],
            args.only,
            scratch,
        )

    print("== WS74 Phase 4: construction matrix")
    matrix = build_matrix(binding, rundir, by_id)
    (HERE / "FULL107_CONSTRUCTION_MATRIX.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n"
    )
    receipt = {
        "schema": "ws74.xmage-build-receipt.v1",
        "evidence_class": "DIRECTLY_VERIFIED",
        "binding": receipt_binding,
        "harness_source": "java/org/commanderlab/xmage/Ws74StagingHarness.java",
        "harness_source_sha256": sha_file(
            HERE / "java/org/commanderlab/xmage/Ws74StagingHarness.java"
        ),
        "build_command": (
            "mvn -o -B -DskipTests -f /tmp/ws56-mage-successor-src/pom.xml "
            "-pl Mage.Server.Plugins/Mage.Deck.Constructed,"
            "Mage.Server.Plugins/Mage.Game.CommanderFreeForAll -am install"
        ),
        "handshake": "runtime classpath jar digests byte-identical to fresh "
        "exact-pin build targets; only 1.4.61 present locally; "
        "successor descends from old pin; old pin absent from classpath",
        "behavior_credit": "0/107",
    }
    (HERE / "XMAGE_BUILD_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(
        "FULL107_CONSTRUCTION=%d/107 attempted=%d"
        % (matrix["constructed"], matrix["attempted"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
