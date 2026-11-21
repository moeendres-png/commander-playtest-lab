from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

FORBIDDEN_PREFIXES = {
    "commander_lab.engine.structural": ("commander_lab.agents.openai_workflow", "openai", "agents"),
    "commander_lab.engine.rules": ("commander_lab.agents.openai_workflow", "openai", "agents"),
    "commander_lab.models": ("commander_lab.tools", "commander_lab.api", "commander_lab.agents"),
}


def test_architecture_layer_import_boundaries(repo_root: Path) -> None:
    violations: list[str] = []
    source = repo_root / "src" / "commander_lab"
    for path in source.rglob("*.py"):
        module = ".".join(path.relative_to(repo_root / "src").with_suffix("").parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        for prefix, forbidden in FORBIDDEN_PREFIXES.items():
            if not module.startswith(prefix):
                continue
            for imported in imports:
                if imported.startswith(forbidden):
                    violations.append(f"{module} imports {imported}")
    assert not violations, "\n".join(violations)


# --- studio/ import graph (architecture option D, package D-0, Refs #1612) -----------------------
#
# The graph and the cycle search live in scripts/studio_architecture_counts.py (one definition for
# the recorded counts and for this test). The recorded values are a ratchet in
# tests/fixtures/studio_architecture_baseline.json: they may go down, never up without a review
# reference in the history entry (see studio_baseline_monotonicity_problems). A drop fails too,
# with the value to write into the fixture, so a gain is locked (same convention as
# tests/unit/test_any_usage_ratchet.py).
#
# Limits of this file (Refs #1650): CI runs it on Linux only (the Windows lane
# .github/workflows/windows-runtime.yml selects other tests); the dynamic import forms that are
# not seen are listed in the docstring of scripts/studio_architecture_counts.qualification_imports.

_STUDIO_BASELINE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "studio_architecture_baseline.json"
)


