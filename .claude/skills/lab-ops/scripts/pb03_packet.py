#!/usr/bin/env python3
"""Fetch a PB-03 run's current-boundary packet and summarize it in a few lines.

    pb03_packet.py RUN_ID OUT_DIR [--repo O/R] [--into LAB_ROOT]

Downloads the run's ``current-boundary-two-candidate-*`` artifact to OUT_DIR,
prints the epoch identity, verifies CURRENT_BOUNDARY_SHA256SUMS against the
packet, and prints the FULL107 counts and every AF00-AF11 gate verdict per
candidate with its blocking rows. With --into, the packet is also copied to
LAB_ROOT/<epoch_root> (the sealing layout); run
``python scripts/regenerate_hash_manifests.py`` afterwards.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def gh(path: str) -> bytes:
    out = subprocess.run(["gh", "api", path], capture_output=True, check=False)
    if out.returncode != 0:
        raise SystemExit(f"gh api {path}: {out.stderr.decode().strip()}")
    return out.stdout


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("run_id")
    p.add_argument("out_dir", type=Path)
    p.add_argument("--repo", default="moeendres-png/commander-playtest-lab")
    p.add_argument("--into", type=Path)
    a = p.parse_args()

    artifacts = json.loads(gh(f"repos/{a.repo}/actions/runs/{a.run_id}/artifacts"))["artifacts"]
    packet = [x for x in artifacts if x["name"].startswith("current-boundary-two-candidate-")]
    if len(packet) != 1:
        raise SystemExit(
            f"expected one current-boundary packet, found {[x['name'] for x in artifacts]}"
        )
    if a.out_dir.exists():
        shutil.rmtree(a.out_dir)
    zipfile.ZipFile(
        io.BytesIO(gh(f"repos/{a.repo}/actions/artifacts/{packet[0]['id']}/zip"))
    ).extractall(a.out_dir)

    identity = json.loads((a.out_dir / "EPOCH_IDENTITY.json").read_text())
    source = identity["producing_source"]
    print(
        f"epoch {identity['epoch_id']} root={identity['epoch_root']} "
        f"source={source['branch']}@{source['commit'][:12]} tree={source['tree'][:12]}"
    )

    prefix = identity["epoch_root"].rstrip("/") + "/"
    bad = 0
    sums = (a.out_dir / "CURRENT_BOUNDARY_SHA256SUMS").read_text().splitlines()
    for line in sums:
        digest, name = line.split(None, 1)
        local = a.out_dir / name.strip().removeprefix(prefix)
        if not local.is_file() or hashlib.sha256(local.read_bytes()).hexdigest() != digest:
            bad += 1
    print(f"sha256sums: {len(sums) - bad}/{len(sums)} verified")

    for cand in ("XMAGE", "FORGE"):
        path = a.out_dir / f"AF00_AF11_{cand}.json"
        if not path.is_file():
            print(f"{cand}: no AF matrix")
            continue
        doc = json.loads(path.read_text())
        print(f"{cand} FULL107 {json.dumps(doc['full107_counts'], sort_keys=True)}")
        for gate in doc["gates"]:
            rows = gate.get("blocking_rows") or []
            shown = ",".join(rows[:6]) + (f",+{len(rows) - 6}" if len(rows) > 6 else "")
            print(f"  {gate['gate']} {gate['verdict']} blocking={len(rows)} {shown}")

    if a.into:
        target = a.into / identity["epoch_root"]
        if target.exists():
            raise SystemExit(f"{target} already exists; an epoch is sealed once")
        shutil.copytree(a.out_dir, target)
        print(f"copied into {target}")
    return None


if __name__ == "__main__":
    sys.exit(main())
