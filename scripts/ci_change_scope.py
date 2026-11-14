#!/usr/bin/env python3
"""Classify a pull request's diff for ``.github/workflows/ci.yml``.

The ``changes`` job of the CI workflow runs this once per run and publishes three outputs that
decide *how much* work the required ``quality`` context does. It never decides *whether* a
check exists: ``lint`` and the ``quality`` gate job always run.

* ``scope`` is ``docs`` only when every changed path is documentation. A path is documentation
  when it matches ``docs/**`` or ``**/*.md`` and is not under ``.github/``, ``config/``,
  ``data/``, ``qualification/``, ``tests/``, ``src/`` or ``scripts/``. Anything else, an empty
  diff, a diff that cannot be read and every event other than ``pull_request`` (a push to
  ``main``, a manual dispatch) is ``full``.
* ``packaging`` is ``true`` when the packaging job must run: on every non-pull-request event,
  and on a pull request that changes a packaging input (see ``packaging_reason``).
* ``test_matrix`` is the JSON matrix of the ``tests`` job: ``MATRIX_COUNT`` slots that share
  every test of the ``quality`` context for ``full``, one slot with only the documentation
  tests for ``docs``.

The diff is read with ``--no-renames``: a rename out of (or into) a documentation path then
shows both of its paths, so ``src/engine.py`` renamed to ``docs/engine.md`` is not
documentation-only. Deleted files count like any other changed file.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Sequence
from pathlib import Path

MATRIX_COUNT = 4

# Never documentation, even when the file name ends in ``.md``.
NON_DOCS_ROOTS = (
    ".github/",
    "config/",
    "data/",
    "qualification/",
    "tests/",
    "src/",
    "scripts/",
)

# Inputs of ``scripts/verify_packaging_smoke.py`` and ``tests/unit/test_packaging_smoke.py``:
# the wheel built from the tree, its dependency closure (the hash-locked requirements), the
# console entrypoints declared by ``pyproject.toml`` and the smoke tooling itself.
PACKAGING_FILES = frozenset(
    {
        "pyproject.toml",
        "MANIFEST.in",
        "setup.py",
        "setup.cfg",
        "scripts/verify_packaging_smoke.py",
        "tests/unit/test_packaging_smoke.py",
        ".github/workflows/ci.yml",
    }
)
PACKAGING_PREFIXES = ("requirements/",)
PACKAGE_INIT = re.compile(r"^src/commander_lab/(?:.+/)?__init__\.py$")
SOURCE_PYTHON = re.compile(r"^src/.+\.py$")


def is_docs_path(path: str) -> bool:
    if path.startswith(NON_DOCS_ROOTS):
        return False
    return path.startswith("docs/") or path.endswith(".md")


def is_docs_only(paths: Sequence[str]) -> bool:
    """True only for a non-empty change set that is entirely documentation."""
    return bool(paths) and all(is_docs_path(path) for path in paths)


def console_script_modules(pyproject: Path) -> set[str]:
    """Source files of the modules the declared console scripts import (``pkg.mod:attr``)."""
    scripts = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {}).get(
        "scripts", {}
    )
    files: set[str] = set()
    for target in scripts.values():
        module = str(target).split(":", 1)[0].strip().replace(".", "/")
        files.update({f"src/{module}.py", f"src/{module}/__init__.py"})
    return files


def packaging_reason(
    changes: Sequence[tuple[str, str]], entrypoint_files: Iterable[str]
) -> str | None:
    """The first changed path that makes the packaging job necessary, else None.

    ``changes`` are ``(status, path)`` pairs. Besides the named inputs, a package ``__init__.py``,
    a console-script target module and any *added or deleted* ``.py`` file below ``src/`` count
    (they change what the wheel contains); an ordinary edit inside an existing module does not.
    """
    targets = set(entrypoint_files)
    for status, path in changes:
        if path in PACKAGING_FILES or path.startswith(PACKAGING_PREFIXES):
            return path
        if PACKAGE_INIT.match(path) or path in targets:
            return path
        if status in {"A", "D"} and SOURCE_PYTHON.match(path):
            return path
    return None


def parse_name_status(payload: bytes) -> list[tuple[str, str]]:
    """``git diff --name-status -z --no-renames`` output as ``(status, path)`` pairs."""
    fields = [item.decode("utf-8", errors="surrogateescape") for item in payload.split(b"\0")]
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) % 2:
        raise ValueError("unpaired name-status output")
    return [(fields[index][:1], fields[index + 1]) for index in range(0, len(fields), 2)]


def changed_files(repo: Path, base: str, head: str) -> list[tuple[str, str]]:
    completed = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-status", "--no-renames", "-z", base, head, "--"],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return parse_name_status(completed.stdout)


def matrix_for(scope: str, count: int = MATRIX_COUNT) -> dict[str, list[dict[str, object]]]:
    if scope == "docs":
        return {"include": [{"index": 1, "count": 1, "scope": "docs"}]}
    return {
        "include": [{"index": index, "count": count, "scope": "all"} for index in range(1, count + 1)]
    }


def decide(
    event: str,
    changes: Sequence[tuple[str, str]] | None,
    entrypoint_files: Iterable[str] = (),
) -> dict[str, str]:
    """The outputs for ``event``; ``changes`` is None when the diff could not be read."""
    if event != "pull_request":
        scope, packaging, reason = "full", True, f"event {event} always runs everything"
    elif changes is None:
        scope, packaging, reason = "full", True, "the diff could not be read: run everything"
    elif not changes:
        scope, packaging, reason = "full", True, "empty diff: run everything"
    elif is_docs_only([path for _, path in changes]):
        scope, packaging, reason = "docs", False, "documentation only"
    else:
        trigger = packaging_reason(changes, entrypoint_files)
        scope, packaging = "full", trigger is not None
        reason = (
            f"code change, packaging input {trigger}" if trigger else "code change, no packaging input"
        )
    return {
        "scope": scope,
        "packaging": "true" if packaging else "false",
        "test_matrix": json.dumps(matrix_for(scope), separators=(",", ":")),
        "reason": reason,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", required=True, help="github.event_name")
    parser.add_argument("--base", default="", help="base commit of the pull request")
    parser.add_argument("--head", default="HEAD", help="commit that is tested (default HEAD)")
    parser.add_argument("--repo", default=".", type=Path)
    parser.add_argument("--github-output", type=Path, help="file that receives key=value lines")
    args = parser.parse_args(argv)

    changes: list[tuple[str, str]] | None = None
    if args.event == "pull_request":
        try:
            if not args.base:
                raise ValueError("a pull request run needs --base")
            changes = changed_files(args.repo, args.base, args.head)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            print(f"could not read the diff: {error}", file=sys.stderr)
    try:
        entrypoints = console_script_modules(args.repo / "pyproject.toml")
    except (OSError, ValueError):
        entrypoints = set()
        if changes is not None and not changes:
            changes = None
    outputs = decide(args.event, changes, entrypoints)
    for key, value in outputs.items():
        print(f"{key}={value}")
    if changes:
        print(f"changed paths: {len(changes)}")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as sink:
            for key, value in outputs.items():
                sink.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
