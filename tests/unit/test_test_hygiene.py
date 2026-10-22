"""No test can pass without testing anything (#961 Q-1).

``scripts/test_hygiene_scan.py`` counts three kinds of test statically. The repository has none
of them, and this file keeps it that way. The scanner itself is tested on small sources,
including the cases it must flag and the ones it must leave alone.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "test_hygiene_scan_under_test", ROOT / "scripts" / "test_hygiene_scan.py"
)
assert spec and spec.loader
scan = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scan  # dataclasses look their module up here
spec.loader.exec_module(scan)


def _groups(source: str) -> dict[str, str]:
    return {name: group for group, name in scan.scan_source(textwrap.dedent(source))}


def test_the_repository_has_no_test_that_passes_without_testing() -> None:
    found = scan.scan()
    assert found.tests > 4000, "the scan found the test suite"
    flagged = {name: tests for name, tests in found.groups.items() if tests}
    assert flagged == {}, (
        "These tests can pass while checking nothing. Assert on what the code returned "
        "(`assert f(x) is None` for a validator), assert something stronger than "
        "`is not None`/`exists()`/`isinstance`, and assert that a collection is not empty "
        f"before a loop walks it: {flagged}"
    )


def test_a_test_without_any_assertion_is_flagged() -> None:
    found = _groups(
        """
        def test_runs():
            compute()
        """
    )
    assert found == {"test_runs": "no_assertion"}


def test_raises_and_assertion_helpers_count_as_assertions() -> None:
    found = _groups(
        """
        import pytest

        def test_rejects():
            with pytest.raises(ValueError):
                compute()

        def test_helper():
            assert_valid(compute())

        def test_check_helper():
            check_everything(compute())
        """
    )
    assert found == {}


def test_a_test_whose_assertions_are_all_trivial_is_flagged() -> None:
    found = _groups(
        """
        def test_not_none():
            assert compute() is not None

        def test_exists(tmp_path):
            assert (tmp_path / "a").exists()

        def test_truthy():
            value = compute()
            assert value

        def test_type():
            assert isinstance(compute(), dict)

        def test_one_real_check_among_trivial_ones():
            value = compute()
            assert value is not None
            assert value == 3
        """
    )
    assert found == {
        "test_not_none": "trivial_only",
        "test_exists": "trivial_only",
        "test_truthy": "trivial_only",
        "test_type": "trivial_only",
    }


def test_a_loop_over_a_collection_that_may_be_empty_is_flagged() -> None:
    found = _groups(
        """
        def test_glob(tmp_path):
            for path in tmp_path.glob("*.json"):
                assert path.stat().st_size > 0

        def test_parsed(data):
            for key, value in data.items():
                assert value == 1, key

        def test_nested_dynamic_in_a_static_loop(data):
            for name in ("a", "b"):
                for row in data[name]:
                    assert row == 1
        """
    )
    assert found == {
        "test_glob": "unguarded_loop",
        "test_parsed": "unguarded_loop",
        "test_nested_dynamic_in_a_static_loop": "unguarded_loop",
    }


def test_a_loop_that_is_guarded_or_runs_over_a_literal_is_not_flagged() -> None:
    found = _groups(
        """
        NAMES = ("a", "b")

        def test_guarded(tmp_path):
            files = list(tmp_path.glob("*.json"))
            assert files, "nothing to check"
            for path in files:
                assert path.stat().st_size > 0

        def test_literal():
            for name in ("a", "b"):
                assert name != ""

        def test_module_constant():
            for name in NAMES:
                assert len(name) == 1

        def test_range():
            for n in range(3):
                assert n < 3

        def test_guard_inside_the_outer_loop(data):
            for name in ("a", "b"):
                rows = data[name]
                assert len(rows) >= 1, name
                for row in rows:
                    assert row == 1

        def test_assertion_outside_the_loop_too(tmp_path):
            assert tmp_path.is_dir() is True
            for path in tmp_path.glob("*.json"):
                assert path.stat().st_size > 0
        """
    )
    assert found == {}


def test_an_assertion_after_the_loop_fails_on_an_empty_collection_too() -> None:
    found = _groups(
        """
        def test_late_guard(data):
            for row in data:
                assert row == 1
            assert data
        """
    )
    assert found == {}, "the test has an assertion outside the loop that an empty input fails"