def _studio_counts_module() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "studio_architecture_counts.py"
    spec = importlib.util.spec_from_file_location("studio_architecture_counts_under_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_COUNTS = _studio_counts_module()


def _studio_baseline() -> dict[str, object]:
    loaded = json.loads(_STUDIO_BASELINE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def studio_cycle_violations(components: list[list[str]], baseline: dict[str, object]) -> list[str]:
    """What is wrong with these cyclic components against the recorded baseline (empty: fine)."""
    allowed = set(cast(list[str], baseline["cyclic_modules"]))
    max_components = cast(int, baseline["max_cyclic_components"])
    max_largest = cast(int, baseline["max_largest_cyclic_component"])
    members = {module for component in components for module in component}
    largest = len(components[0]) if components else 0
    problems: list[str] = []
    if len(components) > max_components:
        problems.append(f"{len(components)} import cycles, recorded at most {max_components}")
    if largest > max_largest:
        problems.append(f"largest import cycle has {largest} modules, recorded {max_largest}")
    if members - allowed:
        problems.append(f"modules newly inside an import cycle: {sorted(members - allowed)}")
    return problems


def studio_cycle_gains(components: list[list[str]], baseline: dict[str, object]) -> list[str]:
    """Improvements the fixture should be lowered to (empty: the fixture is exact)."""
    allowed = set(cast(list[str], baseline["cyclic_modules"]))
    members = {module for component in components for module in component}
    largest = len(components[0]) if components else 0
    gains: list[str] = []
    if len(components) < cast(int, baseline["max_cyclic_components"]):
        gains.append(f"max_cyclic_components -> {len(components)}")
    if largest < cast(int, baseline["max_largest_cyclic_component"]):
        gains.append(f"max_largest_cyclic_component -> {largest}")
    if allowed - members:
        gains.append(f"cyclic_modules: remove {sorted(allowed - members)}")
    return gains


def studio_qualification_violations(
    found: dict[str, int], baseline: dict[str, object]
) -> tuple[list[str], list[str]]:
    """(new or grown imports of commander_lab.qualification, recorded exceptions now smaller)."""
    facades = set(cast(list[str], baseline["qualification_facades"]))
    allowed = cast(dict[str, int], baseline["qualification_import_exceptions"])
    outside = {key: count for key, count in found.items() if key.split(" -> ", 1)[0] not in facades}
    grown = [
        f"{key}: {count} import statement(s), recorded {allowed.get(key, 0)}"
        for key, count in sorted(outside.items())
        if count > allowed.get(key, 0)
    ]
    shrunk = [
        f"{key}: recorded {count}, now {outside.get(key, 0)}"
        for key, count in sorted(allowed.items())
        if outside.get(key, 0) < count
    ]
    return grown, shrunk


def _studio_source(repo_root: Path) -> Path:
    return repo_root / "src" / "commander_lab" / "studio"


def test_studio_import_cycles_do_not_grow(repo_root: Path) -> None:
    graph, _lazy = _COUNTS.studio_import_graph(_studio_source(repo_root))
    assert len(graph) > 50, "the scan found the studio package"
    components = _COUNTS.cyclic_components(graph)
    baseline = _studio_baseline()
    problems = studio_cycle_violations(components, baseline)
    assert not problems, (
        "studio/ import cycles grew (an import inside a function body counts as well). Move the "
        "shared code into a module below both sides instead of importing back: "
        + "; ".join(problems)
    )
    gains = studio_cycle_gains(components, baseline)
    assert not gains, (
        "studio/ import cycles shrank. Lock the gain in "
        f"tests/fixtures/studio_architecture_baseline.json: {'; '.join(gains)}"
    )


def test_studio_imports_qualification_only_through_facade_or_recorded_exceptions(
    repo_root: Path,
) -> None:
    found = _COUNTS.qualification_imports(_studio_source(repo_root))
    grown, shrunk = studio_qualification_violations(found, _studio_baseline())
    assert not grown, (
        "studio/ imports commander_lab.qualification outside a facade and beyond the recorded "
        "exceptions: " + "; ".join(grown)
    )
    assert not shrunk, (
        "Fewer studio/ imports of commander_lab.qualification than recorded. Shrink "
        "`qualification_import_exceptions` in tests/fixtures/studio_architecture_baseline.json: "
        + "; ".join(shrunk)
    )


def test_studio_cycle_search_finds_components_of_a_synthetic_graph() -> None:
    graph = {"a": {"b"}, "b": {"c"}, "c": {"a", "d"}, "d": set(), "e": {"f"}, "f": {"e"}}
    assert _COUNTS.cyclic_components(graph) == [["a", "b", "c"], ["e", "f"]]
    assert _COUNTS.cyclic_components({"x": {"y"}, "y": set()}) == []


def test_studio_cycle_check_rejects_a_new_cycle_or_a_bigger_one() -> None:
    baseline: dict[str, object] = {
        "cyclic_modules": ["a", "b", "c"],
        "max_cyclic_components": 1,
        "max_largest_cyclic_component": 3,
    }
    assert studio_cycle_violations([["a", "b", "c"]], baseline) == []
    assert studio_cycle_violations([["a", "b", "c"], ["x", "y"]], baseline)
    assert studio_cycle_violations([["a", "b", "c", "d"]], baseline)
    assert studio_cycle_violations([["a", "b", "x"]], baseline)
    assert studio_cycle_gains([["a", "b"]], baseline) == [
        "max_largest_cyclic_component -> 2",
        "cyclic_modules: remove ['c']",
    ]


def _studio_copy(repo_root: Path, tmp_path: Path) -> Path:
    target = tmp_path / "studio"
    source = _studio_source(repo_root)
    for path in source.rglob("*.py"):
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def test_studio_cycle_check_turns_red_on_an_injected_lazy_import(
    repo_root: Path, tmp_path: Path
) -> None:
    """Mutation check on a copy of the real package: one import in a function body of
    ``store.py`` (which ``builder`` imports) back to ``builder`` closes a bigger cycle."""
    copy = _studio_copy(repo_root, tmp_path)
    baseline = _studio_baseline()
    graph, _lazy = _COUNTS.studio_import_graph(copy)
    assert studio_cycle_violations(_COUNTS.cyclic_components(graph), baseline) == []
    assert "store" in graph["builder"]
    store = copy / "store.py"
    store.write_text(
        store.read_text(encoding="utf-8")
        + "\n\ndef _mutation() -> object:\n    from . import builder\n\n    return builder\n",
        encoding="utf-8",
    )
    graph, _lazy = _COUNTS.studio_import_graph(copy)
    problems = studio_cycle_violations(_COUNTS.cyclic_components(graph), baseline)
    assert any("store" in problem for problem in problems), problems


def test_studio_qualification_check_flags_a_new_import_but_not_bridge_qualification(
    repo_root: Path, tmp_path: Path
) -> None:
    copy = _studio_copy(repo_root, tmp_path)
    baseline = _studio_baseline()
    assert studio_qualification_violations(_COUNTS.qualification_imports(copy), baseline) == (
        [],
        [],
    )
    web = copy / "web.py"
    web.write_text(
        web.read_text(encoding="utf-8") + "\n\ndef _mutation() -> None:\n"
        "    from commander_lab.bridge_qualification import bridge_qualification\n"
        "    from ..qualification.current_boundary import bridge_launcher\n"
        "    del bridge_qualification, bridge_launcher\n",
        encoding="utf-8",
    )
    grown, shrunk = studio_qualification_violations(_COUNTS.qualification_imports(copy), baseline)
    assert grown == [
        "web -> commander_lab.qualification.current_boundary: 1 import statement(s), recorded 0"
    ]
    assert shrunk == []
    facade_baseline = {**baseline, "qualification_facades": ["web"]}
    assert studio_qualification_violations(
        _COUNTS.qualification_imports(copy), facade_baseline
    ) == ([], [])


_STUDIO_RATCHET_FIELDS = (
    "max_cyclic_components",
    "max_largest_cyclic_component",
    "cyclic_modules",
    "qualification_facades",
    "qualification_import_exceptions",
)


# Monotonicity is checked from the entry of this issue on: the step to it (12 -> 13 modules) was
# recorded, not newly allowed, and stays as the one grandfathered raise.
_STUDIO_MONOTONE_AFTER = "#1622"
_REVIEW_REFERENCE = re.compile(r"#\d+|https://github\.com/\S+/(?:pull|issues)/\d+\S*")


def _raised_values(before: dict[str, object], after: dict[str, object]) -> list[str]:
    """Ratchet values that went up (or were widened) from ``before`` to ``after``."""
    raised: list[str] = []
    for field in ("max_cyclic_components", "max_largest_cyclic_component"):
        if cast(int, after[field]) > cast(int, before[field]):
            raised.append(f"{field} {before[field]} -> {after[field]}")
    new_modules = set(cast(list[str], after["cyclic_modules"])) - set(
        cast(list[str], before["cyclic_modules"])
    )
    if new_modules:
        raised.append(f"cyclic_modules added {sorted(new_modules)}")
    new_facades = set(cast(list[str], after["qualification_facades"])) - set(
        cast(list[str], before["qualification_facades"])
    )
    if new_facades:
        raised.append(f"qualification_facades added {sorted(new_facades)}")
    old_exceptions = cast(dict[str, int], before["qualification_import_exceptions"])
    for key, count in sorted(
        cast(dict[str, int], after["qualification_import_exceptions"]).items()
    ):
        if count > old_exceptions.get(key, 0):
            raised.append(
                f"qualification_import_exceptions {key}: {old_exceptions.get(key, 0)} -> {count}"
            )
    return raised


def studio_baseline_monotonicity_problems(history: list[dict[str, object]]) -> list[str]:
    """From the entry ``_STUDIO_MONOTONE_AFTER`` on, every step of the ratchet may only lower
    values. A step that raises (or widens) a value needs ``raise_review`` in its entry: a
    ``#<number>`` or a GitHub pull request / issue link that differs from the entry's own ``ref``,
    i.e. the review that approved the raise. A new ``history`` entry with any reason alone does
    not make a raise pass. Limit: the test sees the file, not git; removing or rewriting
    earlier entries is a diff the pull request review has to catch."""
    anchor = next(
        (i for i, entry in enumerate(history) if entry.get("ref") == _STUDIO_MONOTONE_AFTER), None
    )
    if anchor is None:
        return [f"history has no entry {_STUDIO_MONOTONE_AFTER}, the point monotonicity starts at"]
    problems: list[str] = []
    for index in range(anchor + 1, len(history)):
        raised = _raised_values(history[index - 1], history[index])
        if not raised:
            continue
        review = str(history[index].get("raise_review", ""))
        if not _REVIEW_REFERENCE.fullmatch(review) or review == history[index].get("ref"):
            problems.append(
                f"history[{index}] ({history[index].get('ref')}) raises {raised} without a "
                "`raise_review` (#number or pull request link of the approving review, not "
                "its own ref)"
            )
    return problems


def studio_baseline_history_problems(baseline: dict[str, object]) -> list[str]:
    """A ratchet value changes only together with a new ``history`` entry (date, issue or pull
    request reference, reason), and the top-level values are those of the last entry. Raises
    need a review reference (``studio_baseline_monotonicity_problems``)."""
    history = baseline.get("history")
    if not isinstance(history, list) or not history:
        return ["no history"]
    problems: list[str] = []
    for index, entry in enumerate(history):
        if not isinstance(entry, dict):
            problems.append(f"history[{index}] is no object")
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry.get("date", ""))):
            problems.append(f"history[{index}] has no date YYYY-MM-DD")
        if not re.fullmatch(r"#\d+", str(entry.get("ref", ""))):
            problems.append(f"history[{index}] has no #issue reference")
        if len(str(entry.get("reason", "")).strip()) < 20:
            problems.append(f"history[{index}] has no reason")
        missing = [field for field in _STUDIO_RATCHET_FIELDS if field not in entry]
        if missing:
            problems.append(f"history[{index}] lacks {missing}")
    last = history[-1]
    if isinstance(last, dict):
        changed = [f for f in _STUDIO_RATCHET_FIELDS if baseline.get(f) != last.get(f)]
        if changed:
            problems.append(f"values changed without a history entry: {changed}")
    if not problems:
        problems.extend(
            studio_baseline_monotonicity_problems(cast(list[dict[str, object]], history))
        )
    return problems


