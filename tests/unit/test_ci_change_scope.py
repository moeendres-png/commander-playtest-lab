"""The CI change classifier (scripts/ci_change_scope.py): docs-only fast path and packaging gate."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "ci_change_scope", ROOT / "scripts" / "ci_change_scope.py"
)
assert _spec is not None and _spec.loader is not None
scope = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scope)

ENTRYPOINTS = {"src/commander_lab/cli/main.py", "src/commander_lab/cli/main/__init__.py"}


def decide(*changes: tuple[str, str], event: str = "pull_request") -> dict[str, str]:
    return scope.decide(event, list(changes), ENTRYPOINTS)


def test_docs_only_runs_the_docs_subset_without_packaging() -> None:
    out = decide(("M", "docs/a.md"), ("A", "README.md"), ("M", "docs/data.json"))
    assert out["scope"] == "docs" and out["packaging"] == "false"
    assert json.loads(out["test_matrix"]) == {
        "include": [{"index": 1, "count": 1, "scope": "docs"}]
    }


def test_docs_plus_one_code_file_runs_everything() -> None:
    out = decide(("M", "docs/a.md"), ("M", "src/commander_lab/x.py"))
    assert out["scope"] == "full"
    include = json.loads(out["test_matrix"])["include"]
    assert [item["index"] for item in include] == list(range(1, scope.MATRIX_COUNT + 1))
    assert {item["scope"] for item in include} == {"all"}


@pytest.mark.parametrize(
    "path",
    [
        ".github/pull_request_template.md",
        "src/commander_lab/README.md",
        "tests/notes.md",
        "data/decks/x.md",
        "config/x.md",
        "qualification/x.md",
        "scripts/x.md",
        "pyproject.toml",
        "docs/tool.py",
        "docs/run.sh",
        "docs/run.ps1",
        "docs/run.bat",
    ],
)
def test_markdown_under_code_roots_and_other_files_are_not_docs(path: str) -> None:
    assert decide(("M", path))["scope"] == "full"


def test_renamed_file_out_of_or_into_docs_is_not_docs_only() -> None:
    # --no-renames reports a rename as delete + add, so the code side is always visible.
    assert decide(("D", "src/commander_lab/e.py"), ("A", "docs/e.md"))["scope"] == "full"
    assert decide(("D", "docs/e.md"), ("A", "src/commander_lab/e.py"))["scope"] == "full"


def test_deleted_code_file_is_not_docs_and_deleted_doc_is() -> None:
    assert decide(("D", "src/commander_lab/e.py"))["scope"] == "full"
    assert decide(("D", "docs/old.md"))["scope"] == "docs"


def test_empty_or_unreadable_diff_runs_everything() -> None:
    assert scope.decide("pull_request", [], ENTRYPOINTS)["scope"] == "full"
    unreadable = scope.decide("pull_request", None, ENTRYPOINTS)
    assert unreadable["scope"] == "full" and unreadable["packaging"] == "true"


@pytest.mark.parametrize("event", ["push", "workflow_dispatch", "schedule"])
def test_other_events_always_run_everything(event: str) -> None:
    out = decide(("M", "docs/a.md"), event=event)
    assert out["scope"] == "full" and out["packaging"] == "true"


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (("M", "pyproject.toml"), "true"),
        (("M", "requirements/lock.txt"), "true"),
        (("M", "scripts/verify_packaging_smoke.py"), "true"),
        (("M", "tests/unit/test_packaging_smoke.py"), "true"),
        (("M", ".github/workflows/ci.yml"), "true"),
        (("M", "src/commander_lab/studio/__init__.py"), "true"),
        (("M", "src/commander_lab/cli/main.py"), "true"),
        (("A", "src/commander_lab/new_module.py"), "true"),
        (("D", "src/commander_lab/old_module.py"), "true"),
        (("M", "src/commander_lab/ordinary.py"), "true"),
        (("T", "src/commander_lab/ordinary.py"), "true"),
        (("M", "src/commander_lab/studio/static/app.js"), "true"),
        (("M", "tests/unit/test_other.py"), "false"),
    ],
)
def test_packaging_inputs(change: tuple[str, str], expected: str) -> None:
    assert decide(change)["packaging"] == expected


def test_console_script_modules_come_from_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project.scripts]\na = "pkg.cli.app:main"\n', encoding="utf-8"
    )
    assert scope.console_script_modules(tmp_path / "pyproject.toml") == {
        "src/pkg/cli/app.py",
        "src/pkg/cli/app/__init__.py",
    }
    assert "src/commander_lab/cli/main.py" in scope.console_script_modules(ROOT / "pyproject.toml")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_real_git_diff_with_rename_and_delete(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "e.py").write_text("x = 1\n" * 20)
    (tmp_path / "docs" / "d.md").write_text("doc\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "mv", "src/e.py", "docs/e.md")
    _git(tmp_path, "rm", "-q", "docs/d.md")
    _git(tmp_path, "commit", "-qm", "head")
    changes = scope.changed_files(tmp_path, base, "HEAD")
    assert sorted(changes) == [("A", "docs/e.md"), ("D", "docs/d.md"), ("D", "src/e.py")]
    assert scope.decide("pull_request", changes)["scope"] == "full"


def test_cli_writes_github_output_and_fails_closed(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    assert (
        scope.main(
            ["--event", "pull_request", "--repo", str(tmp_path), "--github-output", str(out)]
        )
        == 0
    )
    text = out.read_text()
    assert "scope=full" in text and "packaging=true" in text and "test_matrix=" in text
    assert (
        scope.main(["--event", "push", "--repo", str(tmp_path), "--github-output", str(out)]) == 0
    )


def test_cli_with_corrupt_pyproject_fails_closed_even_on_docs_diff(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("one\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'ok'\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "docs" / "a.md").write_text("two\n")
    _git(tmp_path, "add", "docs/a.md")
    _git(tmp_path, "commit", "-qm", "docs head")
    (tmp_path / "pyproject.toml").write_text("not valid toml = [\n")
    out = tmp_path / "out.txt"
    assert (
        scope.main(
            [
                "--event",
                "pull_request",
                "--base",
                base,
                "--repo",
                str(tmp_path),
                "--github-output",
                str(out),
            ]
        )
        == 0
    )
    text = out.read_text()
    assert "scope=full" in text and "packaging=true" in text


def test_parse_name_status_rejects_unpaired_output() -> None:
    with pytest.raises(ValueError):
        scope.parse_name_status(b"M\0")
