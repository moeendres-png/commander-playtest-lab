"""Guard: MTGJSON is a one-off research cross-check (issue #1367), never a data source.

The MTGJSON bulk was used once, locally, to sanity-check the stored
``edhrec_global_inclusion`` signal; the analysis script lives in ``scripts/``. No
production code path under ``src/commander_lab`` may read, import or even name MTGJSON:
if that ever changes, it must be a deliberate, reviewed decision, not an accident. The
second test is the negative control: it proves the scan actually flags a planted
reference, so the first test cannot pass for the wrong reason (an empty or broken scan).
"""

from __future__ import annotations

from pathlib import Path

_NEEDLE = "mtgjson"
_PRODUCTION_ROOT = Path(__file__).resolve().parents[2] / "src" / "commander_lab"

# The one deliberate exception (Owner decision 2026-11-19, issue #1553, "Option A"): the
# checked-in MTGJSON print data is a source for German card NAMES only (deck builder search
# and deck list import resolution; no prices, no other production path). Exactly this file.
_ALLOWED = (_PRODUCTION_ROOT / "studio" / "german_names.py",)


def _allowed(path: Path) -> bool:
    """The allowed file, or its compiled copy (the scan reads every file type)."""
    return any(
        path == item
        or (path.parent == item.parent / "__pycache__" and path.name.startswith(item.stem + "."))
        for item in _ALLOWED
    )


def _flagged(root: Path) -> list[Path]:
    """Every file below ``root`` whose text names MTGJSON, case-insensitively.

    All file types are scanned, not only Python: the Studio ships JS/HTML/CSS
    under the same tree, and the guard's claim covers every production source.
    """
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and _NEEDLE in path.read_text(encoding="utf-8", errors="ignore").casefold()
    )


def test_no_mtgjson_reference_in_production_sources() -> None:
    assert _PRODUCTION_ROOT.is_dir()
    assert [path for path in _flagged(_PRODUCTION_ROOT) if not _allowed(path)] == []


def test_the_exception_is_exactly_one_file_and_is_still_needed() -> None:
    assert len(_ALLOWED) == 1
    assert [p for p in _flagged(_PRODUCTION_ROOT) if _allowed(p)] != []
    assert [p for p in _flagged(_PRODUCTION_ROOT) if p.suffix == ".py" and _allowed(p)] == list(
        _ALLOWED
    )


def test_scan_flags_a_planted_reference(tmp_path: Path) -> None:
    planted = tmp_path / "uses_it.py"
    planted.write_text("SOURCE = 'MTGJSON bulk'\n", encoding="utf-8")
    clean = tmp_path / "clean.py"
    clean.write_text("SOURCE = 'edhrec export'\n", encoding="utf-8")
    nested = tmp_path / "sub" / "deep.py"
    nested.parent.mkdir()
    nested.write_text("import mtgjson_loader\n", encoding="utf-8")
    script = tmp_path / "uses_it.js"
    script.write_text("const SOURCE = 'mtgjson bulk';\n", encoding="utf-8")
    assert _flagged(tmp_path) == sorted([planted, nested, script])
