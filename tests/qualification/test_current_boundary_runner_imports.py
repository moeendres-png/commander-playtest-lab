"""The qualification runner's own imports must resolve.

`run_af03` was added to the runner and it imports `build_deck` from the package,
but `build_deck` was never added to the package's re-exports. The runner
therefore could not be imported at all, and no test caught it, because every test
imports the module it exercises rather than the runner script. The first
bound-source runtime run is what surfaced it.

Importing the runner has module-level side effects by design, so the first two
checks verify the contract structurally. The third resolves the imports for real
against the installed package, which is what the runtime run depends on.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"
INIT = REPO / "src/commander_lab/qualification/current_boundary/__init__.py"
PACKAGE = "commander_lab.qualification.current_boundary"


def _submodule_names() -> set[str]:
    """Modules the runner imports as `from package import module as alias`."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == PACKAGE and node.level == 0:
            for alias in node.names:
                if alias.asname is not None and alias.asname != alias.name:
                    names.add(alias.name)
    return names


def _imported_names() -> set[str]:
    """Names the runner expects the package to provide.

    Submodule imports are excluded: `from package import receipts as receipt_mod`
    binds a module, not an attribute the package must re-export.
    """
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == PACKAGE:
            for alias in node.names:
                if alias.asname is not None and alias.asname != alias.name:
                    continue
                names.add(alias.name)
    return names


def _package_exports() -> set[str]:
    tree = ast.parse(INIT.read_text(encoding="utf-8"))
    exported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            exported.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    for element in ast.walk(node.value):
                        if isinstance(element, ast.Constant) and isinstance(element.value, str):
                            exported.add(element.value)
    return exported


def test_every_package_import_in_the_runner_is_exported() -> None:
    imported = _imported_names()
    assert imported, "the runner imports package names; the parse found none"
    missing = sorted(imported - _package_exports())
    assert not missing, f"runner imports names the package does not export: {missing}"


def test_build_deck_is_exported() -> None:
    """The specific regression: build_deck was used but never re-exported."""
    assert "build_deck" in _package_exports()
    assert "build_deck" in _imported_names()


def test_runner_imports_resolve_against_the_real_package() -> None:
    import importlib
    import sys

    if str(REPO / "src") not in sys.path:
        sys.path.insert(0, str(REPO / "src"))
    module = importlib.import_module(PACKAGE)
    for name in sorted(_imported_names()):
        assert hasattr(module, name), f"{name} is not present on the package"


def test_submodule_imports_are_resolvable() -> None:
    """A submodule alias still has to be a real submodule."""
    import importlib
    import sys

    if str(REPO / "src") not in sys.path:
        sys.path.insert(0, str(REPO / "src"))
    for name in sorted(_submodule_names()):
        assert importlib.import_module(f"{PACKAGE}.{name}") is not None
