"""Failure clustering helper.

Groups structured failure records by normalized signature while preserving
original record IDs and raw evidence references. Clustering assists reasoning
only: it never assigns root cause and never promotes anything to PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HEX_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
PATH_RE = re.compile(r"(?:/[\w.\-]+)+")
TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?")


def normalize(message: str) -> str:
    """Reduce a raw message to a stable clustering signature."""
    sig = TS_RE.sub("<ts>", message)
    sig = PATH_RE.sub("<path>", sig)
    sig = HEX_RE.sub("<sha>", sig)
    sig = NUM_RE.sub("<n>", sig)
    sig = re.sub(r"\s+", " ", sig).strip().lower()
    return sig


def cluster(records: list[dict]) -> list[dict]:
    """Group records; each cluster keeps member IDs and evidence refs."""
    groups: dict[str, dict] = {}
    for record in records:
        message = str(record.get("message", ""))
        signature = normalize(message)
        digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
        bucket = groups.setdefault(
            digest,
            {"signature": signature, "count": 0, "members": []},
        )
        bucket["count"] += 1
        bucket["members"].append(
            {
                "id": record.get("id"),
                "evidence": record.get("evidence"),
                "verdict": record.get("verdict", "UNKNOWN"),
            }
        )
    return sorted(groups.values(), key=lambda g: (-g["count"], g["signature"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cluster failure records by signature.")
    parser.add_argument("--input", required=True, help="JSON array of failure records.")
    parser.add_argument("--output", default=None, help="Write clusters JSON here.")
    args = parser.parse_args(argv)
    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise SystemExit("input must be a JSON array of records")
    text = json.dumps({"clusters": cluster(records)}, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
