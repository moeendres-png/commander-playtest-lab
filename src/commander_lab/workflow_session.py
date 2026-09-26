from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from commander_lab.project_context import ProjectContextSnapshot, load_project_context
from commander_lab.storage import sha256_value


class WorkflowSessionError(RuntimeError):
    pass


def _git_value(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise WorkflowSessionError(completed.stderr.strip() or "git identity lookup failed")
    return completed.stdout.strip()


@dataclass
class WorkflowSession:
    """One immutable current snapshot shared by all stages of one high-level workflow."""

    root: Path
    service: Any
    context: ProjectContextSnapshot
    git_commit: str
    git_tree: str
    session_hash: str
    verified_at_close: bool = False

    @classmethod
    def open(cls, root: str | Path, *, service: Any) -> WorkflowSession:
        resolved = Path(root).resolve()
        context = load_project_context(resolved)
        commit = _git_value(resolved, "rev-parse", "HEAD")
        tree = _git_value(resolved, "rev-parse", "HEAD^{tree}")
        session_hash = sha256_value(
            {
                "context_snapshot_hash": context.snapshot_hash,
                "git_commit": commit,
                "git_tree": tree,
                "engine_version": context.engine_version,
                "software_version": context.software_version,
            }
        )
        return cls(
            root=resolved,
            service=service,
            context=context,
            git_commit=commit,
            git_tree=tree,
            session_hash=session_hash,
        )

    def identity(self) -> dict[str, Any]:
        return {
            "session_hash": self.session_hash,
            "context_snapshot_hash": self.context.snapshot_hash,
            "git_commit": self.git_commit,
            "git_tree": self.git_tree,
            "immutable": True,
            "verified_at_close": self.verified_at_close,
        }

    def verify_current(self) -> None:
        current = load_project_context(self.root)
        commit = _git_value(self.root, "rev-parse", "HEAD")
        tree = _git_value(self.root, "rev-parse", "HEAD^{tree}")
        if current.snapshot_hash != self.context.snapshot_hash:
            raise WorkflowSessionError("semantic project context changed during workflow")
        if commit != self.git_commit or tree != self.git_tree:
            raise WorkflowSessionError("software identity changed during workflow")
        self.verified_at_close = True

    def __enter__(self) -> WorkflowSession:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc is None:
            self.verify_current()


__all__ = ["WorkflowSession", "WorkflowSessionError"]
