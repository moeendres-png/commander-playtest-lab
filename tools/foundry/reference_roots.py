"""Declared external reference-root contract (read-only engine sources).

WS75: production-reachable reads of exact Forge/XMage source checkouts go
through a first-class declared contract instead of ad-hoc ``git -C`` or
sibling-worktree probing. A declared reference binds exactly:

- label: short stable handle (e.g. ``forge``);
- root: absolute path of the checkout root;
- repo_slug: expected ``owner/repo`` remote identity;
- commit: expected exact 40-hex HEAD;
- tree: expected exact 40-hex ``HEAD^{tree}``;
- cleanliness: ``clean`` (no dirty or ignored residue) or
  ``allow-ignored-build-outputs`` (ignored files may exist; every
  non-ignored path must still be clean);
- intent: always ``read-only`` (verification performs read-only git
  commands only, with the checkout as the command CWD; ``git -C`` is
  never used).

Bootstrap verifies every declared reference before launch and fails
closed on the first mismatch. The launcher exposes the verified list to
Muse (no secrets: every field is a path/identity, never a credential)
with the standing rule: use the command CWD inside the reference root
plus ordinary read-only git commands; never mutate reference sources.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REQUIRED_KEYS = ("label", "root", "repo_slug", "commit", "tree", "cleanliness", "intent")
CLEANLINESS_POLICIES = ("clean", "allow-ignored-build-outputs")
READ_ONLY_INTENT = "read-only"

_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class ReferenceError(ValueError):
    """Malformed reference declaration (caller error, not a repo state)."""


def _run_git(args: list[str], root: str) -> str:
    """Run a read-only git command with the reference root as CWD.

    The checkout directory itself is the command working directory; this
    module never uses ``git -C`` (which stays DENY in the permission
    lock) and never runs a mutating git command.
    """
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def parse_spec(raw: str) -> dict:
    """Parse one ``--reference`` JSON declaration; raises ReferenceError."""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ReferenceError(f"reference is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ReferenceError("reference must be a JSON object")
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise ReferenceError(f"reference missing keys: {missing}")
    extra = sorted(set(data) - set(REQUIRED_KEYS))
    if extra:
        raise ReferenceError(f"reference has unknown keys: {extra}")
    label = data["label"]
    if not isinstance(label, str) or not label.strip() or any(c in label for c in " /\\"):
        raise ReferenceError(f"bad label {label!r} (non-empty, no whitespace/slashes)")
    root = data["root"]
    if not isinstance(root, str) or not os.path.isabs(root):
        raise ReferenceError(f"root must be absolute: {root!r}")
    if not isinstance(data["repo_slug"], str) or "/" not in data["repo_slug"]:
        raise ReferenceError(f"bad repo_slug {data.get('repo_slug')!r} (want owner/repo)")
    for key in ("commit", "tree"):
        value = data[key]
        if not isinstance(value, str) or not _HEX40.match(value):
            raise ReferenceError(f"bad {key} {value!r} (want 40-hex)")
    if data["cleanliness"] not in CLEANLINESS_POLICIES:
        raise ReferenceError(
            f"bad cleanliness {data.get('cleanliness')!r} (want one of {CLEANLINESS_POLICIES})"
        )
    if data["intent"] != READ_ONLY_INTENT:
        raise ReferenceError(f"intent must be {READ_ONLY_INTENT!r} (references are read-only)")
    return {k: data[k] for k in REQUIRED_KEYS}


def verify(ref: dict) -> list[str]:
    """Verify a parsed reference against live checkout state.

    Returns a list of failure reasons; empty means VERIFIED. Read-only:
    only ``rev-parse``/``config``/``status`` git commands run, with the
    reference root as CWD.
    """
    failures: list[str] = []
    root = os.path.realpath(ref["root"])
    if not Path(root).is_dir():
        return [f"reference {ref['label']!r}: root not a directory: {ref['root']!r}"]
    try:
        toplevel = os.path.realpath(_run_git(["rev-parse", "--show-toplevel"], root))
    except RuntimeError as exc:
        return [f"reference {ref['label']!r}: not a git checkout: {exc}"]
    if toplevel != root:
        failures.append(
            f"reference {ref['label']!r}: root {root!r} is not the checkout toplevel ({toplevel!r})"
        )
    try:
        url = _run_git(["config", "--get", "remote.origin.url"], root)
    except RuntimeError:
        url = ""
    if ref["repo_slug"] not in url:
        failures.append(
            f"reference {ref['label']!r}: remote identity lacks slug {ref['repo_slug']!r}"
        )
    try:
        head = _run_git(["rev-parse", "HEAD"], root)
    except RuntimeError as exc:
        return [*failures, f"reference {ref['label']!r}: cannot read HEAD: {exc}"]
    if head != ref["commit"]:
        failures.append(
            f"reference {ref['label']!r}: HEAD {head[:12]} != expected {ref['commit'][:12]}"
        )
    try:
        tree = _run_git(["rev-parse", "HEAD^{tree}"], root)
    except RuntimeError as exc:
        failures.append(f"reference {ref['label']!r}: cannot read tree: {exc}")
        tree = ""
    if tree and tree != ref["tree"]:
        failures.append(
            f"reference {ref['label']!r}: tree {tree[:12]} != expected {ref['tree'][:12]}"
        )
    try:
        porcelain = _run_git(["status", "--porcelain"], root)
    except RuntimeError as exc:
        return [*failures, f"reference {ref['label']!r}: cannot read status: {exc}"]
    if porcelain:
        failures.append(
            f"reference {ref['label']!r}: dirty ({len(porcelain.splitlines())} entries; "
            "reference sources are read-only)"
        )
    elif ref["cleanliness"] == "clean":
        try:
            ignored = _run_git(["status", "--porcelain", "--ignored"], root)
        except RuntimeError as exc:
            return [*failures, f"reference {ref['label']!r}: cannot read ignored state: {exc}"]
        residue = [line for line in ignored.splitlines() if line.startswith("!!")]
        if residue:
            failures.append(
                f"reference {ref['label']!r}: {len(residue)} ignored build-output "
                "entries under strict clean policy"
            )
    return failures


def format_context(refs: list[dict]) -> str:
    """Human-readable runtime context block (no secrets: identities only)."""
    lines = [
        "Declared read-only reference roots (verified at bootstrap; do not mutate):",
    ]
    for ref in refs:
        lines.append(
            f"- {ref['label']}: root={ref['root']} slug={ref['repo_slug']} "
            f"commit={ref['commit'][:12]} tree={ref['tree'][:12]} "
            f"cleanliness={ref['cleanliness']} intent=read-only"
        )
    lines.append(
        "Rules: work with the reference root as your command CWD using ordinary "
        "read-only git commands (status/log/show/ls-files/ls-tree/rev-parse); "
        "never use `git -C`; never write into a reference root; ignored build "
        "outputs are observable only when the declared cleanliness explicitly "
        "allows them."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Verify declared reference roots (read-only).")
    parser.add_argument(
        "--reference", action="append", default=[], help="JSON reference declaration (repeatable)."
    )
    args = parser.parse_args(argv)
    if not args.reference:
        print("REFERENCE_CHECK: no references declared")
        return 0
    failed = False
    for raw in args.reference:
        try:
            ref = parse_spec(raw)
        except ReferenceError as exc:
            print(f"REFERENCE_FAIL: {exc}")
            failed = True
            continue
        reasons = verify(ref)
        if reasons:
            for reason in reasons:
                print(f"REFERENCE_FAIL: {reason}")
            failed = True
        else:
            print(f"REFERENCE_OK: {ref['label']} {ref['root']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
