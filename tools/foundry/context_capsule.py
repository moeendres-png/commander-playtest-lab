"""Compact Foundry execution capsule (DERIVED/INDEX, read-only).

Derives a small execution-critical summary from the exact launcher state path
plus live Git/worktree facts, suitable for prompt injection by the ``/work``
command. The capsule is an operational index, never Source Authority: the
state file, contract, and live Git remain authoritative.

Fail-closed: missing/invalid state, unreadable Git facts, or contradictory
source-lock identity (branch mismatch, audit base outside history, broken
validation-credit ancestry) yields ``CAPSULE_REJECT`` (exit 2) and no capsule.

Stdlib plus PyYAML only. Never writes. Never prints environment values.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import state as state_mod
import yaml

STATE_ENV_VAR = "FOUNDRY_STATE_PATH"
IN_WORKTREE_DEFAULT = Path(".foundry") / "WORKSTREAM_STATE.yaml"

CAPSULE_KIND = "FOUNDRY CAPSULE (DERIVED/INDEX - not Source Authority)"


class CapsuleError(ValueError):
    """Fail-closed capsule refusal (state, Git, or identity problem)."""


def resolve_state_path(explicit: str | None) -> str:
    """Exact state path: explicit flag, then FOUNDRY_STATE_PATH, then CWD default."""
    if explicit:
        return explicit
    env_path = os.environ.get(STATE_ENV_VAR)
    if env_path:
        return env_path
    return str(Path.cwd() / IN_WORKTREE_DEFAULT)


def _git(args: list[str], workdir: str) -> str:
    proc = subprocess.run(["git", *args], cwd=workdir, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise CapsuleError(f"cannot read git {' '.join(args)}: {proc.stderr.strip()[:160]}")
    return proc.stdout.strip()


def _load_state(state_path: str) -> dict:
    try:
        with open(state_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        raise CapsuleError(f"cannot read state file {state_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise CapsuleError(f"state file is not parseable YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CapsuleError("state file must be a mapping")
    errors = state_mod.validate(data)
    if errors:
        raise CapsuleError(f"invalid state: {errors[0]}")
    return data


def _git_facts(workdir: str) -> dict:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], workdir)
    if branch == "HEAD":
        raise CapsuleError("detached HEAD (capsule requires the workstream branch)")
    head = _git(["rev-parse", "HEAD"], workdir)
    tree = _git(["rev-parse", "HEAD^{tree}"], workdir)
    porcelain = _git(["status", "--porcelain"], workdir)
    dirty = len(porcelain.splitlines()) if porcelain else 0
    return {"branch": branch, "head": head, "tree": tree, "dirty_entries": dirty}


def _check_identity(data: dict, facts: dict, workdir: str) -> list[str]:
    """Contradictory source-lock identity notes (any entry fails closed)."""
    problems: list[str] = []
    if str(data.get("branch", "")) != facts["branch"]:
        problems.append(
            f"branch mismatch: state={data.get('branch')!r} live={facts['branch']!r} "
            "(live Git wins; update the state file)"
        )
    base = str(data.get("audit_base_sha", ""))
    if not state_mod._is_ancestor(base, facts["head"], workdir):
        problems.append(
            f"SOURCE_LOCK_CONTRADICTION: audit_base_sha {base} is not an ancestor "
            f"of live HEAD {facts['head']}"
        )
    validated = data.get("validated_head")
    if validated is not None:
        if not state_mod._is_ancestor(base, str(validated), workdir):
            problems.append(
                f"VALIDATED_OUTSIDE_LOCK: validated_head {validated} does not "
                f"descend from audit_base_sha {base}"
            )
        if not state_mod._is_ancestor(str(validated), facts["head"], workdir):
            problems.append(
                f"VALIDATED_REWRITTEN: validated_head {validated} is not an "
                f"ancestor of live HEAD {facts['head']} (history moved; revalidate)"
            )
    return problems


def _as_lines(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        lines = []
        for item in value:
            if not isinstance(item, str):
                raise CapsuleError(f"state field {field!r} must be a string list")
            lines.append(item)
        return lines
    if isinstance(value, str):
        return [value]
    raise CapsuleError(f"state field {field!r} must be a string list")


def build_capsule(data: dict, facts: dict, state_path: str) -> str:
    """Render the deterministic text capsule (fixed field order)."""
    recorded = data.get("state_written_against_head")
    drift_note = ""
    if recorded and str(recorded) != facts["head"]:
        drift_note = " (HEAD drift: live Git wins; update the state file)"
    validated = data.get("validated_head")
    lines = [
        CAPSULE_KIND,
        "Read the full state/contract/evidence only when this capsule is insufficient.",
        f"repository: {data.get('repository')}",
        f"worktree: {data.get('worktree')}",
        f"branch: {data.get('branch')}",
        f"ownership: {data.get('ownership')}",
        f"audit_base_sha: {data.get('audit_base_sha')}",
        f"audit_base_tree: {data.get('audit_base_tree')}",
        f"live_HEAD: {facts['head']}",
        f"live_tree: {facts['tree']}",
        f"tree_clean: {'yes' if facts['dirty_entries'] == 0 else 'no'}"
        f" ({facts['dirty_entries']} dirty entries)",
        f"state_written_against_head: {recorded}{drift_note}",
        f"validated_head: {validated if validated is not None else 'null (nothing validated beyond the audit base)'}",
        f"status: {data.get('status')}",
        f"objective: {data.get('objective')}",
        f"exact_next_action: {data.get('exact_next_action')}",
    ]
    failure = str(data.get("failure_class", "NONE"))
    if failure not in ("NONE", ""):
        lines.append(f"failure_class: {failure}")
        lines.append(f"current_failure: {data.get('current_failure')}")
    hard_gates = _as_lines(data.get("hard_gates"), "hard_gates")
    if hard_gates:
        lines.append("hard_gates:")
        lines.extend(f"  - {gate}" for gate in hard_gates)
    authority_gates = _as_lines(data.get("authority_gates"), "authority_gates")
    lines.append("authority_gates:")
    if authority_gates:
        lines.extend(f"  - {gate}" for gate in authority_gates)
    else:
        lines.append("  (none)")
    lines.append(f"full_state: {state_path} (inspect with state.py --state PATH)")
    return "\n".join(lines) + "\n"


def build_capsule_json(data: dict, facts: dict, state_path: str) -> str:
    """Deterministic JSON capsule (sorted keys, same critical fields)."""
    recorded = data.get("state_written_against_head")
    doc = {
        "_kind": "DERIVED_INDEX (not Source Authority)",
        "repository": data.get("repository"),
        "worktree": data.get("worktree"),
        "branch": data.get("branch"),
        "ownership": data.get("ownership"),
        "audit_base_sha": data.get("audit_base_sha"),
        "audit_base_tree": data.get("audit_base_tree"),
        "live_HEAD": facts["head"],
        "live_tree": facts["tree"],
        "tree_clean": facts["dirty_entries"] == 0,
        "dirty_entries": facts["dirty_entries"],
        "state_written_against_head": recorded,
        "head_drift": bool(recorded and str(recorded) != facts["head"]),
        "validated_head": data.get("validated_head"),
        "status": data.get("status"),
        "objective": data.get("objective"),
        "exact_next_action": data.get("exact_next_action"),
        "failure_class": data.get("failure_class"),
        "hard_gates": _as_lines(data.get("hard_gates"), "hard_gates"),
        "authority_gates": _as_lines(data.get("authority_gates"), "authority_gates"),
        "full_state": state_path,
    }
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def derive(state_path: str, workdir: str, fmt: str = "text", full: bool = False) -> str:
    """Load, identity-check, and render. Raises CapsuleError fail-closed."""
    data = _load_state(state_path)
    facts = _git_facts(workdir)
    problems = _check_identity(data, facts, workdir)
    if problems:
        raise CapsuleError(problems[0])
    if full:
        return state_mod.dump_state(data)
    if fmt == "json":
        return build_capsule_json(data, facts, state_path)
    return build_capsule(data, facts, state_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive the compact Foundry execution capsule.")
    parser.add_argument(
        "--state", default=None, help="Exact state path (default: FOUNDRY_STATE_PATH)."
    )
    parser.add_argument(
        "--workdir", default=None, help="Worktree for live Git facts (default: CWD)."
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Opt-in: print the full validated state instead of the compact capsule.",
    )
    args = parser.parse_args(argv)
    state_path = resolve_state_path(args.state)
    workdir = args.workdir or os.getcwd()
    try:
        print(derive(state_path, workdir, args.format, args.full), end="")
    except CapsuleError as exc:
        print(f"CAPSULE_REJECT: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
