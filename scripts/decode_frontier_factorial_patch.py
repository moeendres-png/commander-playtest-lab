from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import tarfile
from pathlib import Path

GZIP_SHA256 = "84f985886535e02a621b1d9031d4a55e3b19189646fec1c17f509e7e818880b1"
TAR_SHA256 = "553a1d5efa1f6e370442ae2ce34dc2ef4dba0ac6c51b3ad5041b305d49b1f919"
CANDIDATE_SHA256 = "61d3373e12d7a08c94b76d02ea608dbf6c59f29c97e9344760f4949fd1504f43"
ALLOWED = {
    "input/CANDIDATES_29.json",
    "input/DECISION_CONTRACT_118784.json",
    "input/PHYSICAL_EVIDENCE_29.json",
    "scripts/aggregate_rogshai_frontier_factorial.py",
    "scripts/generate_rogshai_frontier_factorial_schedule.py",
    "scripts/run_rogshai_frontier_factorial_block.py",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    gzip_bytes = base64.b64decode(Path(args.bundle).read_text(encoding="utf-8").strip())
    assert hashlib.sha256(gzip_bytes).hexdigest() == GZIP_SHA256
    tar_bytes = gzip.decompress(gzip_bytes)
    assert hashlib.sha256(tar_bytes).hexdigest() == TAR_SHA256
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        assert {member.name for member in members} == ALLOWED
        for member in members:
            target = (output / member.name).resolve()
            assert target.is_relative_to(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = archive.extractfile(member)
            assert extracted is not None
            target.write_bytes(extracted.read())
    candidate_path = output / "input/CANDIDATES_29.json"
    assert hashlib.sha256(candidate_path.read_bytes()).hexdigest() == CANDIDATE_SHA256
    print("FRONTIER_FACTORIAL_PATCH=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
