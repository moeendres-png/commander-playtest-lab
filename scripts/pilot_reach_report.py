"""Which changed pilot lines do real requests reach? (#961 R-1)

``pilot_request_corpus.py diff`` says how many real answers a pilot change altered. "0 of 433"
is only evidence when the changed lines ran at all: a branch that no recorded request enters
cannot change an answer, and the footprint stays silent about it. This script closes that gap.
It replays the corpus (and, if given, a full dump of whole games) under ``sys.monitoring`` and
reports, for every executable line the working tree changed against the base, whether any
request ran it, and which decision classes did.

    python scripts/pilot_reach_report.py                         # changes vs the merge base
    python scripts/pilot_reach_report.py --dump all_requests.jsonl.gz
    python scripts/pilot_reach_report.py --whole                 # reach of the pilot as it is

No JVM and no extra package: the line events come from the interpreter (Python 3.12+).

Reading the report. A changed line that is ``reached`` by a request is exercised on real
input; its effect on the answers is what ``pilot_request_corpus.py diff`` counts. A line that
is ``not reached`` needs another proof: a unit test that enters the branch, or a game that
does. Lines are counted only when they run inside a function body: signatures, decorators,
class bodies and module constants run when the file is imported and are listed apart. A line
is reached when it ran once; it does not say that both outcomes of its condition ran.

Exit code: 0 when every changed function-body line is reached (or nothing relevant changed),
1 when at least one is not, 2 for a refusal (no git, no corpus, no free monitoring tool).
"""

from __future__ import annotations

import argparse
import dis
import inspect
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import pilot_request_corpus as corpus_tool  # noqa: E402

# The files whose lines decide a real pilot answer.
PILOT_PATHS = (
    "src/commander_lab/engine/rules/full_game_pilot",
    "src/commander_lab/engine/rules/full_game_pilot_views.py",
    "src/commander_lab/agents/pilots.py",
    "src/commander_lab/agents/card_knowledge.py",
)
SETUP = "<setup>"
# The instructions a function starts with; they carry the line of its ``def``.
_PROLOGUE = frozenset({"RESUME", "RETURN_GENERATOR", "POP_TOP", "COPY_FREE_VARS", "MAKE_CELL"})


class Refusal(Exception):
    """The report cannot be made (not a finding about the pilot)."""


# --- which lines changed -------------------------------------------------------------------


def parse_diff(text: str) -> tuple[dict[str, set[int]], dict[str, int]]:
    """Added or changed new-file lines and the count of removed lines per file of a ``-U0`` diff."""
    changed: dict[str, set[int]] = {}
    removed: dict[str, int] = {}
    path: str | None = None
    for line in text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            path = None if target == "/dev/null" else target.removeprefix("b/")
            if path is not None:
                changed.setdefault(path, set())
                removed.setdefault(path, 0)
        elif line.startswith("@@") and path is not None:
            old, new = line.split("@@")[1].split()[:2]
            _, _, old_len = old.lstrip("-").partition(",")
            new_start, _, new_len = new.lstrip("+").partition(",")
            first = int(new_start)
            count = int(new_len) if new_len != "" else 1
            changed[path].update(range(first, first + count))
            removed[path] += int(old_len) if old_len != "" else 1
    return changed, removed


def _git(*args: str, cwd: Path) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise Refusal(f"git is not available: {exc}") from exc
    if done.returncode != 0:
        raise Refusal(f"git {' '.join(args)} failed: {done.stderr.strip()[:300]}")
    return done.stdout


