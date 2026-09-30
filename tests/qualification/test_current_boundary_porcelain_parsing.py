"""Porcelain status must be parsed without losing the status column.

`git status --porcelain` encodes each line as a two-character status column plus a
space, so an unstaged modification begins with a space. Stripping the whole
command output removed that space from the first line, which shifted every
subsequent column slice and turned

    qualification/final-current-boundary-20260927/ACTUAL_CARD_FORGE.json

into

    ualification/final-current-boundary-20260927/ACTUAL_CARD_FORGE.json

The run-output exclusion then failed to match, a generated artifact was reported
as uncommitted source, and the qualification pipeline could not complete. This is
caught here by parsing real porcelain lines.
"""

from __future__ import annotations

import pytest

from commander_lab.qualification.current_boundary import receipts as R

UNSTAGED = " M qualification/current-boundary-epochs/test-epoch/ACTUAL_CARD_FORGE.json"
STAGED = "M  qualification/current-boundary-epochs/test-epoch/AF01_FORGE.json"
UNTRACKED = "?? qualification/current-boundary-epochs/test-epoch/receipts/x.json"
RENAME = "R  old/path.json -> qualification/current-boundary-epochs/test-epoch/new.json"
CODE = " M src/commander_lab/qualification/current_boundary/receipts.py"


def _paths(lines: list[str]) -> list[str]:
    return [line[3:] for line in lines if not R._is_run_output(line[3:])]


def test_unstaged_run_output_is_not_dirty() -> None:
    assert _paths([UNSTAGED]) == []


def test_staged_run_output_is_not_dirty() -> None:
    assert _paths([STAGED]) == []


def test_untracked_run_output_is_not_dirty() -> None:
    assert _paths([UNTRACKED]) == []


def test_code_change_is_still_dirty() -> None:
    """The property the gate exists for."""
    assert _paths([CODE]) == ["src/commander_lab/qualification/current_boundary/receipts.py"]


def test_stripping_the_output_corrupts_the_first_path() -> None:
    """The exact defect: the first line loses its leading space."""
    raw = "\n".join([UNSTAGED, CODE])
    assert raw.strip().splitlines()[0][3:].startswith("ualification/")
    assert raw.rstrip("\n").splitlines()[0][3:].startswith("qualification/")


def test_git_helper_does_not_strip_leading_whitespace() -> None:
    import inspect

    source = inspect.getsource(R._git)
    assert 'rstrip("\\n")' in source
    assert "return proc.stdout.strip()" not in source


def test_porcelain_reader_splits_lines_without_stripping_them() -> None:
    """`splitlines()` keeps each line's leading space; `.strip()` on the whole
    output would not, and that is the defect."""
    import inspect

    source = inspect.getsource(R._git_porcelain)
    assert "proc.stdout.splitlines()" in source
    assert "proc.stdout.strip()" not in source
    # The filter may inspect each line, but must never rewrite it.
    assert "line.strip() for line in" not in source


def test_run_output_exclusion_is_recorded_not_silent() -> None:
    import inspect

    source = inspect.getsource(R.capture_runner_identity)
    assert "_is_run_output" in source
    assert R._RUN_OUTPUT_PREFIXES
    assert all(prefix.startswith("qualification/") for prefix in R._RUN_OUTPUT_PREFIXES)


@pytest.mark.parametrize(
    "path",
    [
        "qualification/current-boundary-epochs/c0ffee-t0ffee/FULL107_XMAGE_RESULTS.json",
        "qualification/current-boundary-epochs/c0ffee-t0ffee/receipts/native.json",
    ],
)
def test_output_paths_are_recognised(path: str) -> None:
    assert R._is_run_output(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "src/commander_lab/qualification/current_boundary/receipts.py",
        "scripts/run_current_boundary_qualification.py",
        "config/rules_engines.json",
        "engine-bridge/src/main/java/org/commanderlab/xmage/JsonlBridge.java",
        "qualification/other-tree/artifact.json",
    ],
)
def test_source_paths_are_never_excluded(path: str) -> None:
    assert R._is_run_output(path) is False


def test_historical_evidence_is_not_run_output() -> None:
    """The historical WSR22 epoch is a read-only predecessor.

    New runs write a runtime epoch instead, so a modification under the
    historical tree must surface as dirty source rather than being silently
    excluded as "run output".
    """
    assert (
        R._is_run_output("qualification/final-current-boundary-20260927/FULL107_XMAGE_RESULTS.json")
        is False
    )
    assert (
        R._is_run_output("qualification/final-current-boundary-20260927/receipts/x.json") is False
    )