def test_studio_architecture_baseline_changes_are_recorded_with_a_reason() -> None:
    baseline = _studio_baseline()
    assert studio_baseline_history_problems(baseline) == []
    raised = {**baseline, "max_largest_cyclic_component": 99}
    assert studio_baseline_history_problems(raised) == [
        "values changed without a history entry: ['max_largest_cyclic_component']"
    ]
    history = cast(list[dict[str, object]], baseline["history"])
    unexplained = {**baseline, "history": [*history[:-1], {**history[-1], "reason": ""}]}
    assert studio_baseline_history_problems(unexplained) == [
        f"history[{len(history) - 1}] has no reason"
    ]


def test_studio_qualification_check_sees_parent_and_dynamic_imports(
    repo_root: Path, tmp_path: Path
) -> None:
    copy = _studio_copy(repo_root, tmp_path)
    baseline = _studio_baseline()
    web = copy / "web.py"
    web.write_text(
        web.read_text(encoding="utf-8") + "\n\ndef _mutation() -> None:\n"
        "    import importlib\n"
        "    from commander_lab import qualification\n"
        "    from .. import qualification as again\n"
        "    importlib.import_module('commander_lab.qualification.current_boundary')\n"
        "    del qualification, again\n",
        encoding="utf-8",
    )
    grown, _shrunk = studio_qualification_violations(_COUNTS.qualification_imports(copy), baseline)
    assert grown == [
        "web -> commander_lab.qualification: 2 import statement(s), recorded 0",
        "web -> commander_lab.qualification.current_boundary: 1 import statement(s), recorded 0",
    ]


