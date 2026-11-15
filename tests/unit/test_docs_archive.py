"""docs/archive/ holds only unreferenced historical docs; see scripts/classify_docs.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_classify_docs_check_passes() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/classify_docs.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_archive_readme_declares_provenance_only() -> None:
    text = (ROOT / "docs/archive/README.md").read_text(encoding="utf-8")
    assert "provenance only" in text
    assert "not current instruction" in text


def _load_classifier() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "classify_docs", ROOT / "scripts/classify_docs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, docs: dict[str, str], others: dict[str, str]
) -> Any:
    module = _load_classifier()
    files = []
    for rel, text in {**docs, **others}.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        files.append(rel)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module.classify(files)


def test_topic_entry_without_anchor_is_archived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch, {"docs/mulligan_lab/README.md": "x"}, {"src/a.py": "pass"})
    assert plan["archive"] == {"mulligan_lab": "mulligan-lab"}


def test_entry_without_topic_is_current(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(tmp_path, monkeypatch, {"docs/installation.md": "x"}, {})
    assert plan["archive"] == {} and "installation.md" in plan["current"]


def test_code_reference_anchors_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(
        tmp_path,
        monkeypatch,
        {"docs/known_limitations.md": "x"},
        {"tests/test_a.py": 'p = "docs/known_limitations.md"'},
    )
    assert "known_limitations.md" in plan["kept_anchored"] and not plan["archive"]


def test_pathlib_style_reference_anchors_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(
        tmp_path,
        monkeypatch,
        {"docs/meta/R.md": "x"},
        {"tests/test_a.py": 'p = ROOT / "docs" / "meta"'},
    )
    assert "meta" in plan["kept_anchored"]


def test_prose_in_sealed_tree_is_no_anchor_but_machine_record_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = {"docs/known_limitations.md": "x", "docs/validation_levels.md": "x"}
    others = {
        "qualification/e/VALIDATION.md": "see docs/known_limitations.md",
        "qualification/e/LOCK.json": '{"p": "docs/validation_levels.md"}',
    }
    plan = _plan(tmp_path, monkeypatch, docs, others)
    assert "known_limitations.md" in plan["archive"]
    assert "validation_levels.md" in plan["kept_anchored"]


def test_entry_document_link_anchors_but_archive_pointer_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = {"docs/known_limitations.md": "x", "docs/validation_levels.md": "x"}
    others = {
        "README.md": "[a](docs/known_limitations.md) docs/archive/superseded/validation_levels.md"
    }
    plan = _plan(tmp_path, monkeypatch, docs, others)
    assert "known_limitations.md" in plan["kept_anchored"]
    assert "validation_levels.md" in plan["archive"]


def test_owner_decision_documents_are_never_archived() -> None:
    module = _load_classifier()
    assert module.PROTECTED_ENTRY.search("owner_decision_20261013_forge_removal")
    assert not any(
        module.PROTECTED_ENTRY.search(n) for _t, (_d, names) in module.TOPICS.items() for n in names
    )


def test_archive_topics_have_readme() -> None:
    module = _load_classifier()
    for topic in module.TOPICS:
        readme = ROOT / "docs/archive" / topic / "README.md"
        assert readme.is_file(), topic
        assert "Last commit at which the described code existed" in readme.read_text(
            encoding="utf-8"
        )
