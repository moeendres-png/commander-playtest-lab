#!/usr/bin/env python3
"""Audit which executed sources a path-filtered workflow's gates actually cover.

A qualification workflow that filters on ``pull_request.paths`` (or gates its
heavy jobs with the ``change-scope`` action) only runs when a listed path
changes. If a module the workflow executes is not covered by any of those
globs, that module can change without its own gate running.

For every path-filtered workflow this tool:

1. collects the gate globs (trigger ``paths`` and every ``change-scope`` input);
2. finds the executed entry points in its ``run:`` steps (``scripts/…``,
   ``tests/…`` files or directories, ``python -m`` modules, inline
   ``commander_lab`` imports);
3. follows the repository's own Python imports transitively (static AST,
   including package ``__init__`` files and pytest ``conftest.py``);
4. reports every executed repository file no gate glob covers.

It is a static lower bound: dynamic imports are not followed, so an empty
report is necessary, not sufficient.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def glob_regex(pattern: str) -> re.Pattern[str]:
    """GitHub ``paths`` / git ``:(glob)`` semantics: ``**`` spans directories, ``*`` does not."""
    out = ""
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out += "(?:.*/)?"
            index += 3
        elif pattern.startswith("**", index):
            out += ".*"
            index += 2
        elif pattern[index] == "*":
            out += "[^/]*"
            index += 1
        elif pattern[index] == "?":
            out += "[^/]"
            index += 1
        else:
            out += re.escape(pattern[index])
            index += 1
    return re.compile(out + r"\Z")


def covered(path: str, globs: list[str]) -> bool:
    included = False
    for pattern in globs:
        negated = pattern.startswith("!")
        if glob_regex(pattern[1:] if negated else pattern).match(path):
            included = not negated
    return included


def trigger_gates(workflow: dict[Any, Any]) -> list[str] | None:
    """The pull_request ``paths`` filter, or None when pull requests always trigger."""
    on = workflow.get(True) or workflow.get("on") or {}
    spec = on.get("pull_request") if isinstance(on, dict) else None
    if isinstance(spec, dict) and spec.get("paths"):
        return [str(p) for p in spec["paths"]]
    return None


def scope_gates(job: dict[str, Any]) -> list[str] | None:
    """A job's ``change-scope`` paths, or None when the job is not scope-gated."""
    for step in job.get("steps") or ():
        if "change-scope" in str(step.get("uses", "")):
            return [
                line.strip()
                for line in str((step.get("with") or {}).get("paths", "")).splitlines()
                if line.strip()
            ]
    return None


def _module_file(module: str) -> Path | None:
    base = SRC.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _package_inits(module: str) -> list[Path]:
    parts = module.split(".")
    inits = []
    for depth in range(1, len(parts) + 1):
        init = SRC.joinpath(*parts[:depth], "__init__.py")
        if init.is_file():
            inits.append(init)
    return inits


def entry_points(job: dict[str, Any]) -> tuple[set[Path], set[str]]:
    files: set[Path] = set()
    modules: set[str] = set()
    for step in job.get("steps") or ():
        text = str(step.get("run") or "")
        if not text:
            continue
        modules.update(re.findall(r"\b(?:from|import)\s+(commander_lab(?:\.\w+)*)", text))
        joined = re.sub(r"\\\n", " ", text)
        for line in joined.splitlines():
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError:
                tokens = line.split()
            for position, token in enumerate(tokens):
                if token == "-m" and position + 1 < len(tokens):
                    target = tokens[position + 1]
                    if target.startswith("commander_lab"):
                        modules.add(target)
                relative = token.split("::")[0]
                if relative.startswith(("scripts/", "tests/", "src/")):
                    path = ROOT / relative
                    if path.is_file() and path.suffix == ".py":
                        files.add(path)
                    elif path.is_dir():
                        files.update(p for p in path.rglob("*.py"))
    return files, modules


