"""Failure clustering helper.

Groups structured failure records by normalized signature while preserving
original record IDs and raw evidence references. Clustering assists reasoning
only: it never assigns root cause and never promotes anything to PASS.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
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
    if not isinstance(records, list):
        raise ValueError("input must be a JSON array of records")
    identities: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record {index}: expected an object")
        for field in ("id", "message", "evidence"):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"record {index}: missing or invalid {field}")
        identity = record["id"]
        if identity != identity.strip():
            raise ValueError(f"record {index}: surrounding whitespace in id")
        if identity in identities:
            raise ValueError(f"record {index}: duplicate id; provide distinct failure identities")
        identities.add(identity)
        verdict = record.get("verdict", "UNKNOWN")
        if not isinstance(verdict, str) or not verdict.strip():
            raise ValueError(f"record {index}: invalid verdict")
    groups: dict[str, dict] = {}
    for record in records:
        signature = normalize(record["message"])
        # The actual signature is the grouping authority, not a truncated digest.
        bucket = groups.setdefault(
            signature,
            {"signature": signature, "count": 0, "members": []},
        )
        bucket["count"] += 1
        bucket["members"].append(
            {
                "id": record["id"],
                "evidence": record["evidence"],
                "verdict": record.get("verdict", "UNKNOWN"),
            }
        )
    for bucket in groups.values():
        bucket["members"].sort(key=lambda member: member["id"])
    return sorted(groups.values(), key=lambda g: (-g["count"], g["signature"]))


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("non-finite JSON constant")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cluster failure records by signature.")
    parser.add_argument("--input", required=True, help="JSON array of failure records.")
    parser.add_argument("--output", default=None, help="Write clusters JSON here.")
    args = parser.parse_args(argv)
    try:
        records = json.loads(
            Path(args.input).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_keys,
            parse_constant=_invalid_constant,
        )
    except (OSError, ValueError, RecursionError):
        print("CLUSTER_INVALID: cannot read valid records JSON", file=sys.stderr)
        return 1
    try:
        result = cluster(records)
    except ValueError as exc:
        print(f"CLUSTER_INVALID: {exc}", file=sys.stderr)
        return 1
    text = json.dumps({"clusters": result}, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        temporary: str | None = None
        try:
            target = Path(args.output)
            if target.exists() and target.samefile(args.input):
                print("CLUSTER_INVALID: output aliases input evidence", file=sys.stderr)
                return 1
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=target.parent,
                prefix=".failure-clusters-",
                delete=False,
            ) as stream:
                temporary = stream.name
                stream.write(text + "\n")
            os.replace(temporary, target)
        except OSError:
            print("CLUSTER_INVALID: cannot publish output", file=sys.stderr)
            return 1
        finally:
            if temporary is not None:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    print("CLUSTER_WARNING: temporary-file cleanup failed", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
