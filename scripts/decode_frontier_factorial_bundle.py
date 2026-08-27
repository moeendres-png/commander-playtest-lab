from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import tarfile
from pathlib import Path

GZIP_SHA256 = "b76485c5bdbf894c5c2a31e2221e0c7491ecc83c7745c2716eabe5a3c11c25c3"
TAR_SHA256 = "72900651e3d617bf96b7b8ed923b9e9971f8d3f86fe4494499abeb0508f46b79"
CANDIDATE_SHA256 = "7aed9d6ddc4ef6a580c10544aa4a313e761c1d6320f9b145c0229a7ecb7e3f2d"
DECISION_SHA256 = "c181cfe70e08a26b2c123ff9f1662ba1dd1d1908b9ac4426091bc06f041fb04c"
ALLOWED = {
    "input/CANDIDATES_29.json",
    "input/DECISION_CONTRACT.json",
    "input/PHYSICAL_EVIDENCE.json",
    "input/PRIOR_STRUCTURAL_SEEDS.json",
    "scripts/generate_frontier_factorial_schedule.py",
    "scripts/preflight_frontier_factorial.py",
    "scripts/run_frontier_factorial_block.py",
    "scripts/aggregate_frontier_factorial.py",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    bundle = Path(args.bundle)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    gzip_bytes = base64.b64decode(bundle.read_text(encoding="utf-8").strip())
    if hashlib.sha256(gzip_bytes).hexdigest() != GZIP_SHA256:
        raise SystemExit("campaign gzip hash mismatch")
    tar_bytes = gzip.decompress(gzip_bytes)
    if hashlib.sha256(tar_bytes).hexdigest() != TAR_SHA256:
        raise SystemExit("campaign tar hash mismatch")

    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        if {member.name for member in members} != ALLOWED:
            raise SystemExit("campaign bundle member set mismatch")
        for member in members:
            target = (output / member.name).resolve()
            if not target.is_relative_to(output):
                raise SystemExit("unsafe campaign bundle path")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise SystemExit(f"cannot extract {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(extracted.read())

    candidate_path = output / "input/CANDIDATES_29.json"
    decision_path = output / "input/DECISION_CONTRACT.json"
    if hashlib.sha256(candidate_path.read_bytes()).hexdigest() != CANDIDATE_SHA256:
        raise SystemExit("candidate payload hash mismatch")
    if hashlib.sha256(decision_path.read_bytes()).hexdigest() != DECISION_SHA256:
        raise SystemExit("decision contract hash mismatch")
    print("FRONTIER_FACTORIAL_CAMPAIGN_BUNDLE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
