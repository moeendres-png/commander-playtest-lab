"""#1367: MTGJSON is a data quality check only, never a source of the strength index."""

from __future__ import annotations

from pathlib import Path

import commander_lab.studio as studio_package

INDEX_MODULES = ("strength.py", "strength_view.py", "corpus_signals.py", "signals.py")


def _studio_dir() -> Path:
    return Path(studio_package.__file__).resolve().parent


def test_index_modules_exist() -> None:
    for name in INDEX_MODULES:
        assert (_studio_dir() / name).is_file(), name


def test_index_code_does_not_reference_mtgjson() -> None:
    offenders = [
        name
        for name in INDEX_MODULES
        if "mtgjson" in (_studio_dir() / name).read_text(encoding="utf-8").casefold()
    ]
    assert offenders == []


def test_no_studio_module_references_mtgjson() -> None:
    offenders = sorted(
        str(path.relative_to(_studio_dir()))
        for path in _studio_dir().rglob("*.py")
        if "mtgjson" in path.read_text(encoding="utf-8").casefold()
    )
    assert offenders == []