def merge_base(cwd: Path) -> str:
    """The commit the branch left main at (``HEAD`` when main is unknown)."""
    for candidate in ("origin/main", "main"):
        done = subprocess.run(
            ["git", "merge-base", candidate, "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode == 0 and done.stdout.strip():
            return done.stdout.strip()
    return "HEAD"


def changed_lines(
    base: str, paths: Sequence[str], cwd: Path = ROOT
) -> tuple[dict[str, set[int]], dict[str, int]]:
    """Lines the working tree (committed or not) changed against ``base``, plus new files."""
    diff = _git(
        "diff", "--no-ext-diff", "--no-color", "--no-renames", "-U0", base, "--", *paths, cwd=cwd
    )
    changed, removed = parse_diff(diff)
    untracked = _git("ls-files", "--others", "--exclude-standard", "--", *paths, cwd=cwd)
    for name in untracked.splitlines():
        if name.endswith(".py") and (cwd / name).is_file():
            count = len((cwd / name).read_text(encoding="utf-8").splitlines())
            changed[name] = set(range(1, count + 1))
            removed[name] = 0
    return {k: v for k, v in changed.items() if k.endswith(".py")}, removed


def pilot_files(paths: Sequence[str], cwd: Path = ROOT) -> list[str]:
    """Every ``.py`` file under the given files and directories (repository-relative)."""
    found: list[str] = []
    for entry in paths:
        target = cwd / entry
        if target.is_dir():
            found += [str(p.relative_to(cwd)) for p in sorted(target.rglob("*.py"))]
        elif target.is_file():
            found.append(entry)
    return found


# --- which lines can run ------------------------------------------------------------------


@dataclass(frozen=True)
class Executable:
    """The lines of a source file that hold instructions."""

    call: dict[int, str]  # line -> qualified name of the function whose body holds it
    load: frozenset[int]  # lines run when the file is imported (module and class bodies)


def _real_lines(code: CodeType) -> set[int]:
    lines = {line for _, _, line in code.co_lines() if line}
    first = code.co_firstlineno
    if first in lines and code.co_flags & inspect.CO_OPTIMIZED:
        own = any(
            ins.opname not in _PROLOGUE and getattr(ins.positions, "lineno", None) == first
            for ins in dis.get_instructions(code)
        )
        if not own:
            lines.discard(first)
    return lines


def executable_lines(source: str, filename: str = "<source>") -> Executable:
    """Split the instruction-bearing lines of ``source`` into function-body and import-time."""
    call: dict[int, str] = {}
    load: set[int] = set()

    def walk(code: CodeType) -> None:
        lines = _real_lines(code)
        if code.co_flags & inspect.CO_OPTIMIZED:
            for line in lines:
                call[line] = code.co_qualname  # the innermost function wins
        else:
            load.update(lines)
        for const in code.co_consts:
            if isinstance(const, CodeType):
                walk(const)

    walk(compile(source, filename, "exec"))
    return Executable(call=call, load=frozenset(load - set(call)))


# --- which lines ran ----------------------------------------------------------------------


class LineMonitor:
    """Records which lines of ``files`` run, and for which label (a decision class).

    ``begin(label)`` opens a request: every line that runs before ``end()`` is counted once for
    that label. Only lines of the watched files are kept; every other location disables itself
    after its first event, so the cost stays small.
    """

    def __init__(self, files: Iterable[str | Path]) -> None:
        self._files = {os.path.realpath(f) for f in files}
        self._wanted: dict[str, bool] = {}
        self._label = SETUP
        self._tool: int | None = None
        self.hits: dict[tuple[str, int], Counter[str]] = {}

    def __enter__(self) -> LineMonitor:
        mon = sys.monitoring
        for tool in (mon.COVERAGE_ID, 3, 4):
            try:
                mon.use_tool_id(tool, "pilot_reach_report")
            except ValueError:
                continue
            self._tool = tool
            break
        else:
            raise Refusal("no free sys.monitoring tool id (is a coverage tool running?)")
        mon.register_callback(self._tool, mon.events.LINE, self._on_line)
        return self

    def __exit__(self, *exc: object) -> None:
        mon = sys.monitoring
        if self._tool is not None:
            mon.set_events(self._tool, 0)
            mon.register_callback(self._tool, mon.events.LINE, None)
            mon.free_tool_id(self._tool)
            self._tool = None

    def _on_line(self, code: CodeType, line: int) -> object:
        name = code.co_filename
        wanted = self._wanted.get(name)
        if wanted is None:
            wanted = self._wanted[name] = os.path.realpath(name) in self._files
        if wanted:
            key = (os.path.realpath(name), line)
            counter = self.hits.get(key)
            if counter is None:
                counter = self.hits[key] = Counter()
            counter[self._label] += 1
        return sys.monitoring.DISABLE

    def begin(self, label: str) -> None:
        assert self._tool is not None
        self._label = label
        sys.monitoring.restart_events()
        sys.monitoring.set_events(self._tool, sys.monitoring.events.LINE)

    def end(self) -> None:
        assert self._tool is not None
        sys.monitoring.set_events(self._tool, 0)


@contextmanager
def watching(monitor: LineMonitor) -> Iterator[None]:
    """Mark the policy construction and every ``decide`` call of the corpus replay."""
    from commander_lab.engine.rules.full_game_pilot import ExternalPilotDecisionPolicy

    original_decide = ExternalPilotDecisionPolicy.decide
    original_policy = corpus_tool.fresh_policy

    def decide(self: Any, request: dict[str, Any]) -> dict[str, Any]:
        monitor.begin(str(request.get("decision_class")))
        try:
            return original_decide(self, request)
        finally:
            monitor.end()

    def fresh_policy(seed: int) -> Any:
        monitor.begin(SETUP)
        try:
            return original_policy(seed)
        finally:
            monitor.end()

    ExternalPilotDecisionPolicy.decide = decide  # type: ignore[method-assign]
    corpus_tool.fresh_policy = fresh_policy
    try:
        yield
    finally:
        ExternalPilotDecisionPolicy.decide = original_decide  # type: ignore[method-assign]
        corpus_tool.fresh_policy = original_policy


@dataclass
class Source:
    """One replayed file and the lines it reached."""

    name: str
    requests: int
    raised: int
    hits: dict[tuple[str, int], Counter[str]] = field(default_factory=dict)


def replay_source(path: Path, files: Iterable[str | Path], name: str | None = None) -> Source:
    """Replay a corpus (fresh policy per request) or a full dump (as played) under the monitor."""
    if not path.is_file():
        raise Refusal(f"no such corpus file: {path}")
    header, rows = corpus_tool.load_corpus(path)
    replayer = corpus_tool.replay_game if header.get("kind") == "full" else corpus_tool.replay
    with LineMonitor(files) as monitor, watching(monitor):
        outcomes = replayer(rows)
    raised = sum(1 for outcome in outcomes if outcome["answer"] is None)
    return Source(name or path.name, len(rows), raised, monitor.hits)


# --- the report ---------------------------------------------------------------------------


@dataclass
class FileReport:
    path: str
    changed: int
    removed: int
    non_executable: int
    load_lines: list[int]
    executable: dict[int, str]  # changed function-body line -> function
    reached: dict[int, dict[str, int]]  # line -> source -> requests
    classes: dict[int, list[str]]  # line -> decision classes, sorted

    @property
    def unreached(self) -> list[int]:
        return sorted(line for line in self.executable if line not in self.reached)


def build(
    changed: dict[str, set[int]],
    removed: dict[str, int],
    sources: Sequence[Source],
    cwd: Path = ROOT,
    *,
    sources_text: dict[str, str] | None = None,
) -> list[FileReport]:
    """One report per changed file: which changed function-body lines did a request run."""
    reports = []
    for path in sorted(changed):
        text = (sources_text or {}).get(path)
        if text is None:
            file = cwd / path
            if not file.is_file():
                continue  # the file was deleted: nothing left to reach
            text = file.read_text(encoding="utf-8")
        shape = executable_lines(text, path)
        lines = changed[path]
        executable = {line: shape.call[line] for line in sorted(lines) if line in shape.call}
        load = sorted(line for line in lines if line in shape.load)
        real = os.path.realpath(cwd / path)
        reached: dict[int, dict[str, int]] = {}
        classes: dict[int, set[str]] = {}
        for source in sources:
            for line in executable:
                counter = source.hits.get((real, line))
                if not counter:
                    continue
                reached.setdefault(line, {})[source.name] = sum(counter.values())
                classes.setdefault(line, set()).update(counter)
        reports.append(
            FileReport(
                path=path,
                changed=len(lines),
                removed=removed.get(path, 0),
                non_executable=len(lines) - len(executable) - len(load),
                load_lines=load,
                executable=executable,
                reached=reached,
                classes={line: sorted(names) for line, names in classes.items()},
            )
        )
    return reports


def verdict(reports: Sequence[FileReport]) -> str:
    total = sum(len(r.executable) for r in reports)
    reached = sum(len(r.reached) for r in reports)
    if not reports:
        return "NO_PILOT_CHANGE"
    if total == 0:
        return "NOTHING_EXECUTABLE"
    if reached == total:
        return "ALL_REACHED"
    return "NONE_REACHED" if reached == 0 else "SOME_NOT_REACHED"


def exit_code(reports: Sequence[FileReport]) -> int:
    return 1 if verdict(reports) in {"NONE_REACHED", "SOME_NOT_REACHED"} else 0


def ranges(lines: Sequence[int]) -> str:
    """``[3, 4, 5, 9]`` as ``3-5, 9``."""
    out: list[str] = []
    start = prev = None
    for line in sorted(lines):
        if start is None:
            start = prev = line
        elif line == prev + 1:  # type: ignore[operator]
            prev = line
        else:
            out.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = line
    if start is not None:
        out.append(str(start) if start == prev else f"{start}-{prev}")
    return ", ".join(out)


def format_report(
    reports: Sequence[FileReport],
    sources: Sequence[Source],
    *,
    base: str | None,
    thin: int,
) -> str:
    where = f"changes against {base[:12]}" if base else "every function-body line"
    out = [f"pilot reach report: {where}"]
    for source in sources:
        out.append(f"  source {source.name}: {source.requests} requests, {source.raised} raised")
    for report in reports:
        executable, reached = len(report.executable), len(report.reached)
        if base:
            head = f"{report.path}: {report.changed} lines changed, {executable} in function bodies"
        else:
            head = f"{report.path}: {executable} function-body lines"
        out.append(f"{head}, {reached} reached, {len(report.unreached)} not reached")
        if len(sources) > 1 and executable:
            per = ", ".join(
                f"{s.name} {sum(1 for hits in report.reached.values() if s.name in hits)}"
                for s in sources
            )
            out.append(f"    reached by: {per}")
        if report.unreached:
            by_function: dict[str, list[int]] = {}
            for line in report.unreached:
                by_function.setdefault(report.executable[line], []).append(line)
            for function, lines in by_function.items():
                out.append(f"    not reached: {function}: line {ranges(lines)}")
        thin_lines = [line for line, hits in report.reached.items() if max(hits.values()) < thin]
        if thin_lines:
            out.append(f"    reached by fewer than {thin} requests: line {ranges(thin_lines)}")
        if report.load_lines:
            out.append(f"    run at import, not counted: line {ranges(report.load_lines)}")
        if report.removed and not report.changed:
            out.append(f"    {report.removed} lines removed, nothing added")
    total = sum(len(r.executable) for r in reports)
    reached = sum(len(r.reached) for r in reports)
    what = "changed function-body lines" if base else "function-body lines"
    out.append(f"{what} reached: {reached} of {total}")
    kind = verdict(reports)
    out.append(f"verdict: {kind}")
    if kind in {"NONE_REACHED", "SOME_NOT_REACHED"}:
        out.append(
            "  the footprint of `pilot_request_corpus.py diff` is silent about the lines above:"
            " prove them with a unit test that enters the branch or with a game that reaches it"
        )
    return "\n".join(out)


def as_json(reports: Sequence[FileReport], sources: Sequence[Source], base: str | None) -> str:
    return json.dumps(
        {
            "base": base,
            "sources": [
                {"name": s.name, "requests": s.requests, "raised": s.raised} for s in sources
            ],
            "verdict": verdict(reports),
            "files": {
                r.path: {
                    "changed": r.changed,
                    "function_body": sorted(r.executable),
                    "reached": {str(k): v for k, v in sorted(r.reached.items())},
                    "classes": {str(k): v for k, v in sorted(r.classes.items())},
                    "not_reached": r.unreached,
                    "import_time": r.load_lines,
                }
                for r in reports
            },
        },
        indent=1,
        sort_keys=True,
    )


def run(args: argparse.Namespace) -> int:
    paths = list(args.paths) or list(PILOT_PATHS)
    files = pilot_files(paths)
    if not files:
        raise Refusal("no pilot files found under " + ", ".join(paths))
    base: str | None
    if args.whole:
        base = None
        changed = {}
        removed: dict[str, int] = {}
        for name in files:
            shape = executable_lines((ROOT / name).read_text(encoding="utf-8"), name)
            changed[name] = set(shape.call)
            removed[name] = 0
    else:
        base = args.base or merge_base(ROOT)
        changed, removed = changed_lines(base, paths)
    sources = [replay_source(args.corpus, (ROOT / f for f in files))]
    for dump in args.dump:
        sources.append(replay_source(dump, (ROOT / f for f in files)))
    reports = build(changed, removed, sources)
    print(format_report(reports, sources, base=base, thin=args.thin))
    if args.json:
        args.json.write_text(as_json(reports, sources, base) + "\n", encoding="utf-8")
    return exit_code(reports)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--base", help="commit to diff against (default: merge base with main)")
    parser.add_argument(
        "--whole", action="store_true", help="report the reach of every function-body line"
    )
    parser.add_argument("--corpus", type=Path, default=corpus_tool.DEFAULT_CORPUS)
    parser.add_argument(
        "--dump", type=Path, action="append", default=[], help="a full dump (record --all)"
    )
    parser.add_argument(
        "--paths", nargs="*", default=[], help="files or directories (default: the pilot)"
    )
    parser.add_argument("--thin", type=int, default=3, help="flag lines reached by fewer requests")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