def test_studio_private_override_count_follows_studio_subclasses(tmp_path: Path) -> None:
    engine = tmp_path / "engine.py"
    engine.write_text("class Runner:\n    def _drive(self): ...\n", encoding="utf-8")
    first = tmp_path / "first.py"
    first.write_text(
        "from commander_lab.engine.rules import Runner\n"
        "class Recording(Runner):\n    def _drive(self): ...\n",
        encoding="utf-8",
    )
    second = tmp_path / "second.py"
    second.write_text(
        "from .first import Recording\n"
        "class Batch(Recording):\n    def _drive(self): ...\n"
        "class Other:\n    def _drive(self): ...\n",
        encoding="utf-8",
    )
    assert _COUNTS.private_engine_overrides([first, second], [engine]) == [
        "first.py:3 _drive",
        "second.py:3 _drive",
    ]


# --- one protocol driver (D-3, Refs #1663) -------------------------------------------------------
#
# The Studio series session speaks to the bridge only through the runner's public step sequence
# (XmageFullGameRunner.decision_policy / open_session, FullGameBridgeSession, FullGameMatch). The
# floor is 0, so the ratchet is an equality; studio/ follows in the second package of #1663.


def _runner_modules(repo_root: Path) -> list[Path]:
    rules = repo_root / "src" / "commander_lab" / "engine" / "rules"
    return [rules / name for name in _COUNTS.RUNNER_MODULES]


