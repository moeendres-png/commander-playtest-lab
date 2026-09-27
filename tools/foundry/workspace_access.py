"""Explicit project-workspace access declarations for Foundry runs.

A Foundry session may read across declared and verified Commander Simulator Next
worktrees without acquiring writer ownership, and may write more than one worktree
only when every additional mutation surface is explicitly declared owned-write.

Folder names never imply authority. Every surface binds repository identity plus exact
HEAD/tree. Writable surfaces additionally bind branch, state path and ownership.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import yaml

import reference_roots as reference_mod
import state as state_mod

ACCESS_MODES = ("read-only", "owned-write")
COMMON_KEYS = ("label", "root", "repo_slug", "commit", "tree", "cleanliness", "access")
WRITE_KEYS = ("branch", "state_path", "ownership")


class WorkspaceAccessError(ValueError):
    """Malformed or unverifiable workspace-access declaration."""


def _git(args: list[str], root: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def parse_spec(raw: str) -> dict:
    """Parse one repeatable --workspace-access JSON declaration."""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise WorkspaceAccessError(f"workspace access is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkspaceAccessError("workspace access must be a JSON object")
    missing = [key for key in COMMON_KEYS if key not in data]
    if missing:
        raise WorkspaceAccessError(f"workspace access missing keys: {missing}")
    access = data.get("access")
    if access not in ACCESS_MODES:
        raise WorkspaceAccessError(f"bad access {access!r} (want one of {ACCESS_MODES})")
    allowed = set(COMMON_KEYS)
    if access == "owned-write":
        missing_write = [key for key in WRITE_KEYS if key not in data]
        if missing_write:
            raise WorkspaceAccessError(f"owned-write missing keys: {missing_write}")
        allowed.update(WRITE_KEYS)
    extra = sorted(set(data) - allowed)
    if extra:
        raise WorkspaceAccessError(f"workspace access has unknown keys: {extra}")

    ref = {
        "label": data["label"],
        "root": data["root"],
        "repo_slug": data["repo_slug"],
        "commit": data["commit"],
        "tree": data["tree"],
        "cleanliness": data["cleanliness"],
        "intent": "read-only",
    }
    try:
        reference_mod.parse_spec(json.dumps(ref))
    except reference_mod.ReferenceError as exc:
        raise WorkspaceAccessError(str(exc)) from exc

    out = {key: data[key] for key in COMMON_KEYS}
    out["root"] = os.path.realpath(os.path.abspath(str(out["root"])))
    if access == "owned-write":
        for key in WRITE_KEYS:
            value = data[key]
            if not isinstance(value, str) or not value.strip():
                raise WorkspaceAccessError(f"owned-write {key} must be a non-empty string")
            out[key] = value
        if not os.path.isabs(out["state_path"]):
            raise WorkspaceAccessError("owned-write state_path must be absolute")
        out["state_path"] = os.path.realpath(os.path.abspath(out["state_path"]))
    return out


def _reference_view(spec: dict) -> dict:
    return {
        "label": spec["label"],
        "root": spec["root"],
        "repo_slug": spec["repo_slug"],
        "commit": spec["commit"],
        "tree": spec["tree"],
        "cleanliness": spec["cleanliness"],
        "intent": "read-only",
    }


def verify(spec: dict) -> list[str]:
    """Verify exact identity; writable surfaces additionally verify ownership state."""
    failures = reference_mod.verify(_reference_view(spec))
    if failures or spec["access"] == "read-only":
        return failures

    root = os.path.realpath(spec["root"])
    try:
        branch = _git(["branch", "--show-current"], root)
    except RuntimeError as exc:
        return [*failures, f"workspace {spec['label']!r}: cannot read branch: {exc}"]
    if branch != spec["branch"]:
        failures.append(
            f"workspace {spec['label']!r}: branch {branch!r} != expected {spec['branch']!r}"
        )

    state_path = Path(spec["state_path"])
    try:
        data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [*failures, f"workspace {spec['label']!r}: cannot read state: {exc}"]
    errors = state_mod.validate(data if isinstance(data, dict) else {})
    if errors:
        failures.append(f"workspace {spec['label']!r}: invalid state: {errors[0]}")
        return failures
    assert isinstance(data, dict)
    state_root = os.path.realpath(os.path.abspath(str(data.get("worktree", ""))))
    if state_root != root:
        failures.append(f"workspace {spec['label']!r}: state worktree does not match root")
    if str(data.get("branch", "")) != spec["branch"]:
        failures.append(
            f"workspace {spec['label']!r}: state branch {data.get('branch')!r} "
            f"!= expected {spec['branch']!r}"
        )
    if str(data.get("ownership", "")) != spec["ownership"]:
        failures.append(
            f"workspace {spec['label']!r}: state ownership {data.get('ownership')!r} "
            f"!= expected {spec['ownership']!r}"
        )
    if str(data.get("status", "")) not in ("ACTIVE", "WAITING"):
        failures.append(
            f"workspace {spec['label']!r}: owned-write requires ACTIVE/WAITING state, "
            f"got {data.get('status')!r}"
        )
    return failures


def format_context(specs: list[dict]) -> str:
    lines = ["Declared project workspace access (verified at launch):"]
    for spec in specs:
        suffix = ""
        if spec["access"] == "owned-write":
            suffix = (
                f" branch={spec['branch']} ownership={spec['ownership']} "
                f"state={spec['state_path']}"
            )
        lines.append(
            f"- {spec['label']}: access={spec['access']} root={spec['root']} "
            f"slug={spec['repo_slug']} commit={spec['commit'][:12]} "
            f"tree={spec['tree'][:12]}{suffix}"
        )
    lines.append(
        "Only owned-write surfaces are mutation-authorized. Read-only surfaces may be "
        "inspected/tested but not edited or committed. Undeclared/foreign/unknown "
        "worktrees remain outside writer authority."
    )
    return "\n".join(lines)
