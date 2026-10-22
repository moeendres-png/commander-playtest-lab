"""Real pilot requests: the pilot answers the shapes the bridge really sends (#787, #862).

``tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz`` is a stratified sample of the
requests that real XMage games of the real pod put to the policy
(``scripts/pilot_request_corpus.py record``). No JVM runs here: every request is answered by
a fresh policy and checked for a legal answer. A pilot that reads a renamed or moved field,
or a request shape that no hand-built fixture imagines, fails here.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_request_corpus.py"
spec = importlib.util.spec_from_file_location("pilot_request_corpus_under_test", SCRIPT)
assert spec and spec.loader
corpus_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus_tool)

from commander_lab.engine.rules.full_game_pilot import ExternalPilotDecisionPolicy  # noqa: E402


def _record(decision_class: str, index: int, options: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "seed": 1,
        "request": {
            "decision_class": decision_class,
            "decision_id": f"d{index}",
            "legal_options": options,
        },
        "answer": {},
    }


PASS = {"option_id": "p", "option_type": "pass_priority", "metadata": {}}
SPELL = {
    "option_id": "s",
    "option_type": "activated_ability",
    "metadata": {"ability_type": "spell"},
}
MANA = {"option_id": "m", "option_type": "mana_ability", "metadata": {"ability_type": "mana"}}


def test_bucket_tells_the_windows_of_a_priority_decision_apart() -> None:
    bucket = corpus_tool._bucket
    assert bucket({"decision_class": "priority", "legal_options": [PASS]}) == "pass_only"
    assert bucket({"decision_class": "priority", "legal_options": [PASS, MANA]}) == "mana"
    assert bucket({"decision_class": "priority", "legal_options": [PASS, MANA, SPELL]}) == (
        "mana+spell"
    )
    assert bucket({"decision_class": "target", "legal_options": [PASS]}) == "one"
    assert bucket({"decision_class": "target", "legal_options": [PASS] * 9}) == "many"


def test_selection_keeps_the_rare_window_before_the_common_one_fills_the_quota() -> None:
    records = [_record("priority", i, [PASS]) for i in range(200)]
    records += [_record("priority", 1000 + i, [PASS, MANA, SPELL]) for i in range(5)]
    chosen = corpus_tool.select_corpus(records, caps={"priority": 20})
    assert len(chosen) == 20
    spell_windows = [r for r in chosen if len(r["request"]["legal_options"]) == 3]
    assert len(spell_windows) == 5, "every castable-spell window is kept"


def test_selection_is_deterministic_and_keeps_a_small_class_whole() -> None:
    records = [_record("priority", i, [PASS]) for i in range(100)]
    records += [_record("pile", 500 + i, [PASS, MANA]) for i in range(3)]
    first = corpus_tool.select_corpus(records, caps={"priority": 10})
    second = corpus_tool.select_corpus(copy.deepcopy(records), caps={"priority": 10})
    assert first == second
    assert sum(1 for r in first if r["request"]["decision_class"] == "pile") == 3
    assert sum(1 for r in first if r["request"]["decision_class"] == "priority") == 10


@pytest.mark.parametrize(
    ("answer", "needle"),
    [
        ({"selected_option_ids": ["nope"]}, "were not offered"),
        ({"selected_option_ids": ["a", "a"]}, "twice"),
        ({"selected_option_ids": []}, "minimum"),
        ({"selected_option_ids": ["a", "b"]}, "maximum"),
        ({"selected_option_ids": ["a"], "decision_id": "other"}, "decision id"),
        ({"selected_option_ids": ["a"], "actor_id": "other"}, "actor id"),
    ],
)
def test_legality_check_flags_each_defect(answer: dict[str, Any], needle: str) -> None:
    request = {
        "decision_id": "d",
        "actor_id": "x",
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": [{"option_id": "a"}, {"option_id": "b"}],
    }
    full = {"decision_id": "d", "actor_id": "x", **answer}
    problems = corpus_tool.legality_problems(request, full)
    assert any(needle in p for p in problems), problems
    ok = {"decision_id": "d", "actor_id": "x", "selected_option_ids": ["a"]}
    assert corpus_tool.legality_problems(request, ok) == []


CORPUS = corpus_tool.DEFAULT_CORPUS


@pytest.fixture(scope="module")
def corpus() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return corpus_tool.load_corpus(CORPUS)


@pytest.fixture(scope="module")
def replayed(corpus: tuple[dict[str, Any], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return corpus_tool.replay(corpus[1])


def test_corpus_is_large_and_covers_the_decision_classes_of_a_real_game(
    corpus: tuple[dict[str, Any], list[dict[str, Any]]],
) -> None:
    header, rows = corpus
    classes = {row["class"] for row in rows}
    assert len(rows) >= 300
    assert classes <= ExternalPilotDecisionPolicy._SUPPORTED_CLASSES
    # The classes a real pod meets in every game; a corpus without one has lost its sample.
    assert {"priority", "mana_payment", "target", "declare_attacker", "choose_use"} <= classes
    assert len(classes) >= 14
    assert header["stateless"] >= len(rows) * 0.8


def test_every_real_request_is_answered_without_raising_and_legally(
    corpus: tuple[dict[str, Any], list[dict[str, Any]]], replayed: list[dict[str, Any]]
) -> None:
    _, rows = corpus
    failures = []
    for row, outcome in zip(rows, replayed, strict=True):
        if outcome["answer"] is None:
            failures.append((row["class"], outcome["error"]))
            continue
        problems = corpus_tool.legality_problems(row["request"], outcome["answer"])
        if problems:
            failures.append((row["class"], problems))
    assert failures == []


def test_replay_is_deterministic(
    corpus: tuple[dict[str, Any], list[dict[str, Any]]], replayed: list[dict[str, Any]]
) -> None:
    _, rows = corpus
    again = corpus_tool.replay(rows)
    assert [corpus_tool.answer_key(o["answer"] or {}) for o in again] == [
        corpus_tool.answer_key(o["answer"] or {}) for o in replayed
    ]


def _first(rows: list[dict[str, Any]], decision_class: str) -> dict[str, Any]:
    return next(r for r in rows if r["class"] == decision_class and r["stateless"])


def test_a_renamed_option_id_is_caught(
    corpus: tuple[dict[str, Any], list[dict[str, Any]]],
) -> None:
    """Negative control: the check fails when the bridge renames the field the pilot answers by."""
    row = copy.deepcopy(_first(corpus[1], "priority"))
    for option in row["request"]["legal_options"]:
        option["id"] = option.pop("option_id")
    outcome = corpus_tool.replay([row])[0]
    caught = outcome["answer"] is None or corpus_tool.legality_problems(
        row["request"], outcome["answer"]
    )
    assert caught


def test_a_moved_players_list_changes_the_answer_or_raises(
    corpus: tuple[dict[str, Any], list[dict[str, Any]]],
) -> None:
    """Negative control: a state shape the pilot cannot read must not pass as the same answer."""
    rows = [r for r in corpus[1] if r["class"] == "declare_attacker" and r["stateless"]]
    assert rows, "the corpus has a stateless attack declaration"
    differing = 0
    for row in rows:
        mutated = copy.deepcopy(row)
        state = mutated["request"]["pilot_state"]
        state["seats"] = state.pop("players")
        outcome = corpus_tool.replay([mutated])[0]
        if outcome["answer"] is None or corpus_tool.answer_key(outcome["answer"]) != (
            corpus_tool.answer_key(row["answer"])
        ):
            differing += 1
    assert differing > 0


def _break_priority_answers(monkeypatch: pytest.MonkeyPatch, *, legal: bool) -> None:
    """Make the policy answer every priority window wrongly (``legal``: with another real option)."""
    original = ExternalPilotDecisionPolicy.decide

    def decide(self: ExternalPilotDecisionPolicy, request: dict[str, Any]) -> dict[str, Any]:
        answer = original(self, request)
        if request.get("decision_class") == "priority":
            options = [o["option_id"] for o in request["legal_options"]]
            answer = {
                **answer,
                "selected_option_ids": [options[-1] if legal else "not-offered"],
            }
        return answer

    monkeypatch.setattr(ExternalPilotDecisionPolicy, "decide", decide)


def test_a_pilot_that_answers_with_an_unoffered_option_is_caught(
    corpus: tuple[dict[str, Any], list[dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control for the legality check on real request shapes."""
    _, rows = corpus
    _break_priority_answers(monkeypatch, legal=False)
    problems = [
        corpus_tool.legality_problems(row["request"], outcome["answer"])
        for row, outcome in zip(rows, corpus_tool.replay(rows), strict=True)
        if row["class"] == "priority"
    ]
    assert problems and all(problems)


def test_diff_reports_nothing_for_the_recording_pilot_and_counts_a_changed_pilot(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    args = type("Args", (), {"corpus": CORPUS})()
    assert corpus_tool.diff(args) == 0
    quiet = capsys.readouterr().out
    assert "changed in total: 0 of" in quiet, quiet

    _break_priority_answers(monkeypatch, legal=True)
    assert corpus_tool.diff(args) == 0
    loud = capsys.readouterr().out
    priority_line = next(line for line in loud.splitlines() if line.strip().startswith("priority"))
    changed = int(priority_line.split()[1])
    assert changed > 0, loud
    assert "changed in total: 0 of" not in loud
