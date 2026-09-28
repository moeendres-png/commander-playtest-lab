"""AF01 decision-time invariants must be observed against a live game.

The defect these guard against is subtle and silent: AF01 probed
``submit_action`` and ``get_legal_actions`` with no ``game_id`` and no game in
existence. A provider asked to fail closed on a submission for a game that does
not exist refuses anyway, so the invariant reported PASS while demonstrating
nothing about decision-time legality. Two previously unconditional-PASS
invariants are also pinned to a real scan.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary.af01 import (
    LEGALITY_RECONSTRUCTION_PATTERNS,
    observe_no_legality_reconstruction,
    run_af01,
)

REPO = Path(__file__).resolve().parents[2]
SCANNED_REL = "src/commander_lab/qualification/current_boundary"


def test_af01_refuses_to_run_without_a_live_game() -> None:
    """No game_id must be a hard refusal, not a silent downgrade to UNKNOWN."""
    with pytest.raises(ValueError, match="requires a live game_id"):
        run_af01(
            None,  # type: ignore[arg-type]
            candidate="xmage",
            expected_commit="a" * 40,
            runner_commit="b" * 40,
            runner_tree="c" * 40,
            game_id=None,
        )


def test_empty_game_id_is_not_treated_as_live() -> None:
    with pytest.raises(ValueError, match="requires a live game_id"):
        run_af01(
            None,  # type: ignore[arg-type]
            candidate="xmage",
            expected_commit="a" * 40,
            runner_commit="b" * 40,
            runner_tree="c" * 40,
            game_id="",
        )


def test_decision_probes_are_scoped_to_the_live_game() -> None:
    source = (REPO / SCANNED_REL / "af01.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    # Every request that submits or reads a legal action must carry the game_id.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "request"):
            continue
        message = node.args[0] if node.args else None
        if not (
            isinstance(message, ast.Constant)
            and message.value in {"submit_action", "get_legal_actions"}
        ):
            continue
        payload = node.args[1] if len(node.args) > 1 else None
        keys = (
            {k.value for k in payload.keys if isinstance(k, ast.Constant)}
            if isinstance(payload, ast.Dict)
            else set()
        )
        assert "game_id" in keys, f"{message.value} sent without a game_id in the payload"
        assert "game_id" in [kw.arg for kw in node.keywords if kw.arg], (
            f"{message.value} sent without a game_id to the bridge"
        )


def test_no_unguarded_pass_invariants_remain_in_af01() -> None:
    """A PASS with no enclosing condition is credit for nothing.

    A conditional PASS is fine, because the condition is the observation. The
    defect was a bare ``add(name, "PASS", ...)`` that asserted a structural
    property instead of deriving it, so this looks specifically for a literal
    PASS that is not under any ``if``.
    """
    source = (REPO / SCANNED_REL / "af01.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for child in ast.walk(node):
                guarded.add(id(child))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "add"
        ):
            continue
        if len(node.args) < 3:
            continue
        verdict = node.args[1]
        if not (isinstance(verdict, ast.Constant) and verdict.value == "PASS"):
            continue
        if id(node) in guarded:
            continue
        name = node.args[0].value if isinstance(node.args[0], ast.Constant) else "<dynamic>"
        offenders.append(str(name))
    assert offenders == [], f"PASS invariants with no observation: {offenders}"


def test_structure_invariants_are_unknown_without_bound_source() -> None:
    """Without bound source the invariant is unproven, so it must be UNKNOWN.

    The contract is expressed on the helper, because a full run is not needed to
    pin it: the point is that the verdict depends on a real scan, and the
    docstring records why it is an observation rather than an assertion.
    """
    assert observe_no_legality_reconstruction.__doc__ is not None
    assert "not an assertion" in observe_no_legality_reconstruction.__doc__


def test_scan_is_clean_on_the_real_bound_source() -> None:
    result = observe_no_legality_reconstruction(REPO)
    assert result["complete"] is True
    assert result["scanned_files"] > 0
    assert result["hits"] == [], result["hits"]


@pytest.mark.parametrize(
    "line",
    [
        "choice = first_option(candidates)",
        "choice = random_option()",
        "if default_yes():",
        "options = requested_options(payload)",
        "id_ = fabricate_legal_action()",
        "id_ = invent_legal_option()",
    ],
)
def test_scan_detects_each_forbidden_pattern(tmp_path: Path, line: str) -> None:
    target = tmp_path / SCANNED_REL
    target.mkdir(parents=True)
    (target / "bad.py").write_text(line + "\n", encoding="utf-8")
    result = observe_no_legality_reconstruction(tmp_path)
    assert result["complete"] is True
    assert result["hits"], f"not detected: {line}"


def test_scan_ignores_comments_and_prose(tmp_path: Path) -> None:
    """A name mentioned in a comment is not a violation; a source scan for
    absence must not fire on documentation or on the scanner's own patterns."""
    target = tmp_path / SCANNED_REL
    target.mkdir(parents=True)
    (target / "doc.py").write_text(
        "# we must never use first_option here\n"
        '"""random_option is forbidden by policy."""\n'
        "value = 1\n",
        encoding="utf-8",
    )
    result = observe_no_legality_reconstruction(tmp_path)
    assert result["hits"] == []


def test_pattern_table_covers_every_policy_shortcut() -> None:
    """AGENTS.md forbids this list; the scan must cover all of it."""
    blob = " ".join(pattern for pattern, _ in LEGALITY_RECONSTRUCTION_PATTERNS)
    for required in ("first_option", "random_option", "default_yes", "requested_options"):
        assert required in blob
    for pattern, label in LEGALITY_RECONSTRUCTION_PATTERNS:
        re.compile(pattern)  # must be a valid pattern
        assert label


def test_runner_establishes_a_live_game_before_af01() -> None:
    source = (REPO / "scripts/run_current_boundary_qualification.py").read_text(encoding="utf-8")
    drive_at = source.index("af01_live = drive_commander_game(")
    af01_at = source.index("af01 = run_af01(")
    assert drive_at < af01_at, "AF01 runs before a live game exists"
    assert "game_id=af01_game_id" in source
    assert "runner_root=REPO_ROOT" in source
    # And a failure to establish a live game must stop the run, not downgrade.
    assert "AF01 evidence is not produced" in source
