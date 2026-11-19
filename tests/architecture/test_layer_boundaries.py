from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

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
# tests/fixtures/studio_architecture_baseline.json: they may go down, never up. A drop fails too,
# with the value to write into the fixture, so a gain is locked (same convention as
# tests/unit/test_any_usage_ratchet.py).

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
