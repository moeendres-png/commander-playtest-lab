"""Optimizer-v2 full-game route for tactical/external-rules hypotheses (#733)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from commander_lab.engine.rules.full_game_batch import FullGameBatchReport
from commander_lab.engine.rules.full_game_comparison import aggregate_comparison
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import RulesDeckInput
from commander_lab.storage import sha256_value
from commander_lab.whole_deck.optimizer_v2_full_game import (
    FullGameRouteError,
    build_route_spec,
    played_deck_hash,
    route_report,
    select_route_hypotheses,
)

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "3cbf7741" + "0" * 32


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _control() -> RulesDeckInput:
    deck = load_rules_deck_snapshot(ROOT / "data/decks/rogshai_current.json")
    return deck.model_copy(update={"deck_hash": deck.deck_hash or _hash("control")})


def _row(control: RulesDeckInput, removed: str, added: str, tag: str) -> dict[str, Any]:
    mainboard = list(control.mainboard)
    mainboard.remove(removed)
    mainboard.append(added)
    return {
        "deck_hash": _hash(tag),
        "exact_mainboard": mainboard,
        "commander_names": list(control.commander_names),
        "removed_cards": [removed],
        "added_cards": [added],
        "blocked_cards": [added],
        "required_next_evidence_layer": "TACTICAL_EVIDENCE_REQUIRED",
    }


def _artifacts(control: RulesDeckInput) -> tuple[dict[str, Any], dict[str, Any]]:
    first = control.mainboard[0]
    last = control.mainboard[-1]
    rows = [
        _row(control, first, "Counterspell", "a"),
        _row(control, last, "Toxic Deluge", "b"),
        _row(control, first, "Swords to Plowshares", "c"),
    ]
    content = {"control_deck_hash": _hash("ctl"), "rows": rows}
    ledger = {**content, "ledger_hash": sha256_value(content)}
    queues = {
        "candidate_ledger_hash": ledger["ledger_hash"],
        "TOP_TACTICAL_REQUIRED_HYPOTHESES": [
            {
                "deck_hash": rows[0]["deck_hash"],
                "hypothesis_priority": 0.4,
                "required_next_evidence_layer": "TACTICAL_EVIDENCE_REQUIRED",
            },
            {
                "deck_hash": rows[1]["deck_hash"],
                "hypothesis_priority": 0.9,
                "required_next_evidence_layer": "TACTICAL_EVIDENCE_REQUIRED",
            },
        ],
        "TOP_EXTERNAL_RULES_REQUIRED_HYPOTHESES": [
            {
                "deck_hash": rows[2]["deck_hash"],
                "hypothesis_priority": 0.6,
                "required_next_evidence_layer": "EXTERNAL_RULES_EVIDENCE_REQUIRED",
            },
            # The same deck in two queues is played once.
            {
                "deck_hash": rows[1]["deck_hash"],
                "hypothesis_priority": 0.5,
                "required_next_evidence_layer": "EXTERNAL_RULES_EVIDENCE_REQUIRED",
            },
        ],
    }
    return ledger, queues


def _rehash(ledger: dict[str, Any]) -> dict[str, Any]:
    content = {key: value for key, value in ledger.items() if key != "ledger_hash"}
    return {**content, "ledger_hash": sha256_value(content)}


def _opponents() -> tuple[RulesDeckInput, ...]:
    paths = (
        "data/decks/opponents/kaervek/current/deck.json",
        "data/opponents/hosts_of_mordor_precon.json",
        "data/opponents/lorehold_spirit_precon.json",
    )
    decks = []
    for index, path in enumerate(paths):
        deck = load_rules_deck_snapshot(ROOT / path)
        decks.append(deck.model_copy(update={"deck_hash": deck.deck_hash or _hash(str(index))}))
    return tuple(decks)


def test_selects_top_hypotheses_across_queues_by_priority() -> None:
    control = _control()
    ledger, queues = _artifacts(control)
    selected = select_route_hypotheses(queues, ledger, control, limit=2)
    assert [h.deck_hash for h in selected] == [_hash("b"), _hash("c")]
    assert selected[0].queue == "TOP_TACTICAL_REQUIRED_HYPOTHESES"
    assert selected[0].added_cards == ("Toxic Deluge",)
    deck = selected[0].deck
    assert len(deck.mainboard) + len(deck.commander_names) == 100
    assert deck.commander_names == control.commander_names
    everything = select_route_hypotheses(queues, ledger, control, limit=10)
    assert len(everything) == 3  # de-duplicated


def test_route_fails_closed_on_mismatched_artifacts() -> None:
    control = _control()
    ledger, queues = _artifacts(control)
    with pytest.raises(FullGameRouteError, match="not built from this candidate ledger"):
        select_route_hypotheses({**queues, "candidate_ledger_hash": _hash("x")}, ledger, control)
    missing = _rehash({**ledger, "rows": ledger["rows"][:1]})
    with pytest.raises(FullGameRouteError, match="no candidate ledger row"):
        select_route_hypotheses(
            {**queues, "candidate_ledger_hash": missing["ledger_hash"]}, missing, control
        )
    broken_row = {**ledger["rows"][1], "added_cards": ["Sol Ring"]}
    broken = _rehash({**ledger, "rows": [ledger["rows"][0], broken_row, ledger["rows"][2]]})
    with pytest.raises(FullGameRouteError, match="does not reconstruct"):
        select_route_hypotheses(
            {**queues, "candidate_ledger_hash": broken["ledger_hash"]}, broken, control
        )
    with pytest.raises(FullGameRouteError, match="unknown hypothesis queues"):
        select_route_hypotheses(queues, ledger, control, groups=("TOP_EVERYTHING",))


def test_route_spec_and_report_stay_exploratory() -> None:
    control = _control()
    ledger, queues = _artifacts(control)
    hypotheses = select_route_hypotheses(queues, ledger, control, limit=2)
    spec = build_route_spec(control, hypotheses, _opponents(), seeds=(1, 2), xmage_commit=COMMIT)
    assert spec.contenders[0].deck_id == control.deck_id
    assert spec.player_count == 4 and spec.pod_count == 8
    empty = FullGameBatchReport(
        total_cases=0, completed_cases=0, failed_cases=0, resumed_cases=0, records=()
    )
    comparison = aggregate_comparison(spec, empty)
    report = route_report(
        control=control,
        hypotheses=hypotheses,
        comparison=comparison,
        candidate_ledger_hash=ledger["ledger_hash"],
        queues=("TOP_TACTICAL_REQUIRED_HYPOTHESES",),
    )
    assert [row.route_status for row in report.hypotheses] == ["FULL_GAME_NOT_DECIDED"] * 2
    assert all(row.confirmatory_eligible is False for row in report.hypotheses)
    payload = report.model_dump(mode="json")
    assert payload["structural_decision_authority"] is False
    assert payload["evidence_class"] == "exploratory_xmage_full_game"


def test_cli_plan_only_from_an_optimizer_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    control = _control()
    ledger, queues = _artifacts(control)
    (tmp_path / "ALL_CANDIDATE_LEDGER.json").write_text(json.dumps(ledger), encoding="utf-8")
    (tmp_path / "ROUTED_HYPOTHESIS_QUEUES.json").write_text(json.dumps(queues), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(
            "route_cli", ROOT / "scripts/run_optimizer_v2_full_game_route.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        code = module.main(
            [
                "--run-dir",
                str(tmp_path),
                "--seeds",
                "1-3",
                "--limit",
                "2",
                "--plan-only",
                "--workers",
                "2",
            ]
        )
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    assert code == 0
    out = capsys.readouterr().out
    assert "2 hypotheses" in out and "36 games" in out
    assert "+Toxic Deluge" in out


def test_edited_ledger_no_longer_matches_its_hash() -> None:
    control = _control()
    ledger, queues = _artifacts(control)
    tampered = [dict(row) for row in ledger["rows"]]
    tampered[0]["blocked_cards"] = []
    with pytest.raises(FullGameRouteError, match="its own ledger_hash"):
        select_route_hypotheses(queues, {**ledger, "rows": tampered}, control)


def test_games_are_bound_to_the_list_actually_played() -> None:
    control = _control()
    ledger, queues = _artifacts(control)
    hypotheses = select_route_hypotheses(queues, ledger, control)
    for hypothesis in hypotheses:
        assert hypothesis.deck.deck_hash == hypothesis.played_deck_hash
        assert hypothesis.played_deck_hash == played_deck_hash(
            control.commander_names, hypothesis.deck.mainboard
        )
        assert hypothesis.played_deck_hash != hypothesis.deck_hash
    spec = build_route_spec(control, hypotheses, _opponents(), seeds=(1,), xmage_commit=COMMIT)
    played = spec.contenders[0]
    assert played.card_printings == () and played.sideboard == ()
    assert played.deck_hash == played_deck_hash(control.commander_names, control.mainboard)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"commander_names": []}, "control's commanders"),
        ({"commander_names": ["Someone Else"]}, "control's commanders"),
    ],
)
def test_row_must_name_the_control_commanders(change: dict[str, Any], message: str) -> None:
    from commander_lab.whole_deck.optimizer_v2_full_game import variant_deck

    control = _control()
    ledger, _queues = _artifacts(control)
    with pytest.raises(FullGameRouteError, match=message):
        variant_deck(control, {**ledger["rows"][0], **change})


def test_row_that_is_not_a_commander_deck_fails_closed() -> None:
    from commander_lab.whole_deck.optimizer_v2_full_game import variant_deck

    control = _control()
    ledger, _queues = _artifacts(control)
    row = dict(ledger["rows"][0])
    row["exact_mainboard"] = [*row["exact_mainboard"], "Island"]
    row["added_cards"] = [*row["added_cards"], "Island"]
    with pytest.raises(FullGameRouteError, match="legal deck input"):
        variant_deck(control, row)
