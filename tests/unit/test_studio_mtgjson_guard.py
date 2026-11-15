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
    assert _flagged(_PRODUCTION_ROOT) == []


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
