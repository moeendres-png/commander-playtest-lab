from __future__ import annotations

import os
import subprocess
import sys


def _cold_import(repo_root, statement: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [sys.executable, "-c", statement],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_whole_deck_domain_imports_without_tools_initialization(repo_root) -> None:
    for statement in (
        "import commander_lab.whole_deck.lab_context",
        "from commander_lab.whole_deck.lab import WholeDeckDesignLab",
    ):
        result = _cold_import(repo_root, statement)
        assert result.returncode == 0, result.stderr


def test_import_orders_are_cycle_free(repo_root) -> None:
    statements = (
        "import commander_lab.tools.service; import commander_lab.whole_deck.lab",
        "import commander_lab.whole_deck.lab; import commander_lab.tools.service",
        "import commander_lab.tools.registry; import commander_lab.tools",
        "import commander_lab.tools; import commander_lab.tools.registry",
    )
    for statement in statements:
        result = _cold_import(repo_root, statement)
        assert result.returncode == 0, result.stderr
