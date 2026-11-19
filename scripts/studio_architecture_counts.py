"""Static counts of the Studio package, so that "better" in the D-0 measuring net is measurable.

Refs #1612 (architecture option D, package D-0 part iii). Reads source files only; nothing is
imported from ``commander_lab``, nothing is written unless ``--out`` is given. Every count is
defined in the docstring of the function that computes it; the recorded values and the command
that produced them are in ``docs/research/studio_architecture_counts_20261119.md``.

The import graph functions (``studio_import_graph``, ``cyclic_components``,
``qualification_imports``) are also what ``tests/architecture/test_layer_boundaries.py`` checks
against its recorded baseline, so the counts here and the architecture test measure the same way.

Usage::

    python scripts/studio_architecture_counts.py [--repo PATH] [--out FILE]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import subprocess
import sys
import tokenize
from collections.abc import Iterable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO_PACKAGE = "commander_lab.studio"
QUALIFICATION_PACKAGE = "commander_lab.qualification"
SQL_METHODS = frozenset({"execute", "executemany", "executescript"})
DUPLICATION_WINDOW = 6
DUPLICATION_MIN_LINE = 8


def line_count(path: Path) -> int:
    """Lines as ``wc -l`` counts them for a file that ends in a newline (``str.splitlines``)."""
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _module_name(root: Path, path: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _import_targets(module: str, node: ast.AST, package: str) -> list[str]:
    """Package-internal targets (dotted, relative to ``package``) of one import statement.

    ``from . import x`` and ``from commander_lab.studio import x`` name ``x`` as a target (it may
    be a submodule; ``studio_import_graph`` drops names that are not modules). Imports of other
    packages give no target here.
    """
    parts = module.split(".")
    targets: list[str] = []
    if isinstance(node, ast.ImportFrom):
        if node.level > 0:
            base = parts[:-1]
            if node.level > 1:
                if node.level - 1 > len(base):
                    return []
                base = base[: len(base) - (node.level - 1)]
            if node.module:
                targets.append(".".join([*base, *node.module.split(".")]))
            else:
                targets.extend(".".join([*base, alias.name]) for alias in node.names)
        elif node.module and (node.module == package or node.module.startswith(package + ".")):
            sub = node.module[len(package) :].lstrip(".")
            if sub:
                targets.append(sub)
            else:
                targets.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.Import):
        targets.extend(
            alias.name[len(package) + 1 :]
            for alias in node.names
            if alias.name.startswith(package + ".")
        )
    return [target.strip(".") for target in targets if target.strip(".")]


def studio_import_graph(
    studio_root: Path, package: str = STUDIO_PACKAGE
) -> tuple[dict[str, set[str]], int]:
    """Module-level import graph of the ``studio`` package and the number of lazy edges.

    A node is a module under ``studio_root`` (``builder``, ``web``, a subpackage module as
    ``a.b``). Every import statement found by ``ast.walk`` counts, so an import inside a function
    body or under ``if TYPE_CHECKING:`` is an edge as well. A target that is not a module is
    reduced to its longest module prefix (``from .store import X`` -> ``store``); a name that
    is no module at all is dropped (``from commander_lab.studio import StudioStore``). Self
    edges are dropped. The second value counts the distinct edges that exist only through an
    import that is not a top-level statement of its module.
    """
    sources = sorted(studio_root.rglob("*.py"))
    known = {_module_name(studio_root, path) for path in sources}

    def resolve(target: str) -> str:
        while target and target not in known:
            target = target.rsplit(".", 1)[0] if "." in target else ""
        return target

    graph: dict[str, set[str]] = {name: set() for name in known}
    top_level: dict[str, set[str]] = {name: set() for name in known}
    for path in sources:
        module = _module_name(studio_root, path)
        tree = _parse(path)
        top_nodes = set(map(id, tree.body))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            for target in _import_targets(module, node, package):
                resolved = resolve(target)
                if resolved and resolved != module:
                    graph[module].add(resolved)
                    if id(node) in top_nodes:
                        top_level[module].add(resolved)
    lazy_only = sum(len(graph[name] - top_level[name]) for name in known)
    return graph, lazy_only


def cyclic_components(graph: Mapping[str, Iterable[str]]) -> list[list[str]]:
    """Strongly connected components with more than one module, each sorted, largest first.

    Iterative Tarjan, so a deep graph cannot hit the recursion limit. Ties in size are ordered
    by the first module name, so the result is deterministic.
    """
    edges = {node: sorted(set(targets)) for node, targets in graph.items()}
    for targets in list(edges.values()):
        for target in targets:
            edges.setdefault(target, [])
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0
    for start in sorted(edges):
        if start in index:
            continue
        work: list[tuple[str, int]] = [(start, 0)]
        while work:
            node, position = work.pop()
            if position == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            targets = edges[node]
            if position < len(targets):
                work.append((node, position + 1))
                target = targets[position]
                if target not in index:
                    work.append((target, 0))
                elif target in on_stack:
                    low[node] = min(low[node], index[target])
                continue
            if low[node] == index[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return sorted(components, key=lambda members: (-len(members), members[0]))


def qualification_imports(
    studio_root: Path, package: str = QUALIFICATION_PACKAGE
) -> dict[str, int]:
    """Import statements under ``studio_root`` that reach the qualification package.

    Key ``"<studio module> -> <imported module>"``, value the number of such statements (an
    import in a function body counts). Matches ``commander_lab.qualification`` and its
    submodules exactly; ``commander_lab.bridge_qualification`` is a different module and does
    not match. A relative import that climbs out of ``studio`` to ``qualification`` matches too.
    """
    found: dict[str, int] = {}
    for path in sorted(studio_root.rglob("*.py")):
        module = _module_name(studio_root, path)
        full = f"{STUDIO_PACKAGE}.{module}".split(".")
        for node in ast.walk(_parse(path)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    names = [node.module] if node.module else []
                elif node.level < len(full):
                    base = full[: len(full) - node.level]
                    if node.module:
                        names = [".".join([*base, node.module])]
                    else:
                        names = [".".join([*base, alias.name]) for alias in node.names]
            for name in names:
                if name == package or name.startswith(package + "."):
                    key = f"{module} -> {name}"
                    found[key] = found.get(key, 0) + 1
    return dict(sorted(found.items()))


def any_uses(paths: Iterable[Path]) -> int:
    """``ast.Name`` with id ``Any`` plus ``ast.Attribute`` with attr ``Any`` (as in
    ``tests/unit/test_any_usage_ratchet.py``; import statements are not counted)."""
    total = 0
    for path in paths:
        for node in ast.walk(_parse(path)):
            if (isinstance(node, ast.Name) and node.id == "Any") or (
                isinstance(node, ast.Attribute) and node.attr == "Any"
            ):
                total += 1
    return total


def function_return_annotations(paths: Iterable[Path]) -> tuple[int, int]:
    """(functions with a return annotation, all functions); nested functions and methods count."""
    annotated = total = 0
    for path in paths:
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                total += 1
                annotated += node.returns is not None
    return annotated, total


def type_ignores(path: Path) -> int:
    """Comments that contain ``type: ignore`` (found by ``tokenize``, so a string is no hit)."""
    source = path.read_text(encoding="utf-8")
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return sum(
        1 for token in tokens if token.type == tokenize.COMMENT and "type: ignore" in token.string
    )


def sql_calls(path: Path) -> int:
    """Calls of a method named ``execute``, ``executemany`` or ``executescript`` (any receiver)."""
    return sum(
        1
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in SQL_METHODS
    )


def keyword_uses(path: Path, keyword: str) -> int:
    """Call keywords with this name (``response_model=...``)."""
    return sum(
        1
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.Call) and any(item.arg == keyword for item in node.keywords)
    )


def _private(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


def _defined_names(paths: Iterable[Path]) -> set[str]:
    names: set[str] = set()
    for path in paths:
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
                    elif isinstance(target, ast.Attribute):
                        names.add(target.attr)
            elif isinstance(node, ast.AnnAssign | ast.AugAssign):
                if isinstance(node.target, ast.Name):
                    names.add(node.target.id)
                elif isinstance(node.target, ast.Attribute):
                    names.add(node.target.attr)
    return names


def private_engine_accesses(studio_paths: list[Path], engine_paths: list[Path]) -> list[str]:
    """Places where Studio code reaches a private name of the engine package.

    A hit is (a) ``from commander_lab.engine... import _name``, (b) an attribute access
    ``obj._name`` or (c) a ``getattr``/``hasattr`` call with the constant ``"_name"``, (b) and
    (c) only in a Studio module that imports from ``commander_lab.engine``, where ``obj`` is not
    ``self``/``cls``/``super()`` and ``_name`` (single leading underscore, not a dunder) is
    defined in the engine package (def, class or assignment) and not defined in any Studio
    module. A Studio subclass that overrides an engine method is not an access here (see
    ``private_engine_overrides``); a call of an engine method on an engine object is. Returns
    ``"<file>:<line> <name>"`` entries.
    """
    engine_names = {name for name in _defined_names(engine_paths) if _private(name)}
    studio_names = _defined_names(studio_paths)
    hits: list[str] = []
    for path in studio_paths:
        tree = _parse(path)
        imports_engine = False
        for node in ast.walk(tree):
            module = (
                node.module
                if isinstance(node, ast.ImportFrom)
                else (node.names[0].name if isinstance(node, ast.Import) else None)
            )
            if module and module.startswith("commander_lab.engine"):
                imports_engine = True
                if isinstance(node, ast.ImportFrom):
                    hits.extend(
                        f"{path.name}:{node.lineno} {alias.name}"
                        for alias in node.names
                        if _private(alias.name)
                    )
        if not imports_engine:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Attribute) and _private(node.attr)):
                continue
            receiver = node.value
            if isinstance(receiver, ast.Name) and receiver.id in {"self", "cls"}:
                continue
            if isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name):
                if receiver.func.id == "super":
                    continue
            if node.attr in engine_names and node.attr not in studio_names:
                hits.append(f"{path.name}:{node.lineno} {node.attr}")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"getattr", "hasattr"}
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and _private(node.args[1].value)
                and node.args[1].value in engine_names
                and node.args[1].value not in studio_names
            ):
                hits.append(f"{path.name}:{node.lineno} {node.args[1].value}")
    return sorted(hits, key=_site_key)


def _site_key(site: str) -> tuple[str, int, str]:
    place, name = site.split(" ", 1)
    file_name, line = place.rsplit(":", 1)
    return file_name, int(line), name


def private_engine_overrides(studio_paths: list[Path], engine_paths: list[Path]) -> list[str]:
    """Private methods (single underscore) of Studio classes that subclass a name imported from
    ``commander_lab.engine`` and that the engine package also defines: a Studio subclass that
    overrides engine internals. ``"<file>:<line> <name>"``.
    """
    engine_names = {name for name in _defined_names(engine_paths) if _private(name)}
    hits: list[str] = []
    for path in studio_paths:
        tree = _parse(path)
        engine_imports = {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("commander_lab.engine")
            for alias in node.names
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {base.id for base in node.bases if isinstance(base, ast.Name)}
            if not bases & engine_imports:
                continue
            hits.extend(
                f"{path.name}:{item.lineno} {item.name}"
                for item in node.body
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                and _private(item.name)
                and item.name in engine_names
            )
    return sorted(hits, key=_site_key)


def duplication(paths: Iterable[Path]) -> dict[str, object]:
    """Exact clone share: windows of ``DUPLICATION_WINDOW`` normalised significant lines that
    occur more than once. A significant line is at least ``DUPLICATION_MIN_LINE`` characters
    after stripping, is not a comment (``#`` for Python, ``//`` otherwise), with whitespace runs
    collapsed. Every line inside a repeated window counts once as duplicated."""
    occurrences: dict[str, list[tuple[str, int]]] = {}
    total = 0
    for path in paths:
        comment = "#" if path.suffix == ".py" else "//"
        lines = []
        for raw in path.read_text(encoding="utf-8", errors="replace").split("\n"):
            stripped = raw.strip()
            if stripped.startswith(comment) or len(stripped) < DUPLICATION_MIN_LINE:
                continue
            lines.append(re.sub(r"\s+", " ", stripped))
        total += len(lines)
        for start in range(len(lines) - DUPLICATION_WINDOW + 1):
            window = "\n".join(lines[start : start + DUPLICATION_WINDOW])
            digest = hashlib.sha256(window.encode("utf-8")).hexdigest()
            occurrences.setdefault(digest, []).append((str(path), start))
    duplicated: set[tuple[str, int]] = set()
    cross_file: set[tuple[str, int]] = set()
    for places in occurrences.values():
        if len(places) < 2:
            continue
        files = {name for name, _ in places}
        for name, start in places:
            for offset in range(start, start + DUPLICATION_WINDOW):
                duplicated.add((name, offset))
                if len(files) > 1:
                    cross_file.add((name, offset))
    share = round(100 * len(duplicated) / total, 1) if total else 0.0
    cross = round(100 * len(cross_file) / total, 1) if total else 0.0
    return {
        "significant_lines": total,
        "duplicated_lines": len(duplicated),
        "duplicated_percent": share,
        "cross_file_percent": cross,
    }


def _calls_which_node(function: ast.AST) -> bool:
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "which"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "node"
        ):
            return True
    return False


def js_executing_tests(test_paths: Iterable[Path]) -> list[str]:
    """Test functions that run JavaScript with ``node``.

    A function "runs node" if its body calls ``<x>.which("node")`` (the repository's way to
    find the binary before ``subprocess.run``), or calls by bare name a module-level function
    of the same file that runs node (transitively). Counted are the ``test_*`` functions that
    run node, as ``"<file>::<test>"``.
    """
    found: list[str] = []
    for path in test_paths:
        tree = _parse(path)
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        runs = {name for name, node in functions.items() if _calls_which_node(node)}
        changed = True
        while changed:
            changed = False
            for name, node in functions.items():
                if name in runs:
                    continue
                called = {
                    call.func.id
                    for call in ast.walk(node)
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                }
                if called & runs:
                    runs.add(name)
                    changed = True
        found.extend(f"{path.name}::{name}" for name in sorted(runs) if name.startswith("test_"))
    return sorted(found)


def _files(root: Path, pattern: str) -> list[Path]:
    return sorted(path for path in root.glob(pattern) if path.is_file())


def _size(paths: list[Path]) -> dict[str, int]:
    return {"files": len(paths), "lines": sum(line_count(path) for path in paths)}


def _git_head(repo: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def collect(repo: Path) -> dict[str, object]:
    """All counts for the checkout at ``repo``."""
    source = repo / "src" / "commander_lab"
    studio = source / "studio"
    studio_py = _files(studio, "**/*.py")
    studio_js = _files(studio / "static", "**/*.js")
    engine_py = _files(source / "engine", "**/*.py")
    studio_tests = _files(repo / "tests" / "unit", "test_studio*.py")
    graph, lazy_only = studio_import_graph(studio)
    components = cyclic_components(graph)
    annotated, functions = function_return_annotations(studio_py)
    sql = {_module_name(studio, path): sql_calls(path) for path in studio_py}
    ignores = {_module_name(studio, path): type_ignores(path) for path in studio_py}
    js_tests = js_executing_tests(_files(repo / "tests", "**/test_*.py"))
    private = private_engine_accesses(studio_py, engine_py)
    overrides = private_engine_overrides(studio_py, engine_py)
    return {
        "repo_head": _git_head(repo),
        "sizes": {
            "src_commander_lab_py": _size(_files(source, "**/*.py")),
            "studio_py": _size(studio_py),
            "studio_static_js": _size(studio_js),
            "engine_py": _size(engine_py),
            "qualification_src_py": _size(_files(source / "qualification", "**/*.py")),
            "tests_unit_py": _size(_files(repo / "tests" / "unit", "**/*.py")),
            "tests_unit_test_studio_py": _size(studio_tests),
        },
        "studio_any_uses": any_uses(studio_py),
        "studio_functions": functions,
        "studio_functions_with_return_annotation": annotated,
        "studio_type_ignore_comments": sum(ignores.values()),
        "studio_type_ignore_by_module": {k: v for k, v in sorted(ignores.items()) if v},
        "studio_sql_calls": sum(sql.values()),
        "studio_modules_with_sql_calls": sum(1 for value in sql.values() if value),
        "studio_sql_calls_by_module": {
            k: v for k, v in sorted(sql.items(), key=lambda kv: (-kv[1], kv[0])) if v
        },
        "studio_web_response_model_keywords": keyword_uses(studio / "web.py", "response_model"),
        "studio_private_engine_accesses": len(private),
        "studio_private_engine_access_sites": private,
        "studio_private_engine_overrides": len(overrides),
        "studio_private_engine_override_sites": overrides,
        "studio_import_graph": {
            "modules": len(graph),
            "edges": sum(len(targets) for targets in graph.values()),
            "edges_only_through_nested_imports": lazy_only,
            "cyclic_components": len(components),
            "largest_cyclic_component": len(components[0]) if components else 0,
            "cyclic_component_members": components,
        },
        "studio_qualification_imports": qualification_imports(studio),
        "duplication_window_6": {
            "studio_py": duplication(studio_py),
            "studio_static_js": duplication(studio_js),
            "engine_py": duplication(engine_py),
            "tests_unit_test_studio_py": duplication(studio_tests),
        },
        "js_executing_test_functions": len(js_tests),
        "js_executing_test_function_names": js_tests,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", type=Path, default=ROOT, help="checkout to measure")
    parser.add_argument("--out", type=Path, help="write the JSON here instead of stdout")
    args = parser.parse_args(argv)
    text = json.dumps(collect(args.repo.resolve()), indent=1, ensure_ascii=False) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
