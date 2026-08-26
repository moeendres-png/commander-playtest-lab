from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import tarfile
from pathlib import Path

GZIP_SHA256 = "f28fc3bb95fc2d1bc0226a406de774fde204c45d14fe394296fe6e5de2a3db83"
TAR_SHA256 = "5ba2404282afd0dc170bb0d664a185dc957d6aff15e418cddcb9e7fade2955c4"
CANDIDATE_SHA256 = "d9d37611cca81f5a2ff3149c473a125bf52fc420b01ccc0a123713b4a37d2884"
ALLOWED = {
    "input/CANDIDATES_20.json",
    "scripts/generate_arch_frontier_schedule.py",
    "scripts/run_arch_frontier_block.py",
    "scripts/aggregate_arch_frontier.py",
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

    candidate_path = output / "input/CANDIDATES_20.json"
    assert hashlib.sha256(candidate_path.read_bytes()).hexdigest() == CANDIDATE_SHA256
    print("CAMPAIGN_BUNDLE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
