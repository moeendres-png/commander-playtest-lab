"""AF02 must be all-or-nothing over a real Commander lifecycle.

The defect: ``card_pass`` counted any run whose ``steps_completed`` list was
non-empty and which reported no failure. ``steps_completed`` grows as the driver
proceeds, so a run that imported decks and created a game but never started it,
never reached a decision, and never bound an external choice counted as a
completed lifecycle at that player count -- and four such prefixes earned AF02
PASS. A shortfall was also reported as FAIL, when an unestablished count is an
evidence gap rather than a refutation.
"""

from __future__ import annotations

import ast
from pathlib import Path

from commander_lab.qualification.current_boundary.lifecycle import (
    REQUIRED_LIFECYCLE_STEPS,
    cardinality_verdict,
    lifecycle_completeness,
)

REPO = Path(__file__).resolve().parents[2]
ASSEMBLER = REPO / "scripts/assemble_current_boundary_evidence.py"
FULL107 = REPO / "src/commander_lab/qualification/current_boundary/full107.py"

COMPLETE_STEPS = list(REQUIRED_LIFECYCLE_STEPS)


def _complete() -> dict:
    return {
        "steps_completed": list(COMPLETE_STEPS),
        "failure": None,
        "terminal_facts": {"priority_reached": True},
        "decision_tape": [{"chosen_option_id": "opt-1"}],
    }


def _af01(commit: str) -> dict:
    return {"engine_commit_reported": commit, "engine_commit_provenance": "test"}


def test_a_full_lifecycle_is_complete() -> None:
    assert lifecycle_completeness(_complete())["complete"] is True


def test_import_only_is_not_a_lifecycle() -> None:
    """The exact defect: a deck import is not a game."""
    result = lifecycle_completeness(
        {
            "steps_completed": ["handshake", "import_deck", "create_commander_game"],
            "failure": None,
            "terminal_facts": {},
            "decision_tape": [],
        }
    )
    assert result["complete"] is False
    assert "start_game" in result["missing_steps"]
    assert "decision_drive" in result["missing_steps"]


def test_created_but_not_started_is_not_a_lifecycle() -> None:
    result = lifecycle_completeness(
        {
            "steps_completed": ["handshake", "import_deck", "create_commander_game"],
            "failure": None,
            "terminal_facts": {"priority_reached": False},
            "decision_tape": [{"chosen_option_id": "opt-1"}],
        }
    )
    assert result["complete"] is False


def test_no_steps_is_incomplete() -> None:
    result = lifecycle_completeness({"steps_completed": [], "failure": None})
    assert result["complete"] is False
    assert "recorded no completed steps" in " ".join(result["reasons"])


def test_a_run_with_a_failure_is_incomplete() -> None:
    payload = _complete()
    payload["failure"] = "BridgeTimeout: deadline exceeded"
    assert lifecycle_completeness(payload)["complete"] is False


def test_out_of_order_steps_are_incomplete() -> None:
    payload = _complete()
    payload["steps_completed"] = [
        "import_deck",
        "handshake",
        "create_commander_game",
        "start_game",
        "decision_drive",
    ]
    result = lifecycle_completeness(payload)
    assert result["complete"] is False
    assert any("out of order" in reason for reason in result["reasons"])


def test_no_external_decision_is_incomplete() -> None:
    payload = _complete()
    payload["decision_tape"] = [{"chosen_option_id": None}]
    assert lifecycle_completeness(payload)["complete"] is False


def test_af02_passes_only_when_every_required_count_is_complete() -> None:
    results = {f"{n}P": _complete() for n in (2, 3, 4, 5)}
    verdict = cardinality_verdict(results)
    assert verdict["verdict"] == "PASS"
    assert verdict["complete_counts"] == [2, 3, 4, 5]
    assert verdict["incomplete_counts"] == []


def test_four_complete_counts_and_one_broken_is_unknown_not_pass() -> None:
    results = {f"{n}P": _complete() for n in (2, 3, 4, 5)}
    results["5P"] = {"steps_completed": ["handshake", "import_deck"], "failure": None}
    verdict = cardinality_verdict(results)
    assert verdict["verdict"] == "UNKNOWN", "a shortfall is an evidence gap, not a failure"
    assert verdict["incomplete_counts"] == [5]
    assert verdict["complete_counts"] == [2, 3, 4]


def test_four_import_only_prefixes_no_longer_earn_pass() -> None:
    """The historical defect, reproduced exactly."""
    results = {
        f"{n}P": {
            "steps_completed": ["handshake", "import_deck", "create_commander_game"],
            "failure": None,
            "terminal_facts": {},
            "decision_tape": [],
        }
        for n in (2, 3, 4, 5)
    }
    verdict = cardinality_verdict(results)
    assert verdict["verdict"] != "PASS"
    assert verdict["complete_counts"] == []


def test_a_missing_count_is_unknown() -> None:
    results = {f"{n}P": _complete() for n in (2, 3, 4)}
    verdict = cardinality_verdict(results)
    assert verdict["verdict"] == "UNKNOWN"
    assert verdict["incomplete_counts"] == [5]
    assert verdict["detail"]["5P"]["present"] is False


# --- AF00, which was a literal PASS that never compared the reported commit --- #


def test_af00_passes_when_the_provider_named_the_expected_commit() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("asm", ASSEMBLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.source_lock_verdict(_af01("a" * 40), "a" * 40) == "PASS"


def test_af00_fails_when_the_provider_named_another_commit() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("asm", ASSEMBLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.source_lock_verdict(_af01("b" * 40), "a" * 40) == "FAIL"


def test_af00_is_unknown_when_the_provider_named_nothing() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("asm", ASSEMBLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.source_lock_verdict(_af01(""), "a" * 40) == "UNKNOWN"
    assert module.source_lock_verdict(_af01("a" * 40), "") == "UNKNOWN"


def test_row_verdict_uses_the_all_or_nothing_rule() -> None:
    source = FULL107.read_text(encoding="utf-8")
    assert "lifecycle_completeness" in source
    block = source[source.index("assessment = lifecycle.lifecycle_completeness(") :]
    assert '"UNKNOWN"' in block[:600]
    assert "lifecycle_completeness" in block


def test_assembler_has_no_prefix_credit_expression() -> None:
    source = ASSEMBLER.read_text(encoding="utf-8")
    assert "card_pass" not in source
    assert "cardinality_verdict" in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            values = list(node.values)
            for index, key in enumerate(keys):
                if key in {"AF00", "AF02"}:
                    following = values[index + 1]
                    assert not (
                        isinstance(following, ast.Constant) and following.value in {"PASS", "FAIL"}
                    ), f"{key} verdict must not be a literal"
