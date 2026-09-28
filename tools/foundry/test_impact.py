"""Deterministic changed-surface to test-surface mapper (advisory, conservative).

Maps files changed since a base commit to the minimum required tests plus
relevant regression sets, with a reason per file. Rules:

- docs-only prose changes require no tests (stated, not assumed);
- operating-layer code maps to its test module, or the whole tests/foundry/
  dir when no dedicated module exists;
- opencode.json / agent / skill changes additionally require the MANUAL
  battery re-run against CLI-resolved rules (pattern matching alone cannot
  prove resolution order);
- state/schema/profile changes require their validator + module tests;
- anything outside the known operating-layer surface (src/**, engine
  bridges, qualification rigs, vendor, unknown paths) is UNCERTAIN and maps
  to the full suite with requalification_required=true.

This tool NEVER authorizes skipping a contract-required test: every output
carries the contract-override reminder, and contract suites are always
included in `minimum`. Impact adjudication stays a technical decision recorded
by the caller; changing what counts as qualification credit remains an
AUTHORITY_GATE.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FULL_FOUNDRY_SUITE = "pytest tests/foundry/ -q"
CONTRACT_OVERRIDE = (
    "Contract-required tests always run regardless of this mapping; "
    "a green subset never qualifies an unrun surface."
)

# (prefix, minimum tests, regression, manual steps, reason)
RULES: list[tuple[str, list[str], list[str], list[str], str]] = [
    (
        "opencode.json",
        [FULL_FOUNDRY_SUITE],
        [FULL_FOUNDRY_SUITE],
        ["permission battery vs pinned-CLI resolved rules (resolution order is runtime truth)"],
        "permission/model/effort lock changed",
    ),
    (
        ".opencode/agents/",
        [FULL_FOUNDRY_SUITE],
        [FULL_FOUNDRY_SUITE],
        ["permission battery vs pinned-CLI resolved rules"],
        "agent permission/model/variant surface changed",
    ),
    (
        ".opencode/skills/",
        ["pytest tests/foundry/test_foundry_tools.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "skill structural conformance is pinned by tests",
    ),
    (
        "tools/foundry/source_lock.py",
        ["pytest tests/foundry/test_foundry_tools.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "source-lock module maps to its tool tests",
    ),
    (
        "tools/foundry/state.py",
        ["pytest tests/foundry/test_state_v2.py tests/foundry/test_foundry_tools.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "state semantics map to schema/migration/ancestry tests",
    ),
    (
        "tools/foundry/writer_lock.py",
        ["pytest tests/foundry/test_writer_lock.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "lock module maps to its concurrency battery",
    ),
    (
        "tools/foundry/safe_push.py",
        ["pytest tests/foundry/test_safe_push.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "push wrapper maps to its adversarial battery",
    ),
    (
        "tools/foundry/permission_battery.py",
        ["pytest tests/foundry/test_foundry_tools.py -q"],
        [FULL_FOUNDRY_SUITE],
        ["permission battery vs pinned-CLI resolved rules"],
        "battery logic changed; re-prove against live resolution",
    ),
    (
        "tools/foundry/drift_check.py",
        ["pytest tests/foundry/test_drift.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "drift checker maps to its fixture + live-read tests",
    ),
    (
        "tools/foundry/bootstrap.py",
        ["pytest tests/foundry/test_launcher.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "bootstrap gate maps to launcher/bootstrap tests",
    ),
    (
        "tools/foundry/launcher.py",
        ["pytest tests/foundry/test_launcher.py -q"],
        [FULL_FOUNDRY_SUITE],
        ["launcher init dry-run for cpl/mage/forge profiles"],
        "launcher maps to its test suite plus profile smoke",
    ),
    (
        "tools/foundry/metrics.py",
        ["pytest tests/foundry/test_foundry_tools.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "metrics schema maps to tool tests",
    ),
    (
        "tools/foundry/opencode_cli_version.py",
        ["pytest tests/foundry/test_ws75_tooling_hardening.py -q"],
        [FULL_FOUNDRY_SUITE],
        ["launcher init dry-run for cpl/mage/forge profiles"],
        "CLI version pin maps to WS75 hardening tests",
    ),
    (
        "tools/foundry/reference_roots.py",
        ["pytest tests/foundry/test_ws75_tooling_hardening.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "reference-root contract maps to WS75 hardening tests",
    ),
    (
        "tools/foundry/session_stats.py",
        ["pytest tests/foundry/test_telemetry.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "session-stats parser maps to its shape tests",
    ),
    (
        "tests/foundry/",
        [FULL_FOUNDRY_SUITE],
        [FULL_FOUNDRY_SUITE],
        [],
        "test change requires the suite it belongs to",
    ),
    (
        ".foundry/repo-profiles/",
        ["pytest tests/foundry/test_drift.py -q"],
        [FULL_FOUNDRY_SUITE],
        [],
        "profile/marker change maps to drift tests",
    ),
    (
        ".foundry/WORKSTREAM_STATE.schema.json",
        ["pytest tests/foundry/test_state_v2.py -q"],
        [FULL_FOUNDRY_SUITE],
        ["state.py --state on the live workstream file"],
        "schema change maps to validator tests plus live validation",
    ),
]


KNOWN_TOP_DIRS = ("tools", "tests", ".foundry", ".opencode", "docs", ".github")


GIT_TIMEOUT_SECONDS = 15


def _git(args: list[str], cwd: str) -> bytes:
    """No partial evidence or raw Git diagnostics escape a failed command."""
    operation = args[0]
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise ValueError(
            f"Git {operation} unavailable ({type(exc).__name__}); inspect the checkout and retry"
        ) from exc
    if proc.returncode != 0:
        raise ValueError(
            f"Git {operation} failed (exit {proc.returncode}); no impact plan produced"
        )
    return proc.stdout


def _commit(workdir: str, ref: str) -> str:
    raw = _git(["rev-parse", "--verify", "--end-of-options", ref + "^{commit}"], workdir)
    if not re.fullmatch(rb"(?:[0-9a-f]{40}|[0-9a-f]{64})\n", raw):
        raise ValueError("Git returned an invalid commit identity; no impact plan produced")
    return raw[:-1].decode("ascii")


def _paths(raw: bytes) -> set[str]:
    if not raw:
        return set()
    if not raw.endswith(b"\0"):
        raise ValueError("Git path output lacks NUL framing; no impact plan produced")
    paths = set()
    for record in raw[:-1].split(b"\0"):
        # Surrogate escapes retain otherwise undecodable Git pathname bytes in JSON.
        path = record.decode("utf-8", errors="surrogateescape")
        if not path or any(part in ("", ".", "..") for part in path.split("/")):
            raise ValueError(
                "Git returned an incomplete/invalid path (possibly a nested repository); "
                "inspect the checkout before retrying"
            )
        paths.add(path)
    return paths


def _inventory(workdir: str, base: str) -> tuple[str, str, list[str]]:
    try:
        resolved_base = _commit(workdir, base)
    except ValueError as exc:
        raise ValueError(f"cannot diff against base: {exc}") from exc
    if _git(["rev-parse", "--show-prefix"], workdir) != b"\n":
        raise ValueError("--workdir must be the checkout root; subdirectories omit sibling changes")
    head = _commit(workdir, "HEAD")
    diff = [
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--ignore-submodules=none",
        "--name-only",
        "-z",
    ]
    files: set[str] = set()
    # Keep both sides of renames and dirty index/worktree changes even when they
    # cancel relative to the base. No human-oriented status parsing is needed.
    for revisions in ([resolved_base], ["--cached", head], []):
        files.update(_paths(_git([*diff, *revisions, "--"], workdir)))
    files.update(_paths(_git(["ls-files", "--others", "--exclude-standard", "-z", "--"], workdir)))
    if _commit(workdir, "HEAD") != head:
        raise ValueError("HEAD changed during collection; stop concurrent writes and retry")
    return resolved_base, head, sorted(files)


def changed_files(workdir: str, base: str) -> list[str]:
    """Complete tracked/dirty/untracked path inventory in a quiescent checkout."""
    return _inventory(workdir, base)[2]


def is_docs_only(path: str) -> bool:
    return path.endswith(".md") and not path.startswith((".opencode/", "docs/foundry-execution/"))


def plan(changed: list[str]) -> dict:
    minimum: list[str] = []
    regression: list[str] = []
    manual: list[str] = []
    reasons: dict[str, str] = {}
    uncertain: list[str] = []

    def _add(bucket: list[str], items: list[str]) -> None:
        for item in items:
            if item not in bucket:
                bucket.append(item)

    for path in changed:
        matched = False
        for prefix, min_tests, reg, man, reason in RULES:
            if path == prefix or path.startswith(prefix):
                _add(minimum, min_tests)
                _add(regression, reg)
                _add(manual, man)
                reasons[path] = reason
                matched = True
                break
        if matched:
            continue
        if is_docs_only(path):
            reasons[path] = "prose only (no test surface)"
            continue
        top = path.split("/")[0] if "/" in path else ""
        if top not in KNOWN_TOP_DIRS:
            uncertain.append(path)
            reasons[path] = "outside known operating-layer surface: full suite + requalification"
            continue
        _add(minimum, [FULL_FOUNDRY_SUITE])
        reasons[path] = "default conservative surface"
    if uncertain:
        _add(minimum, ["pytest tests/ -q"])
        _add(regression, ["pytest tests/ -q"])
    _add(regression, [FULL_FOUNDRY_SUITE])
    return {
        "changed": changed,
        "minimum": minimum,
        "regression": regression,
        "manual": manual,
        "requalification_required": bool(uncertain),
        "uncertain_files": uncertain,
        "contract_override": CONTRACT_OVERRIDE,
        "reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Map changed surfaces to required tests.")
    parser.add_argument("--base", required=True, help="Base commit to diff against.")
    parser.add_argument("--workdir", default=".")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    try:
        resolved_base, head, changed = _inventory(args.workdir, args.base)
    except ValueError as exc:
        print(f"TEST_IMPACT_ERROR: {exc}", file=sys.stderr)
        return 1
    result = {"base": args.base, "resolved_base": resolved_base, "head": head, **plan(changed)}
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
