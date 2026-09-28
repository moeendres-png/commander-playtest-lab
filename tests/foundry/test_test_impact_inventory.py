"""Real Git regressions for complete advisory impact inputs, not qualification."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from foundry import test_impact as impact


def git(repo, *args):
    return (
        subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)
        .stdout.decode()
        .strip()
    )


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    (tmp_path / "seed").write_text("seed")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "base")
    return tmp_path


def test_exact_paths_and_recursive_untracked(repo):
    paths = ["docs/two words.md", "tools/a -> b.py", "src/über.py"]
    for path in paths:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("before")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "paths")
    base = git(repo, "rev-parse", "HEAD")
    for path in paths:
        (repo / path).write_text("after")
    (repo / "new/deep").mkdir(parents=True)
    (repo / "new/deep/card.py").write_text("new")
    assert impact.changed_files(str(repo), base) == sorted([*paths, "new/deep/card.py"])


def test_rename_keeps_removed_production_surface(repo):
    (repo / "src").mkdir()
    (repo / "docs").mkdir()
    (repo / "src/engine.py").write_text("same content\n" * 20)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "source")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "mv", "src/engine.py", "docs/moved.md")
    git(repo, "commit", "-m", "rename")
    changed = impact.changed_files(str(repo), base)
    assert changed == ["docs/moved.md", "src/engine.py"]
    assert impact.plan(changed)["requalification_required"] is True


def test_failed_secondary_query_cannot_return_partial_inventory(repo, monkeypatch):
    real = subprocess.run

    def fail(args, **kwargs):
        if "status" in args or "ls-files" in args:
            return subprocess.CompletedProcess(args, 128, b"" if not kwargs.get("text") else "", "")
        return real(args, **kwargs)

    monkeypatch.setattr(impact.subprocess, "run", fail)
    with pytest.raises(ValueError):
        impact.changed_files(str(repo), "HEAD")


def test_staged_and_worktree_cancellation_still_requires_tests(repo):
    (repo / "seed").write_text("staged")
    git(repo, "add", "seed")
    (repo / "seed").write_text("seed")
    assert impact.changed_files(str(repo), "HEAD") == ["seed"]


def test_clean_control(repo):
    assert impact.changed_files(str(repo), "HEAD") == []


def test_subdirectory_cannot_hide_sibling_changes(repo):
    (repo / "docs").mkdir()
    (repo / "src").mkdir()
    (repo / "src/new.py").write_text("new")
    with pytest.raises(ValueError, match="root"):
        impact.changed_files(str(repo / "docs"), "HEAD")


def test_non_utf8_and_control_char_paths_are_lossless(repo):
    if os.name == "nt":
        pytest.skip("POSIX raw/control pathname fixture")
    names = [b"tab\tand\nnewline.py", b"invalid-\xff.py", b' quote".py ']
    for name in names:
        with open(os.fsencode(repo) + b"/" + name, "wb") as stream:
            stream.write(b"data")
    changed = impact.changed_files(str(repo), "HEAD")
    assert {path.encode("utf-8", "surrogateescape") for path in changed} == set(names)
    assert json.loads(json.dumps(impact.plan(changed)))["changed"] == changed


@pytest.mark.parametrize("base", ["missing", "--all", "seed"])
def test_bad_base_is_not_an_option_or_path(repo, base):
    with pytest.raises(ValueError, match="cannot diff"):
        impact.changed_files(str(repo), base)


@pytest.mark.parametrize("payload", [b"a.py", b"\0", b"a\0\0", b"../x\0", b"/x\0", b"nested/\0"])
def test_malformed_inventory_is_not_usable(payload):
    with pytest.raises(ValueError):
        impact._paths(payload)


@pytest.mark.parametrize("operation", ["rev-parse", "diff", "ls-files"])
def test_nonzero_plausible_stdout_is_failure(repo, monkeypatch, operation):
    real = subprocess.run

    def fail(args, **kwargs):
        if operation in args:
            return subprocess.CompletedProcess(args, 1, b"src/engine.py\0", b"secret sentinel")
        return real(args, **kwargs)

    monkeypatch.setattr(impact.subprocess, "run", fail)
    with pytest.raises(ValueError) as error:
        impact.changed_files(str(repo), "HEAD")
    assert "secret sentinel" not in str(error.value)


@pytest.mark.parametrize(
    "error",
    [
        OSError("private sentinel"),
        subprocess.TimeoutExpired("git", 15),
        UnicodeDecodeError("utf8", b"\xff", 0, 1, "invalid"),
    ],
)
def test_cli_structured_failure_preserves_existing_report(repo, monkeypatch, capsys, error):
    def fail(*args, **kwargs):
        assert kwargs["timeout"] == 15
        raise error

    monkeypatch.setattr(impact.subprocess, "run", fail)
    output = repo / "report.json"
    output.write_text("previous report")
    assert impact.main(["--workdir", str(repo), "--base", "HEAD", "--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "TEST_IMPACT_ERROR:" in captured.err
    assert "private sentinel" not in captured.err
    assert output.read_text() == "previous report"


def test_head_changes_during_collection(repo, monkeypatch):
    real = impact._git
    calls = 0

    def moving_head(args, cwd):
        nonlocal calls
        raw = real(args, cwd)
        if args[-1] == "HEAD^{commit}":
            calls += 1
            if calls == 3:  # base=HEAD, initial HEAD, final HEAD
                return b"a" * 40 + b"\n"
        return raw

    monkeypatch.setattr(impact, "_git", moving_head)
    with pytest.raises(ValueError, match="HEAD changed"):
        impact.changed_files(str(repo), "HEAD")


def test_ignored_files_excluded_and_cli_identifies_base(repo, capsys):
    (repo / ".gitignore").write_text("ignored/\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "ignore")
    (repo / "ignored").mkdir()
    (repo / "ignored/private").write_text("ignored")
    assert impact.main(["--workdir", str(repo), "--base", "HEAD"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["changed"] == []
    assert result["head"] == result["resolved_base"] == git(repo, "rev-parse", "HEAD")
    assert result["contract_override"] == impact.CONTRACT_OVERRIDE


def test_untracked_nested_repo_fails_closed(repo):
    nested = repo / "nested"
    nested.mkdir()
    git(nested, "init")
    (nested / "a.py").write_text("nested")
    with pytest.raises(ValueError, match="nested repository"):
        impact.changed_files(str(repo), "HEAD")
