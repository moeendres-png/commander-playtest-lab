"""Static ratchet against new first-option picks (LEDGER D-08, audit item 16).

AGENTS.md section 2 forbids answering a production-reachable decision with
whatever option an engine happens to list first. The behavioural proof for the
production validation seam lives in
``commander_lab.qualification.current_boundary.shortcut_campaign``; a static
scan cannot tell a forbidden pick from the same subscript reached after an
exact-uniqueness check. This gate therefore does not judge the existing
occurrences. It only stops new ones from arriving unreviewed:

* no file may gain an occurrence;
* a file not listed may have none;
* a count that drops must be lowered here, so it cannot silently grow back.

A new occurrence needs an explicit choice (label, id or predicate) or a
reviewed baseline entry stating why the pick is sound.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCANNED_ROOTS = (
    "engine-bridge/src/main/java",
    "engine-bridge/src/test/java",
    "src/commander_lab",
    "scripts",
)

FIRST_OPTION = re.compile(
    r"\b\w*(?:[aA]ctions|[oO]ptions|[cC]andidates|[cC]hoices|[tT]argets|[aA]bilities)"
    r"(?:\.get\(0\)|\[0\])"
)

# Occurrences present on main at 2026-09-30; entries may only go down.
BASELINE: dict[str, int] = {
    "engine-bridge/src/test/java/org/commanderlab/xmage/Ws204DecisionKindCensusTest.java": 3,
    "engine-bridge/src/test/java/org/commanderlab/xmage/Ws92D1D2D3ProjectionTest.java": 1,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageActualCardCorpusTest.java": 4,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameActionProjectionTest.java": 4,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameCombatDamageTest.java": 1,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameConcedeActionTest.java": 1,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameGenericActionSubmissionTest.java": 4,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameHiddenInformationTest.java": 1,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameNameCanaryTest.java": 1,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameReplayTwinTest.java": 4,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageMidgameCausalTest.java": 1,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageMultiplayerLeaverStackTest.java": 1,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmagePb03Tier1RowsTest.java": 2,
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageVariablePlayerLifecycleTest.java": 1,
    "src/commander_lab/engine/action_validation.py": 1,
    "src/commander_lab/engine/rules/full_game.py": 1,
    "src/commander_lab/engine/structural/simulator.py": 3,
    "src/commander_lab/qualification/current_boundary/game_driver.py": 1,
    "src/commander_lab/qualification/current_boundary/shortcut_campaign.py": 1,
    "src/commander_lab/robustness.py": 1,
    "src/commander_lab/semantic_replay/consumer.py": 2,
    "src/commander_lab/tools/service.py": 1,
    "scripts/run_candidate_handoff_conformance.py": 1,
    "scripts/run_external_b4c_regression.py": 2,
    "scripts/run_external_b4d_regression.py": 1,
    "scripts/run_external_b4f_illegal_action_regression.py": 1,
    "scripts/run_midgame_capability_probe.py": 1,
}


def count_first_option_picks(root: Path = ROOT) -> dict[str, int]:
    found: dict[str, int] = {}
    for scanned in SCANNED_ROOTS:
        base = root / scanned
        if not base.is_dir():
            raise AssertionError(f"scanned root missing (gate cannot run): {scanned}")
        for path in sorted(base.rglob("*")):
            if path.suffix not in (".java", ".py") or "__pycache__" in path.parts:
                continue
            count = len(FIRST_OPTION.findall(path.read_text(encoding="utf-8", errors="replace")))
            if count:
                found[path.relative_to(root).as_posix()] = count
    return found


def ratchet_problems(found: dict[str, int], baseline: dict[str, int]) -> list[str]:
    problems = []
    for name, count in sorted(found.items()):
        allowed = baseline.get(name, 0)
        if count > allowed:
            problems.append(
                f"{name}: {count} first-option picks, allowed {allowed} "
                "(choose explicitly by label/id/predicate, or add a reviewed baseline entry)"
            )
        elif count < allowed:
            problems.append(f"{name}: now {count}, lower its BASELINE entry from {allowed}")
    for name in sorted(set(baseline) - set(found)):
        problems.append(f"{name}: no picks left (or file gone), remove its BASELINE entry")
    return problems


def test_no_file_gains_a_first_option_pick() -> None:
    found = count_first_option_picks()
    assert found, "gate saw no occurrences at all; the scan is broken"
    problems = ratchet_problems(found, BASELINE)
    assert not problems, "\n".join(problems)


def test_the_pattern_catches_the_forbidden_shapes() -> None:
    for text in (
        "legal = actions.get(0);",
        "chosen = options[0]",
        "pick(legalActions.get(0))",
        "x = pass_actions[0]['action_id']",
        "c = candidates[0]",
    ):
        assert FIRST_OPTION.search(text), text
    for text in ("actions.get(i)", "options[1]", "labels.get(0)", "row[0]"):
        assert not FIRST_OPTION.search(text), text


def test_the_ratchet_rejects_growth_and_stale_entries() -> None:
    assert ratchet_problems({"a.py": 2}, {"a.py": 1})
    assert ratchet_problems({"new.py": 1}, {})
    assert ratchet_problems({"a.py": 1}, {"a.py": 2})
    assert ratchet_problems({}, {"gone.py": 1})
    assert not ratchet_problems({"a.py": 1}, {"a.py": 1})
