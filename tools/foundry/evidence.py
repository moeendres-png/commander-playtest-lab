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
import os
import stat
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

VERDICTS = ("PASS", "FAIL", "UNKNOWN", "NOT_RUN", "PARTIAL")


class ArtifactIndexError(ValueError):
    """Incomplete or unstable inputs cannot produce an artifact manifest."""


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _snapshot(path: Path) -> tuple[int, str]:
    """Bind size and hash to one regular-file descriptor; reject observed drift."""
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ArtifactIndexError("artifact is no longer a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as handle:
        opened = os.fstat(handle.fileno())
        if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
            raise ArtifactIndexError("artifact changed before reading")
        digest = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: handle.read(65536), b""):
            size += len(chunk)
            digest.update(chunk)
        if (
            size != opened.st_size
            or _identity(opened) != _identity(os.fstat(handle.fileno()))
            or _identity(opened) != _identity(path.lstat())
        ):
            raise ArtifactIndexError("artifact changed while reading; stop its writer and retry")
    return size, digest.hexdigest()


def sha256_of(path: Path) -> str:
    return _snapshot(path)[1]


def artifact_index(
    roots: list[str],
    run: str = "UNKNOWN",
    source_sha: str = "UNKNOWN",
    patterns: tuple[str, ...] = ("*",),
    *,
    exclude: tuple[str, ...] = (),
) -> dict:
    if not roots or not patterns:
        raise ArtifactIndexError("at least one existing directory and pattern are required")
    if any(not p or Path(p).is_absolute() or ".." in Path(p).parts for p in patterns):
        raise ArtifactIndexError("patterns must be relative and cannot traverse parents")
    entries = []
    seen: set[Path] = set()
    excluded = {Path(p).resolve() for p in exclude}

    def traversal_error(_error: OSError) -> None:
        raise ArtifactIndexError("directory traversal failed; verify input access")

    try:
        bases = []
        for root in roots:
            base = Path(root)
            if base.is_symlink() or not base.is_dir():
                raise ArtifactIndexError("each root must be an existing non-symlink directory")
            bases.append(base.resolve(strict=True))
        for base in sorted(set(bases)):
            # Keep pathlib's existing rglob semantics (including zero-depth **).
            # os.walk below independently makes traversal errors explicit.
            matched = {path for pattern in patterns for path in base.rglob(pattern)}
            for directory, dirs, files in os.walk(base, onerror=traversal_error, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
                for name in sorted(files):
                    path = Path(directory) / name
                    if path.is_symlink() or path not in matched:
                        continue
                    if path in seen or path in excluded:
                        continue
                    seen.add(path)
                    size, digest = _snapshot(path)
                    entries.append(
                        {
                            "name": name,
                            "path": str(path),
                            "size": size,
                            "sha256": digest,
                            "run": run,
                            "source_sha": source_sha,
                        }
                    )
    except OSError as exc:
        raise ArtifactIndexError("artifact input unavailable; verify access and retry") from exc
    entries.sort(key=lambda e: e["path"])
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "run": run,
        "source_sha": source_sha,
        "artifacts": entries,
    }


def _write_manifest(output: Path, text: str) -> None:
    """Publish only a complete manifest, replacing the prior file atomically."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent, prefix=".artifact-index-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
        try:
            output = Path(args.output).absolute() if args.output else None
            if output is not None and output.is_symlink():
                raise ArtifactIndexError("output cannot be a symlink")
            payload = artifact_index(
                args.root,
                args.run,
                args.source_sha,
                exclude=(str(output),) if output is not None else (),
            )
            text = json.dumps(payload, indent=2, sort_keys=True)
            if output is not None:
                _write_manifest(output, text)
            else:
                print(text)
        except (ArtifactIndexError, OSError):
            print(
                "ARTIFACT_INDEX_FAIL: incomplete, unstable, or inaccessible input/output; verify paths and stop artifact writers before retrying",
                file=sys.stderr,
            )
            return 1
        return 0
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
