"""Remote milestone-checkpoint verification (fail closed, no parallel orchestrator).

Reuses the canonical Foundry state identity plus read-only ``git ls-remote``
inspection. A claimed remote checkpoint is satisfied only when the remote
branch tip equals the recorded SHA and tree, or descends from it through a
generated-state-only closeout delta.

A pushed WIP is never qualification PASS: resumability requires a validated
implementation identity plus a satisfied remote checkpoint.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import materiality as materiality_mod

SATISFIED = "SATISFIED"
MISSING = "MISSING"
MISMATCH = "MISMATCH"
UNVERIFIABLE = "UNVERIFIABLE"
EXEMPT_HISTORICAL = "EXEMPT_HISTORICAL"
PUSHED_WIP = "PUSHED_WIP"
REMOTE_RESUMABLE = "REMOTE_RESUMABLE"


@dataclass(frozen=True)
class RemoteCheckpointResult:
    status: str
    reasons: tuple[str, ...] = ()
    remote: str | None = None
    branch: str | None = None
    recorded_sha: str | None = None
    recorded_tree: str | None = None
    live_remote_sha: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in (SATISFIED, EXEMPT_HISTORICAL)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "ok": self.ok,
            "reasons": list(self.reasons),
            "remote": self.remote,
            "branch": self.branch,
            "recorded_sha": self.recorded_sha,
            "recorded_tree": self.recorded_tree,
            "live_remote_sha": self.live_remote_sha,
        }


def _is_sha(value: object) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(c in "0123456789abcdef" for c in text)


def _run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def remote_head(remote: str, branch: str, workdir: str) -> str | None:
    """Exact remote branch tip via read-only ls-remote; None when absent."""
    proc = _run(["git", "ls-remote", remote, f"refs/heads/{branch}"], workdir)
    if proc.returncode != 0:
        raise RuntimeError("remote branch identity unreadable")
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    fields = lines[0].split()
    if len(fields) != 2 or fields[1] != f"refs/heads/{branch}":
        raise RuntimeError("remote branch identity ambiguous")
    return fields[0]


def _local_tree(workdir: str, sha: str) -> str | None:
    proc = _run(["git", "rev-parse", f"{sha}^{{tree}}"], workdir)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _is_ancestor(workdir: str, older: str, newer: str) -> bool:
    if older == newer:
        return True
    proc = _run(["git", "merge-base", "--is-ancestor", older, newer], workdir)
    return proc.returncode == 0


def _generated_state_only(
    workdir: str, older: str, newer: str, state_paths: tuple[str, ...]
) -> bool:
    report = materiality_mod.classify_commit_range(workdir, older, newer, state_paths=state_paths)
    return report.effective_computed == materiality_mod.NON_MATERIAL


def verify_remote_checkpoint(
    doc: dict,
    *,
    workdir: str | None = None,
    remote_head_fn=None,
    state_paths: tuple[str, ...] = (),
) -> RemoteCheckpointResult:
    """Verify the recorded remote checkpoint against live remote state."""
    policy_engaged = (
        "remote_checkpoint" in doc or "materiality" in doc or "cross_executor_review" in doc
    )
    if not policy_engaged:
        return RemoteCheckpointResult(
            status=EXEMPT_HISTORICAL,
            reasons=("REMOTE_CHECKPOINT_EXEMPT_HISTORICAL: pre-policy state",),
        )
    checkpoint = doc.get("remote_checkpoint")
    if checkpoint is None:
        return RemoteCheckpointResult(
            status=MISSING,
            reasons=("REMOTE_CHECKPOINT_MISSING: no verified remote checkpoint recorded",),
        )
    if not isinstance(checkpoint, dict):
        return RemoteCheckpointResult(
            status=UNVERIFIABLE,
            reasons=("REMOTE_CHECKPOINT_INVALID: remote_checkpoint must be a mapping",),
        )
    remote = str(checkpoint.get("remote") or "origin")
    branch = str(checkpoint.get("branch") or doc.get("branch") or "")
    recorded_sha = str(checkpoint.get("sha") or "")
    recorded_tree = str(checkpoint.get("tree") or "")
    if not _is_sha(recorded_sha) or not _is_sha(recorded_tree) or not branch:
        return RemoteCheckpointResult(
            status=UNVERIFIABLE,
            reasons=("REMOTE_CHECKPOINT_INVALID: sha/tree must be 40-hex and branch non-empty",),
            remote=remote,
            branch=branch or None,
        )
    state_branch = str(doc.get("branch") or "")
    if state_branch and branch != state_branch:
        return RemoteCheckpointResult(
            status=MISMATCH,
            reasons=(
                f"REMOTE_CHECKPOINT_MISMATCH: checkpoint branch {branch!r} != "
                f"state branch {state_branch!r}",
            ),
            remote=remote,
            branch=branch,
            recorded_sha=recorded_sha,
            recorded_tree=recorded_tree,
        )
    if workdir is None:
        return RemoteCheckpointResult(
            status=UNVERIFIABLE,
            reasons=("REMOTE_CHECKPOINT_UNVERIFIABLE: no workdir for remote inspection",),
            remote=remote,
            branch=branch,
            recorded_sha=recorded_sha,
            recorded_tree=recorded_tree,
        )
    try:
        live = (
            remote_head_fn(remote, branch, workdir)
            if remote_head_fn
            else remote_head(remote, branch, workdir)
        )
    except RuntimeError as exc:
        return RemoteCheckpointResult(
            status=UNVERIFIABLE,
            reasons=(f"REMOTE_CHECKPOINT_UNVERIFIABLE: {exc}",),
            remote=remote,
            branch=branch,
            recorded_sha=recorded_sha,
            recorded_tree=recorded_tree,
        )
    if live is None:
        return RemoteCheckpointResult(
            status=MISMATCH,
            reasons=(
                "REMOTE_CHECKPOINT_MISMATCH: checkpoint records a pushed commit but the "
                "remote branch is absent",
            ),
            remote=remote,
            branch=branch,
            recorded_sha=recorded_sha,
            recorded_tree=recorded_tree,
        )
    if live == recorded_sha:
        local_tree = _local_tree(workdir, recorded_sha)
        if local_tree is not None and local_tree != recorded_tree:
            return RemoteCheckpointResult(
                status=MISMATCH,
                reasons=(
                    "REMOTE_CHECKPOINT_TREE_MISMATCH: remote tip tree differs from the "
                    "recorded checkpoint tree",
                ),
                remote=remote,
                branch=branch,
                recorded_sha=recorded_sha,
                recorded_tree=recorded_tree,
                live_remote_sha=live,
            )
        return RemoteCheckpointResult(
            status=SATISFIED,
            reasons=(f"REMOTE_CHECKPOINT_SATISFIED: {remote}/{branch}@{live[:12]}",),
            remote=remote,
            branch=branch,
            recorded_sha=recorded_sha,
            recorded_tree=recorded_tree,
            live_remote_sha=live,
        )
    # Remote advanced: only a generated-state-only closeout delta preserves the
    # recorded checkpoint identity. Anything else is a real mismatch.
    if _local_tree(workdir, recorded_sha) is None:
        return RemoteCheckpointResult(
            status=UNVERIFIABLE,
            reasons=(
                "REMOTE_CHECKPOINT_UNVERIFIABLE: remote tip moved and the recorded "
                "checkpoint object is not available locally for delta adjudication",
            ),
            remote=remote,
            branch=branch,
            recorded_sha=recorded_sha,
            recorded_tree=recorded_tree,
            live_remote_sha=live,
        )
    if _is_ancestor(workdir, recorded_sha, live) and _generated_state_only(
        workdir, recorded_sha, live, state_paths
    ):
        return RemoteCheckpointResult(
            status=SATISFIED,
            reasons=(
                f"REMOTE_CHECKPOINT_SATISFIED: remote advanced from recorded "
                f"{recorded_sha[:12]} to {live[:12]} by generated-state-only closeout",
            ),
            remote=remote,
            branch=branch,
            recorded_sha=recorded_sha,
            recorded_tree=recorded_tree,
            live_remote_sha=live,
        )
    return RemoteCheckpointResult(
        status=MISMATCH,
        reasons=(
            f"REMOTE_CHECKPOINT_MISMATCH: intended {recorded_sha[:12]} != remote "
            f"{live[:12]} (remote resumability PASS refused)",
        ),
        remote=remote,
        branch=branch,
        recorded_sha=recorded_sha,
        recorded_tree=recorded_tree,
        live_remote_sha=live,
    )


def resumability_status(doc: dict, checkpoint: RemoteCheckpointResult) -> str:
    """Pushed WIP is never qualification PASS."""
    if checkpoint.status == EXEMPT_HISTORICAL:
        return EXEMPT_HISTORICAL
    if checkpoint.status != SATISFIED:
        return "NO_REMOTE_RESUMABILITY"
    if doc.get("validated_head") is None:
        return PUSHED_WIP
    return REMOTE_RESUMABLE


def _load_state(path: str) -> dict:
    import yaml

    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    if not isinstance(doc, dict):
        raise ValueError("state is not a mapping")
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remote checkpoint verifier.")
    parser.add_argument("--state", required=True, help="Workstream state YAML.")
    parser.add_argument("--workdir", required=True, help="Git worktree for remote inspection.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        doc = _load_state(args.state)
    except (OSError, ValueError) as exc:
        print(f"REMOTE_CHECKPOINT_FAIL: cannot read state: {exc}", file=sys.stderr)
        return 2
    result = verify_remote_checkpoint(doc, workdir=args.workdir)
    payload = result.to_dict()
    payload["resumability"] = resumability_status(doc, result)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif result.ok:
        print(f"REMOTE_CHECKPOINT_OK: {result.status} ({payload['resumability']})")
    else:
        print(f"REMOTE_CHECKPOINT_FAIL: {result.status}: {result.reasons[0]}", file=sys.stderr)
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