def imported_modules(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    package = None
    if path.is_relative_to(SRC):
        package = ".".join(path.relative_to(SRC).with_suffix("").parts)
        if path.name != "__init__.py":
            package = package.rsplit(".", 1)[0]
        else:
            package = package.removesuffix(".__init__")
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(
                alias.name for alias in node.names if alias.name.startswith("commander_lab")
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level and package:
                base_parts = package.split(".")
                base_parts = base_parts[: len(base_parts) - (node.level - 1)]
                base = ".".join(base_parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            if not base.startswith("commander_lab"):
                continue
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def executed_files(files: set[Path], modules: set[str]) -> set[Path]:
    pending = set(files)
    for module in modules:
        pending.update(_package_inits(module))
        target = _module_file(module)
        if target:
            pending.add(target)
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        if path.is_relative_to(ROOT / "tests"):
            for parent in [path.parent, *path.parent.parents]:
                if not parent.is_relative_to(ROOT):
                    break
                conftest = parent / "conftest.py"
                if conftest.is_file():
                    pending.add(conftest)
        for module in imported_modules(path):
            pending.update(_package_inits(module))
            target = _module_file(module)
            if target:
                pending.add(target)
    return seen


def audit(workflow_path: Path) -> dict[str, Any] | None:
    """Per job: executed repository files no active gate of that job covers.

    A job runs only when the pull_request trigger filter fires (if the workflow
    has one) and its own change-scope is relevant (if it has one), so every
    executed file must be covered by each gate that applies to the job.
    """
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8")) or {}
    trigger = trigger_gates(workflow)
    all_jobs = workflow.get("jobs") or {}
    own_scope = {name: scope_gates(job) for name, job in all_jobs.items()}
    jobs: dict[str, Any] = {}
    for name, job in all_jobs.items():
        scope = own_scope[name]
        if scope is None:
            # A heavy job gated by a scope job it needs (``if: needs.<scope>.outputs...``).
            needs = job.get("needs") or []
            needs = [needs] if isinstance(needs, str) else list(needs)
            condition = str(job.get("if") or "")
            for needed in needs:
                if own_scope.get(needed) is not None and f"needs.{needed}." in condition:
                    scope = own_scope[needed]
        if trigger is None and scope is None:
            continue
        files, modules = entry_points(job)
        executed = sorted(str(p.relative_to(ROOT)) for p in executed_files(files, modules))
        uncovered = []
        for path in executed:
            missing = [
                gate
                for gate, globs in (("trigger", trigger), ("change-scope", scope))
                if globs is not None and not covered(path, globs)
            ]
            if missing:
                uncovered.append({"path": path, "gates": missing})
        jobs[name] = {
            "entry_points": sorted(str(p.relative_to(ROOT)) for p in files) + sorted(modules),
            "executed_files": executed,
            "uncovered": uncovered,
        }
    if not jobs:
        return None
    return {"trigger_paths": trigger, "jobs": jobs}


# Workflows whose gates this tool must not rewrite, with the owner and reason.
NOT_REWRITTEN: dict[str, str] = {
    "pb03-runtime-qualification.yml": "active surface of the current-boundary lane (PR #395)",
}


def cover_glob(path: str) -> str:
    """The glob that covers ``path`` in a gate: its whole subpackage, else the file."""
    parts = path.split("/")
    if parts[:2] == ["src", "commander_lab"] and len(parts) > 3:
        return f"src/commander_lab/{parts[2]}/**"
    return path


def _append_to_list(lines: list[str], start: int, additions: list[str], block: bool) -> int:
    """Append items to the YAML list (or ``|`` block) whose first item follows ``start``."""
    index = start + 1
    item_indent = None
    last = start
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if not stripped:
            index += 1
            continue
        if item_indent is None:
            item_indent = indent
        if indent < item_indent or (not block and not stripped.startswith("- ")):
            break
        last = index
        index += 1
    if item_indent is None:
        raise ValueError(f"empty gate list after line {start + 1}")
    pad = " " * item_indent
    rendered = [f"{pad}{item}" if block else f'{pad}- "{item}"' for item in additions]
    lines[last + 1 : last + 1] = rendered
    return len(rendered)


def fix(workflow_path: Path) -> int:
    """Add the missing cover globs to every gate list of ``workflow_path``."""
    result = audit(workflow_path)
    if result is None:
        return 0
    trigger_missing: list[str] = []
    scope_missing: list[str] = []
    for detail in result["jobs"].values():
        for item in detail["uncovered"]:
            glob = cover_glob(item["path"])
            if "trigger" in item["gates"] and glob not in trigger_missing:
                trigger_missing.append(glob)
            if "change-scope" in item["gates"] and glob not in scope_missing:
                scope_missing.append(glob)
    if not trigger_missing and not scope_missing:
        return 0
    lines = workflow_path.read_text(encoding="utf-8").splitlines()
    added = 0
    section = None
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped in {"pull_request:", "push:"}:
            section = "trigger"
        elif stripped.startswith("jobs:"):
            section = "jobs"
        if section == "trigger" and stripped == "paths:" and trigger_missing:
            added += _append_to_list(lines, index, sorted(set(trigger_missing)), block=False)
        scope_block = any("change-scope" in lines[back] for back in range(max(0, index - 3), index))
        if section == "jobs" and stripped == "paths: |" and scope_missing and scope_block:
            added += _append_to_list(lines, index, sorted(set(scope_missing)), block=True)
        index += 1
    workflow_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workflow", action="append", help="limit to these workflow files")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--fix", action="store_true", help="add the missing cover globs to the gates"
    )
    args = parser.parse_args(argv)
    paths = (
        [Path(p) for p in args.workflow]
        if args.workflow
        else sorted((ROOT / ".github/workflows").glob("*.yml"))
    )
    if args.fix:
        for path in paths:
            if path.name in NOT_REWRITTEN:
                continue
            added = fix(path)
            if added:
                print(f"{path.name}: added {added} gate globs")
    report = {}
    for path in paths:
        result = audit(path)
        if result is not None:
            report[path.name] = result
    if args.json:
        json.dump(report, sys.stdout, indent=1, sort_keys=True)
        print()
    else:
        for name, result in report.items():
            for job, detail in result["jobs"].items():
                print(
                    f"{name}:{job}: executed={len(detail['executed_files'])} "
                    f"uncovered={len(detail['uncovered'])}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