def test_full_game_series_reaches_no_private_runner_name(repo_root: Path) -> None:
    series = repo_root / "src" / "commander_lab" / "engine" / "rules" / "full_game_series.py"
    assert _COUNTS.private_runner_accesses([series], _runner_modules(repo_root)) == []


#: Private runner names reached from studio/ (strict count): 12 on main d63a6e64, 0 since the
#: second package of #1663 (PLAY on the public steps). May only go down.
STUDIO_PRIVATE_RUNNER_ACCESS_CEILING = 0

#: ``type: ignore`` comments in studio/play.py: 18 on main d63a6e64, the acceptance of #1663 allows
#: at most 2; held at the value the second package reached. May only go down.
PLAY_TYPE_IGNORE_CEILING = 1

#: Studio overrides of private engine hooks, frozen (file, name); a new one needs a review. They
#: are not counted as accesses (#1663, recommendation B of the first package): a subclass hook
#: that ``run()`` itself calls. Their number (3) is a ratchet of its own; removing one means
#: removing it here too.
STUDIO_PRIVATE_OVERRIDES = {
    ("play.py", "_drive"),
    ("play.py", "_validated_policy"),
    ("play_batch.py", "_drive"),
}


def _studio_and_engine_files(repo_root: Path) -> tuple[list[Path], list[Path]]:
    source = repo_root / "src" / "commander_lab"
    return (
        sorted((source / "studio").rglob("*.py")),
        sorted((source / "engine").rglob("*.py")),
    )


def test_studio_private_runner_accesses_do_not_grow(repo_root: Path) -> None:
    studio, _engine = _studio_and_engine_files(repo_root)
    sites = _COUNTS.private_runner_accesses(studio, _runner_modules(repo_root))
    assert len(sites) <= STUDIO_PRIVATE_RUNNER_ACCESS_CEILING, sites


def test_play_type_ignores_do_not_grow(repo_root: Path) -> None:
    play = repo_root / "src" / "commander_lab" / "studio" / "play.py"
    assert _COUNTS.type_ignores(play) <= PLAY_TYPE_IGNORE_CEILING


def _raw_client_reads(path: Path) -> list[int]:
    """Lines where ``path`` reads an attribute named ``client`` (the raw bridge client behind
    ``FullGameBridgeSession.client``), in any form."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if (isinstance(node, ast.Attribute) and node.attr == "client")
        or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "hasattr", "setattr"}
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "client"
        )
    )


def test_play_never_reaches_the_raw_bridge_client(repo_root: Path) -> None:
    """PLAY reads every status through a step of its match, which audits it before it is
    published (#1663 cross review P2-2): no ``<session>.client`` (0, may only stay 0)."""
    play = repo_root / "src" / "commander_lab" / "studio" / "play.py"
    assert _raw_client_reads(play) == []


def test_the_raw_client_scan_sees_each_form(tmp_path: Path) -> None:
    probe = tmp_path / "probe.py"
    for line in (
        'bridge.client.request("start_full_game")',
        "raw = self._bridge.client",
        'getattr(bridge, "client").request("x")',
    ):
        probe.write_text(line + "\n", encoding="utf-8")
        assert _raw_client_reads(probe) == [1], line


def test_studio_overrides_of_private_engine_hooks_are_frozen(repo_root: Path) -> None:
    studio, engine = _studio_and_engine_files(repo_root)
    sites = _COUNTS.private_engine_overrides(studio, engine)
    found = {(place.split(":", 1)[0], name) for place, name in (s.split(" ") for s in sites)}
    assert found == STUDIO_PRIVATE_OVERRIDES


def _calls_super(function: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
        and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Name)
        and node.func.value.func.id == "super"
        for node in ast.walk(function)
    )


