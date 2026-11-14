from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "ci_ruff_annotations", ROOT / "scripts/ci_ruff_annotations.py"
)
assert _spec is not None and _spec.loader is not None
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


def test_annotation_format_and_escaping() -> None:
    item = {
        "code": "F401",
        "message": "unused\nimport 100%",
        "filename": str(Path.cwd() / "a/b.py"),
        "location": {"row": 3, "column": 5},
        "end_location": {"row": 3, "column": 9},
    }
    (line,) = module.annotations([item], Path.cwd())
    assert line == (
        "::error title=Ruff (F401),file=a/b.py,line=3,col=5,endLine=3,endColumn=9::unused%0Aimport 100%25"
    )


def test_unreadable_report_prints_nothing_and_succeeds(tmp_path: Path) -> None:
    assert module.main([str(tmp_path / "missing.json")]) == 0
    assert module.annotations([]) == []


def test_malformed_diagnostics_and_non_list_json_do_not_crash(tmp_path: Path) -> None:
    lines = module.annotations(
        [
            {"code": None, "message": "x", "filename": "f.py", "location": None, "end_location": 1},
            "not-a-dict",  # type: ignore[list-item]
        ]
    )
    assert lines == ["::error title=Ruff (ruff),file=f.py,line=1,col=1,endLine=1,endColumn=1::x"]
    non_list = tmp_path / "obj.json"
    non_list.write_text('{"error": true}', encoding="utf-8")
    assert module.main([str(non_list)]) == 0
    assert module.main([]) == 2
