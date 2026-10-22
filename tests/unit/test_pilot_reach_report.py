"""Reach report: which changed pilot lines does a replay of real requests run? (#961 R-1)

The mechanics are tested on small modules written for the test, with a branch that no request
can enter as the negative control; the real corpus is replayed once to prove the monitor sees
the pilot.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_reach_report.py"
spec = importlib.util.spec_from_file_location("pilot_reach_report_under_test", SCRIPT)
assert spec and spec.loader
reach = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reach  # dataclasses look their module up here
spec.loader.exec_module(reach)

SOURCE = textwrap.dedent(
    '''\
    """Module doc."""
    LIMIT = 3


    class Box:
        size = 2

        def grow(self, n):
            """Doc string."""
            total = n + self.size
            if total > LIMIT:
                return "big"
            # a comment
            return "small"


    def never(x):
        if x == "unreachable":
            return x.upper()
        return x
    '''
)


def _import(tmp_path: Path, name: str, source: str) -> ModuleType:
    path = tmp_path / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    module_spec = importlib.util.spec_from_file_location(name, path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


# --- the diff ------------------------------------------------------------------------------


def test_parse_diff_reads_changed_added_and_removed_lines() -> None:
    text = textwrap.dedent(
        """\
        diff --git a/pkg/a.py b/pkg/a.py
        --- a/pkg/a.py
        +++ b/pkg/a.py
        @@ -3,2 +3,3 @@ def f():
        -old
        -older
        +new
        +newer
        +newest
        @@ -10 +11 @@ def g():
        -x
        +y
        @@ -20,2 +20,0 @@ def h():
        -gone
        -gone too
        diff --git a/pkg/b.py b/pkg/b.py
        new file mode 100644
        --- /dev/null
        +++ b/pkg/b.py
        @@ -0,0 +1,2 @@
        +one
        +two
        diff --git a/pkg/c.py b/pkg/c.py
        deleted file mode 100644
        --- a/pkg/c.py
        +++ /dev/null
        @@ -1,4 +0,0 @@
        -a
        """
    )
    changed, removed = reach.parse_diff(text)
    assert changed["pkg/a.py"] == {3, 4, 5, 11}
    assert removed["pkg/a.py"] == 2 + 1 + 2
    assert changed["pkg/b.py"] == {1, 2}
    assert "pkg/c.py" not in changed


def _repo(tmp_path: Path) -> Path:
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@example.org", "-c", "user.name=t", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    (tmp_path / "pilot").mkdir()
    (tmp_path / "pilot" / "a.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("x = 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    return tmp_path


def test_changed_lines_sees_committed_dirty_and_untracked_files(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "pilot" / "a.py").write_text("a = 1\nb = 20\nc = 3\nd = 4\n", encoding="utf-8")
    (repo / "pilot" / "new.py").write_text("n = 1\nm = 2\n", encoding="utf-8")
    (repo / "other.py").write_text("x = 2\n", encoding="utf-8")
    changed, removed = reach.changed_lines("HEAD", ["pilot"], cwd=repo)
    assert changed == {"pilot/a.py": {2, 4}, "pilot/new.py": {1, 2}}
    assert removed["pilot/a.py"] == 1
    assert reach.pilot_files(["pilot"], cwd=repo) == ["pilot/a.py", "pilot/new.py"]


def test_changed_lines_refuses_an_unknown_base(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(reach.Refusal):
        reach.changed_lines("no-such-commit", ["pilot"], cwd=repo)


# --- which lines can run -------------------------------------------------------------------


def test_executable_lines_tell_function_bodies_from_import_time_code() -> None:
    shape = reach.executable_lines(SOURCE)
    source_lines = SOURCE.splitlines()

    def line_of(text: str) -> int:
        return next(i for i, line in enumerate(source_lines, 1) if text in line)

    assert shape.call[line_of("total = n")] == "Box.grow"
    assert shape.call[line_of('return "small"')] == "Box.grow"
    assert shape.call[line_of("x.upper()")] == "never"
    assert line_of("LIMIT = 3") in shape.load
    assert line_of("size = 2") in shape.load
    assert line_of("def grow") in shape.load
    assert line_of('"""Module doc."""') in shape.load  # it is stored when the file is imported
    for text in ('"""Doc string."""', "# a comment"):
        number = line_of(text)
        assert number not in shape.call and number not in shape.load, text
    # The signature of a function is not one of its body lines.
    assert line_of("def never") not in shape.call


# --- which lines ran -----------------------------------------------------------------------


def test_monitor_counts_a_line_once_per_request_and_per_label(tmp_path: Path) -> None:
    module = _import(tmp_path, "reach_toy_a", SOURCE)
    path = str(tmp_path / "reach_toy_a.py")
    shape = reach.executable_lines(SOURCE)
    big = next(i for i, line in enumerate(SOURCE.splitlines(), 1) if 'return "big"' in line)
    small = next(i for i, line in enumerate(SOURCE.splitlines(), 1) if 'return "small"' in line)
    with reach.LineMonitor([path]) as monitor:
        for label, n in (("a", 1), ("a", 1), ("b", 9)):
            monitor.begin(label)
            for _ in range(5):  # a line in a loop still counts once for the request
                module.Box().grow(n)
            monitor.end()
        module.never("outside the monitored window")
    real = str((tmp_path / "reach_toy_a.py").resolve())
    assert monitor.hits[(real, big)] == {"b": 1}
    assert monitor.hits[(real, small)] == {"a": 2}
    unreached = [line for line in shape.call if (real, line) not in monitor.hits]
    assert unreached, "the function `never` ran outside any request and is not counted"


def test_monitor_frees_its_tool_and_refuses_when_none_is_free() -> None:
    for _ in range(2):
        with reach.LineMonitor([]):
            pass
    mon = sys.monitoring
    taken = []
    try:
        for tool in (mon.COVERAGE_ID, 3, 4):
            mon.use_tool_id(tool, "test-holder")
            taken.append(tool)
        with pytest.raises(reach.Refusal), reach.LineMonitor([]):
            pass
    finally:
        for tool in taken:
            mon.free_tool_id(tool)


# --- the report ----------------------------------------------------------------------------


def _report(tmp_path: Path, changed_text: str, lines: set[int]) -> list[Any]:
    """Run the toy module on a small `grow` request and build the report for ``lines``."""
    module = _import(tmp_path, "reach_toy_b", SOURCE)
    path = tmp_path / "reach_toy_b.py"
    with reach.LineMonitor([str(path)]) as monitor:
        monitor.begin("priority")
        module.Box().grow(1)
        monitor.end()
    source = reach.Source("toy", requests=1, raised=0, hits=monitor.hits)
    return reach.build({path.name: lines}, {path.name: 0}, [source], cwd=tmp_path)


def _line(text: str) -> int:
    return next(i for i, line in enumerate(SOURCE.splitlines(), 1) if text in line)


def test_a_changed_line_in_a_branch_no_request_enters_is_reported_not_reached(
    tmp_path: Path,
) -> None:
    """Negative control: `never` is changed, and the replay only runs `grow`."""
    live, dead = _line('return "small"'), _line("x.upper()")
    reports = _report(tmp_path, "", {live, dead})
    (report,) = reports
    assert sorted(report.reached) == [live]
    assert report.unreached == [dead]
    assert report.executable[dead] == "never"
    assert reach.verdict(reports) == "SOME_NOT_REACHED"
    assert reach.exit_code(reports) == 1
    text = reach.format_report(reports, [reach.Source("toy", 1, 0)], base="abc123", thin=3)
    assert "not reached: never: line" in text and "SOME_NOT_REACHED" in text


def test_a_change_the_replay_enters_is_reached_with_its_decision_class(tmp_path: Path) -> None:
    live = _line('return "small"')
    reports = _report(tmp_path, "", {live})
    assert reach.verdict(reports) == "ALL_REACHED"
    assert reach.exit_code(reports) == 0
    assert reports[0].classes[live] == ["priority"]


def test_changes_that_hold_no_instruction_are_not_a_pass_or_a_failure(tmp_path: Path) -> None:
    comment, constant = _line("# a comment"), _line("LIMIT = 3")
    reports = _report(tmp_path, "", {comment, constant})
    assert reach.verdict(reports) == "NOTHING_EXECUTABLE"
    assert reach.exit_code(reports) == 0
    assert reports[0].load_lines == [constant]
    assert reports[0].non_executable == 1
    assert reach.verdict([]) == "NO_PILOT_CHANGE"


def test_a_line_reached_by_one_request_is_called_thin(tmp_path: Path) -> None:
    reports = _report(tmp_path, "", {_line('return "small"')})
    text = reach.format_report(reports, [reach.Source("toy", 1, 0)], base="abc", thin=3)
    assert "reached by fewer than 3 requests" in text


def test_ranges_fold_consecutive_lines() -> None:
    assert reach.ranges([9, 3, 4, 5, 7]) == "3-5, 7, 9"
    assert reach.ranges([]) == ""


# --- the real corpus -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def whole_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[int, dict[str, Any]]:
    out = tmp_path_factory.mktemp("reach") / "reach.json"
    code = reach.main(
        ["--whole", "--paths", "src/commander_lab/engine/rules/full_game_pilot", "--json", str(out)]
    )
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_the_corpus_replay_reaches_the_pilot_and_names_the_decision_classes(
    whole_run: tuple[int, dict[str, Any]],
) -> None:
    code, payload = whole_run
    assert code in (0, 1)
    assert payload["sources"][0]["requests"] >= 300 and payload["sources"][0]["raised"] == 0
    policy = payload["files"]["src/commander_lab/engine/rules/full_game_pilot/policy.py"]
    assert len(policy["reached"]) > len(policy["function_body"]) * 0.5
    classes = {name for names in policy["classes"].values() for name in names}
    assert {"priority", "mana_payment", "target", "declare_attacker"} <= classes
    setup = {name for f in payload["files"].values() for v in f["classes"].values() for name in v}
    assert reach.SETUP in setup, "constructing the policy is a labelled step of its own"


def test_watching_restores_the_policy_and_the_corpus_hook() -> None:
    from commander_lab.engine.rules.full_game_pilot import ExternalPilotDecisionPolicy

    decide, fresh = ExternalPilotDecisionPolicy.decide, reach.corpus_tool.fresh_policy
    with reach.LineMonitor([]) as monitor, reach.watching(monitor):
        assert ExternalPilotDecisionPolicy.decide is not decide
    assert ExternalPilotDecisionPolicy.decide is decide
    assert reach.corpus_tool.fresh_policy is fresh


def test_a_full_dump_is_replayed_as_played_and_reaches_the_same_lines(tmp_path: Path) -> None:
    corpus_tool = reach.corpus_tool
    _, rows = corpus_tool.load_corpus()
    full = [r for r in rows if r["stateless"]][:60]
    dump = tmp_path / "dump.jsonl.gz"
    corpus_tool.write_corpus(dump, {"corpus_version": 1, "kind": "full"}, full)
    files = reach.pilot_files(["src/commander_lab/engine/rules/full_game_pilot"])
    source = reach.replay_source(dump, (ROOT / f for f in files))
    assert (source.requests, source.raised) == (60, 0)
    assert any(label != reach.SETUP for hits in source.hits.values() for label in hits)
    args = type("Args", (), {"corpus": dump})()
    assert corpus_tool.diff(args) == 0


def test_a_missing_corpus_is_a_refusal_with_exit_code_two(tmp_path: Path) -> None:
    assert reach.main(["--whole", "--corpus", str(tmp_path / "none.jsonl.gz")]) == 2