def test_every_studio_drive_override_keeps_the_runner_drive(repo_root: Path) -> None:
    """An override of ``_drive`` that skips ``super()._drive`` would switch off the per-frame
    hidden-information audit and the runner's loop without a trace."""
    studio, engine = _studio_and_engine_files(repo_root)
    by_name = {path.name: path for path in studio}
    checked = 0
    for site in _COUNTS.private_engine_overrides(studio, engine):
        place, name = site.split(" ")
        if name != "_drive":
            continue
        file_name, line = place.rsplit(":", 1)
        tree = ast.parse(by_name[file_name].read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.lineno == int(line)
        )
        assert _calls_super(function, "_drive"), site
        checked += 1
    assert checked == 2


def test_the_super_check_sees_a_drive_override_without_super() -> None:
    tree = ast.parse(
        "class A(R):\n    def _drive(self, c, p):\n        return self._other(c)\n"
        "class B(R):\n    def _drive(self, c, p):\n        return super()._drive(c, p)\n"
    )
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert [_calls_super(function, "_drive") for function in functions] == [False, True]


_RUNNER_FIXTURE = (
    "_STARTUP_ATTEMPTS = 4\n"
    "class Runner:\n"
    "    def __init__(self):\n"
    "        self._hidden_audit = None\n"
    "    def _drive(self): ...\n"
    "    @staticmethod\n"
    "    def _sha256(value): ...\n"
)


@pytest.mark.parametrize(
    ("line", "name"),
    [
        ("runner._drive()", "_drive"),
        ("runner._hidden_audit = object()", "_hidden_audit"),
        ("Runner._sha256(1)", "_sha256"),
        ("from .full_game import _STARTUP_ATTEMPTS", "_STARTUP_ATTEMPTS"),
        ("from commander_lab.engine.rules.full_game_batch import _other", "_other"),
        ("getattr(runner, '_hidden_audit')", "_hidden_audit"),
        ("setattr(runner, '_drive', None)", "_drive"),
        ("self._runner._drive()", "_drive"),
    ],
)
def test_private_runner_scan_turns_red_on_each_access_form(
    tmp_path: Path, line: str, name: str
) -> None:
    full_game = tmp_path / "full_game.py"
    full_game.write_text(_RUNNER_FIXTURE, encoding="utf-8")
    batch = tmp_path / "full_game_batch.py"
    batch.write_text("def _other(): ...\n", encoding="utf-8")
    caller = tmp_path / "caller.py"
    caller.write_text(f"def play(runner):\n    {line}\n", encoding="utf-8")
    assert _COUNTS.private_runner_accesses([caller], [full_game, batch]) == [f"caller.py:2 {name}"]


def test_private_runner_scan_ignores_own_attributes_and_other_modules(tmp_path: Path) -> None:
    full_game = tmp_path / "full_game.py"
    full_game.write_text(_RUNNER_FIXTURE, encoding="utf-8")
    caller = tmp_path / "caller.py"
    caller.write_text(
        "from .full_game_pilot.common import _StrictModel\n"
        "class Session:\n"
        "    def _drive(self):\n"
        "        self._drive()\n"
        "        super()._drive()\n"
        "        return self._hidden_audit\n",
        encoding="utf-8",
    )
    assert _COUNTS.private_runner_accesses([caller], [full_game]) == []


def _history_entry(**changes: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "date": "2026-11-20",
        "ref": "#1700",
        "reason": "a reason that is long enough to count",
        "max_cyclic_components": 1,
        "max_largest_cyclic_component": 13,
        "cyclic_modules": ["a", "b"],
        "qualification_facades": [],
        "qualification_import_exceptions": {"doctor -> commander_lab.qualification.x": 1},
    }
    entry.update(changes)
    return entry


