#!/usr/bin/env python3
"""WS74 staging determinism check (staging only; zero behavior credit).

Reruns the full construction + normalization pipeline from the committed
tools into fresh directories and requires deterministic normalized outputs:
identical normalized digests, identical classifications/codes, and
byte-identical normalized projections for every adjudicated fixture.

Volatile by design (excluded from comparison, documented per fixture):
native UUIDs, engine game UUIDs, decision/action IDs, wall-clock/log text.
Everything compared here is required deterministic: seeds are explicit
(424242 / scenario seeds), shuffles are Rules-seeded, placements are
record-ordered, and normalization strips all provider-local IDs.

Verdict STAGING_DETERMINISM=PASS|FAIL.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))


def sh(args, timeout=None):
    return subprocess.run(args, capture_output=True, text=True, cwd=str(REPO), timeout=timeout)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir-a", required=True)
    ap.add_argument("--normdir-a", required=True)
    ap.add_argument("--rundir-b", default=None)
    ap.add_argument("--normdir-b", default=None)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--spots", action="store_true",
                    help="isolated single-fixture JVM spot checks (contamination)")
    args = ap.parse_args()

    rundir_b = Path(args.rundir_b) if args.rundir_b else (HERE / ".scratch" / "run-rerun")
    normdir_b = Path(args.normdir_b) if args.normdir_b else (HERE / ".scratch" / "norm-rerun")
    backups = {}

    if args.rerun:
        # Back up canonical matrices: the rerun regenerates them as a side
        # effect and they are restored afterwards (readback SHAs are volatile).
        backups = {}
        for name in ("FULL107_DENOMINATOR_BINDING.json",
                     "FULL107_CONSTRUCTION_MATRIX.json",
                     "XMAGE_BUILD_RECEIPT.json",
                     "FULL107_NORMALIZATION_MATRIX.json"):
            fp = HERE / name
            if fp.exists():
                backups[name] = fp.read_bytes()
        print("== determinism rerun: construction")
        out = sh([sys.executable, str(HERE / "ws74_construct.py"), "--run-all",
                  "--rundir", str(rundir_b)], timeout=3600)
        print(out.stdout[-2000:] if out.stdout else "")
        if out.returncode != 0:
            print(out.stderr[-2000:] if out.stderr else "")
            raise RuntimeError("WS74_DETERMINISM_RERUN_CONSTRUCT_FAILED")
        print("== determinism rerun: normalization")
        out = sh([sys.executable, str(HERE / "ws74_normalize.py"), "--rundir", str(rundir_b),
                  "--outdir", str(normdir_b)], timeout=1200)
        print(out.stdout[-2000:] if out.stdout else "")
        if out.returncode != 0:
            print(out.stderr[-2000:] if out.stderr else "")
            raise RuntimeError("WS74_DETERMINISM_RERUN_NORMALIZE_FAILED")

    rundir_a = Path(args.rundir_a)
    normdir_a = Path(args.normdir_a)
    mismatches = []
    checked = 0
    for rp in sorted(rundir_a.glob("*.json")):
        if rp.name.startswith("harness-"):
            continue
        fid = rp.stem
        rb_b = rundir_b / (rp.name)
        if not rb_b.exists():
            mismatches.append({"fixture_id": fid, "kind": "MISSING_IN_RERUN"})
            continue
        ra = json.loads(rp.read_text())
        rbb = json.loads(rb_b.read_text())
        ca_ = ra.get("construction", {})
        cb_ = rbb.get("construction", {})
        for key in ("result", "code"):
            if ca_.get(key) != cb_.get(key):
                mismatches.append({"fixture_id": fid, "kind": "CONSTRUCTION_" + key,
                                   "a": ca_.get(key), "b": cb_.get(key)})
        for key in ("requested_object_count", "placed_object_count", "player_count"):
            if ca_.get(key) != cb_.get(key):
                mismatches.append({"fixture_id": fid, "kind": "CONSTRUCTION_" + key,
                                   "a": ca_.get(key), "b": cb_.get(key)})
        if len(ca_.get("failed_placements", [])) != len(cb_.get("failed_placements", [])):
            mismatches.append({"fixture_id": fid, "kind": "FAILED_COUNT"})
        else:
            for fa, fb in zip(ca_.get("failed_placements", []), cb_.get("failed_placements", [])):
                if fa.get("semantic_id") != fb.get("semantic_id") or fa.get("code") != fb.get("code"):
                    mismatches.append({"fixture_id": fid, "kind": "FAILED_ENTRY"})
                    break
        if len(ca_.get("placement_ledger", [])) != len(cb_.get("placement_ledger", [])):
            mismatches.append({"fixture_id": fid, "kind": "LEDGER_COUNT"})
        else:
            for fa, fb in zip(ca_.get("placement_ledger", []), cb_.get("placement_ledger", [])):
                if fa.get("semantic_id") != fb.get("semantic_id") or fa.get("zone") != fb.get("zone"):
                    mismatches.append({"fixture_id": fid, "kind": "LEDGER_ENTRY"})
                    break
        # startup passes: deterministic offsets/actors/kinds (no volatile IDs)
        if ca_.get("startup_passes") != cb_.get("startup_passes"):
            mismatches.append({"fixture_id": fid, "kind": "STARTUP_PASSES"})
        ga, gb = ra.get("game", {}), rbb.get("game", {})
        for key in ("turn_number", "phase", "step", "active_seat", "priority_seat",
                    "player_count", "paused", "ended"):
            if ga.get(key) != gb.get(key):
                mismatches.append({"fixture_id": fid, "kind": "GAME_" + key,
                                   "a": ga.get(key), "b": gb.get(key)})
        checked += 1
    # normalized projections: byte-identical
    for np in sorted((normdir_a / "normalized").glob("*.json")):
        fid = np.stem
        nb = normdir_b / "normalized" / np.name
        if not nb.exists():
            mismatches.append({"fixture_id": fid, "kind": "NORMALIZED_MISSING_IN_RERUN"})
            continue
        ha = hashlib.sha256(np.read_bytes()).hexdigest()
        hb = hashlib.sha256(nb.read_bytes()).hexdigest()
        if ha != hb:
            mismatches.append({"fixture_id": fid, "kind": "NORMALIZED_BYTES_DIFFER"})
        checked += 1
    for name, blob in backups.items():
        (HERE / name).write_bytes(blob)
    if args.spots:
        import ws74_normalize as NZ
        by_id, _ids = NZ.load_contract()
        for fid in ("HIDDEN_01", "MICRO_COPY", "WS05-CMD-DMG-SPLIT"):
            srun = HERE / ".scratch" / ("spot-" + fid)
            snorm = HERE / ".scratch" / ("spot-norm-" + fid)
            print("== isolated spot check: %s" % fid)
            out = sh([sys.executable, str(HERE / "ws74_construct.py"), "--only", fid,
                      "--rundir", str(srun)], timeout=1800)
            if out.returncode != 0:
                print(out.stdout[-1500:] if out.stdout else "")
                print(out.stderr[-1500:] if out.stderr else "")
                raise RuntimeError("WS74_SPOT_CONSTRUCT_FAILED:%s" % fid)
            rb = json.loads((srun / (fid + ".json")).read_text())
            result, code, digest, _p, _d, _c, _e = NZ.adjudicate_one(by_id[fid], rb)
            # canonical comparison: normalized digest + classification
            cfile = normdir_a / "normalized" / (fid + ".json")
            if not cfile.exists():
                mismatches.append({"fixture_id": fid, "kind": "SPOT_CANONICAL_MISSING"})
                continue
            canon = json.loads(cfile.read_text())
            if canon.get("normalized_digest") != digest:
                mismatches.append({"fixture_id": fid, "kind": "SPOT_DIGEST_DIFFER",
                                   "a": canon.get("normalized_digest"), "b": digest})
            else:
                print("   spot %s isolated==sequential digest=%s" % (fid, str(digest)[:16]))
    for name, blob in backups.items():
        (HERE / name).write_bytes(blob)
    verdict = "PASS" if not mismatches else "FAIL"
    payload = {
        "schema": "ws74.staging-determinism.v1",
        "evidence_class": "CODE_DERIVED",
        "runs": {"a_rundir": str(rundir_a), "b_rundir": str(rundir_b)},
        "checked_artifacts": checked,
        "mismatches": mismatches[:50],
        "mismatch_count": len(mismatches),
        "verdict": verdict,
    }
    (HERE / "STAGING_DETERMINISM.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print("STAGING_DETERMINISM=%s checked=%d mismatches=%d" % (verdict, checked, len(mismatches)))
    for m in mismatches[:15]:
        print("  ", m)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
