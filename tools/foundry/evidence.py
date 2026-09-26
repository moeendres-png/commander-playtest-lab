"""Artifact index and evidence-reporter helpers.

`artifact-index` writes a deterministic manifest (file name, path, size,
SHA-256, producing run/test, source SHA). `report` emits the required
handoff/evidence skeleton with missing results left UNKNOWN or absent —
never fabricated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

VERDICTS = ("PASS", "FAIL", "UNKNOWN", "NOT_RUN", "PARTIAL")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_index(
    roots: list[str],
    run: str = "UNKNOWN",
    source_sha: str = "UNKNOWN",
    patterns: tuple[str, ...] = ("*",),
) -> dict:
    entries = []
    for root in roots:
        base = Path(root)
        for pattern in patterns:
            for path in sorted(base.rglob(pattern)):
                if not path.is_file() or path.is_symlink():
                    continue
                stat = path.stat()
                entries.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size": stat.st_size,
                        "sha256": sha256_of(path),
                        "run": run,
                        "source_sha": source_sha,
                    }
                )
    entries.sort(key=lambda e: e["path"])
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "run": run,
        "source_sha": source_sha,
        "artifacts": entries,
    }


def handoff_skeleton(
    workstream: str,
    source_lock: dict,
    results: list[dict] | None = None,
) -> dict:
    sections = {
        "workstream": workstream,
        "source_lock": source_lock,
        "work_completed": [],
        "new_findings": [],
        "changes": [],
        "tests_evidence": [],
        "verdicts": {},
        "remaining_blockers": [],
        "outputs": [],
        "dependencies_unblocked": [],
        "exact_next_action": "UNKNOWN",
    }
    for item in results or []:
        verdict = item.get("verdict", "UNKNOWN")
        if verdict not in VERDICTS:
            verdict = "UNKNOWN"
        entry = dict(item)
        entry["verdict"] = verdict
        sections["tests_evidence"].append(entry)
    return sections


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Foundry artifact index and evidence reporter.")
    sub = parser.add_subparsers(dest="command", required=True)
    idx = sub.add_parser("artifact-index", help="Write a deterministic artifact manifest.")
    idx.add_argument("--root", action="append", default=[], help="Directory to index (repeatable).")
    idx.add_argument("--run", default="UNKNOWN")
    idx.add_argument("--source-sha", default="UNKNOWN")
    idx.add_argument("--output", default=None)
    rep = sub.add_parser("report", help="Emit the handoff/evidence skeleton.")
    rep.add_argument("--workstream", required=True)
    rep.add_argument("--source-lock", required=True, help="JSON object with source identity.")
    rep.add_argument("--results", default=None, help="JSON array of result objects.")
    rep.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    if args.command == "artifact-index":
        if not args.root:
            raise SystemExit("--root is required at least once")
        payload = artifact_index(args.root, args.run, args.source_sha)
    else:
        results = json.loads(Path(args.results).read_text(encoding="utf-8")) if args.results else []
        payload = handoff_skeleton(args.workstream, json.loads(args.source_lock), results)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