def test_studio_baseline_history_checks_monotonicity_from_1622_on() -> None:
    anchor = _history_entry(ref="#1622", max_largest_cyclic_component=13)
    first = _history_entry(ref="#1612", max_largest_cyclic_component=12)
    # the recorded raise to the anchor (12 -> 13) is grandfathered
    assert studio_baseline_monotonicity_problems([first, anchor]) == []
    # lowering needs no extra approval
    lower = _history_entry(ref="#1701", max_largest_cyclic_component=12, cyclic_modules=["a"])
    assert studio_baseline_monotonicity_problems([first, anchor, lower]) == []
    # a new entry with any reason is not enough to raise
    raises: list[dict[str, object]] = [
        _history_entry(max_cyclic_components=2),
        _history_entry(max_largest_cyclic_component=14),
        _history_entry(cyclic_modules=["a", "b", "c"]),
        _history_entry(qualification_facades=["web"]),
        _history_entry(
            qualification_import_exceptions={"doctor -> commander_lab.qualification.x": 2}
        ),
        _history_entry(qualification_import_exceptions={"web -> commander_lab.qualification.y": 1}),
    ]
    for raised in raises:
        problems = studio_baseline_monotonicity_problems([first, anchor, raised])
        assert len(problems) == 1 and "without a `raise_review`" in problems[0], raised
        reviewed = {**raised, "raise_review": "#1699"}
        assert studio_baseline_monotonicity_problems([first, anchor, reviewed]) == []
    # the review reference must be a reference, and not the entry's own issue
    for bad in ("", "approved", "#abc", "#1700"):
        raised = {**raises[0], "raise_review": bad}
        assert studio_baseline_monotonicity_problems([first, anchor, raised]), bad
    link = {**raises[0], "raise_review": "https://github.com/o/r/pull/1699#pullrequestreview-1"}
    assert studio_baseline_monotonicity_problems([first, anchor, link]) == []
    # without the anchor entry the check cannot tell where it starts
    assert studio_baseline_monotonicity_problems([first, lower]) == [
        "history has no entry #1622, the point monotonicity starts at"
    ]


def test_studio_baseline_history_problems_report_an_unreviewed_raise() -> None:
    baseline = _studio_baseline()
    history = cast(list[dict[str, object]], baseline["history"])
    last = history[-1]
    bigger = {**last, "ref": "#1700", "max_largest_cyclic_component": 14}
    raised = {**baseline, **{k: bigger[k] for k in _STUDIO_RATCHET_FIELDS}}
    raised["history"] = [*history, bigger]
    problems = studio_baseline_history_problems(raised)
    # the step from the recorded value (12 since #1679, 13 before) to 14 is named
    step = f"max_largest_cyclic_component {last['max_largest_cyclic_component']} -> 14"
    assert len(problems) == 1 and step in problems[0]
    raised["history"] = [*history, {**bigger, "raise_review": "#1699"}]
    assert studio_baseline_history_problems(raised) == []


_DYNAMIC_IMPORT_FORMS = {
    "fromlist": "__import__('commander_lab', fromlist=['qualification'])",
    "fromlist_positional": "__import__('commander_lab', None, None, ['qualification'])",
    "fromlist_tuple": "__import__('commander_lab', fromlist=('qualification',))",
    "fromlist_inside_package": "__import__('commander_lab.qualification', fromlist=['x'])",
    "relative_with_package": "importlib.import_module('.qualification', 'commander_lab')",
    "relative_package_keyword": "importlib.import_module('.qualification', package='commander_lab')",
    "relative_name_keyword": "importlib.import_module(name='commander_lab.qualification')",
    "relative_two_levels_package_dunder": "importlib.import_module('..qualification', __package__)",
    "relative_from_the_qualification_package": (
        "importlib.import_module('.', 'commander_lab.qualification')"
    ),
    "alias_from_import": "im('commander_lab.qualification')",
    "alias_assignment": "again('commander_lab.qualification')",
    "alias_builtins_import": "dunder('commander_lab.qualification')",
    "alias_module": "il.import_module('commander_lab.qualification')",
}

