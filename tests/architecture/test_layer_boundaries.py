from __future__ import annotations

import ast
from pathlib import Path


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