_DYNAMIC_IMPORT_UNSEEN = {
    "variable": "importlib.import_module(name)",
    "f_string": "importlib.import_module(f'commander_lab.{name}')",
    "relative_without_package": "importlib.import_module('.qualification')",
    "relative_with_variable_package": "importlib.import_module('.qualification', pkg)",
    "relative_above_the_root": "importlib.import_module('....qualification', 'commander_lab')",
    "other_package": "importlib.import_module('.qualification', 'commander_lab.bridge')",
    "bridge_qualification": "importlib.import_module('.bridge_qualification', 'commander_lab')",
    "fromlist_other": "__import__('commander_lab', fromlist=['bridge_qualification'])",
    "fromlist_variable": "__import__('commander_lab', fromlist=names)",
    "getattr_indirection": "getattr(importlib, 'import_module')('commander_lab.qualification')",
}

_DYNAMIC_IMPORT_PRELUDE = (
    "import importlib\n"
    "import importlib as il\n"
    "from importlib import import_module as im\n"
    "from builtins import __import__ as dunder\n"
    "again = importlib.import_module\n"
)


def _synthetic_studio(tmp_path: Path, statement: str) -> Path:
    root = tmp_path / "studio"
    root.mkdir(parents=True)
    (root / "web.py").write_text(
        _DYNAMIC_IMPORT_PRELUDE
        + f"\n\ndef _mutation(name, pkg, names) -> None:\n    {statement}\n",
        encoding="utf-8",
    )
    return root


def test_studio_qualification_scan_sees_each_constant_dynamic_import_form(tmp_path: Path) -> None:
    for form, statement in _DYNAMIC_IMPORT_FORMS.items():
        found = _COUNTS.qualification_imports(_synthetic_studio(tmp_path / form, statement))
        assert sum(found.values()) == 1, (form, found)
        assert all(key.startswith("web -> commander_lab.qualification") for key in found), found
    assert _COUNTS.qualification_imports(
        _synthetic_studio(tmp_path / "fromlist_name", _DYNAMIC_IMPORT_FORMS["fromlist"])
    ) == {"web -> commander_lab.qualification": 1}
    assert _COUNTS.qualification_imports(
        _synthetic_studio(tmp_path / "pkg_name", _DYNAMIC_IMPORT_FORMS["relative_with_package"])
    ) == {"web -> commander_lab.qualification": 1}
    assert _COUNTS.qualification_imports(
        _synthetic_studio(
            tmp_path / "dunder_pkg", _DYNAMIC_IMPORT_FORMS["relative_two_levels_package_dunder"]
        )
    ) == {"web -> commander_lab.qualification": 1}


def test_studio_qualification_scan_documents_the_dynamic_imports_it_does_not_see(
    tmp_path: Path,
) -> None:
    """The boundary named in the docstring of ``qualification_imports``: these stay invisible
    (a run-time name or package) or are no import of the watched package at all."""
    assert len(_DYNAMIC_IMPORT_UNSEEN) >= 8
    for form, statement in _DYNAMIC_IMPORT_UNSEEN.items():
        found = _COUNTS.qualification_imports(_synthetic_studio(tmp_path / form, statement))
        assert found == {}, (form, found)


def test_studio_qualification_check_turns_red_on_each_dynamic_import_form(
    repo_root: Path, tmp_path: Path
) -> None:
    """Mutation check on a copy of the real package for the three forms of #1650."""
    baseline = _studio_baseline()
    forms = {
        "fromlist": "__import__('commander_lab', fromlist=['qualification'])",
        "relative_with_package": "import_module('.qualification', 'commander_lab')",
        "alias": "im('commander_lab.qualification')",
    }
    assert len(forms) == 3
    for form, call in forms.items():
        copy = _studio_copy(repo_root, tmp_path / form)
        assert studio_qualification_violations(_COUNTS.qualification_imports(copy), baseline) == (
            [],
            [],
        )
        web = copy / "web.py"
        web.write_text(
            web.read_text(encoding="utf-8") + "\n\ndef _mutation_1650() -> None:\n"
            "    from importlib import import_module as im\n"
            "    from importlib import import_module\n"
            f"    {call}\n"
            "    del im, import_module\n",
            encoding="utf-8",
        )
        grown, _shrunk = studio_qualification_violations(
            _COUNTS.qualification_imports(copy), baseline
        )
        assert grown == ["web -> commander_lab.qualification: 1 import statement(s), recorded 0"], (
            form,
            grown,
        )
