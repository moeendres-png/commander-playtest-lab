"""Deck-readiness checks against the repo's card data (#834).

Uses repo data only (``data/cards/xmage_card_facts.json`` and
``data/cards/pilot_card_knowledge.json``), never ``data/collections/**``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from commander_lab.deck_readiness import CardReadinessStatus, check_deck
from commander_lab.models import RulesDeckInput

ROOT = Path(__file__).resolve().parents[2]
_FACTS = json.loads((ROOT / "data/cards/xmage_card_facts.json").read_text(encoding="utf-8"))
_PILOT_CARDS = json.loads(
    (ROOT / "data/cards/pilot_card_knowledge.json").read_text(encoding="utf-8")
)["cards"]


def _known_names() -> list[str]:
    """Card names present in both card-data files (repo data only)."""
    return sorted(set(_FACTS["cards"]) & set(_PILOT_CARDS))


def _deck(names: list[str], deck_id: str = "readiness-test") -> RulesDeckInput:
    commander, *rest = names
    return RulesDeckInput(
        deck_id=deck_id,
        name=deck_id,
        commander_names=(commander,),
        mainboard=tuple((rest * 100)[:99]),
    )


def _write_deck_file(tmp_path: Path, names: list[str], deck_id: str) -> Path:
    payload = {
        "deck_id": deck_id,
        "name": deck_id,
        "commander": names[0],
        "cards": [{"oracle_name": name, "zone": "main", "quantity": 1} for name in names[1:100]]
        + [{"oracle_name": names[0], "zone": "commander", "quantity": 1}],
    }
    path = tmp_path / f"{deck_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _cli_script(name: str):  # type: ignore[no-untyped-def]
    path = ROOT / f"scripts/{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deck_of_known_cards_is_ready() -> None:
    report = check_deck(_deck(_known_names()[:100]))
    assert report.ready is True
    assert report.counts[CardReadinessStatus.OK] == 100
    assert all(card.status is CardReadinessStatus.OK for card in report.cards)


def test_invented_card_is_no_card_facts() -> None:
    deck = _deck(["Invented Card Name Qzx 999", *_known_names()[1:100]])
    report = check_deck(deck)
    assert report.ready is False
    assert report.cards[0].name == "Invented Card Name Qzx 999"
    assert report.cards[0].status is CardReadinessStatus.NO_CARD_FACTS
    assert report.counts[CardReadinessStatus.NO_CARD_FACTS] == 1


def test_missing_in_xmage_is_reported() -> None:
    missing: list[str] = _FACTS["missing"]
    assert missing, "the fixture facts need a missing entry"
    deck = _deck([missing[0], *_known_names()[1:100]])
    report = check_deck(deck)
    assert report.ready is False
    assert report.cards[0].status is CardReadinessStatus.KNOWN_MISSING_IN_XMAGE
    assert report.counts[CardReadinessStatus.KNOWN_MISSING_IN_XMAGE] == 1


def test_double_faced_card_resolves_by_front_face() -> None:
    double_faced = next(name for name in _FACTS["cards"] if " // " in name and name in _PILOT_CARDS)
    deck = _deck([double_faced, *_known_names()[1:100]])
    report = check_deck(deck)
    assert report.cards[0].status is CardReadinessStatus.OK


def test_cli_exit_code_1_for_not_ready_deck(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _cli_script("deck_readiness")
    deck_file = _write_deck_file(
        tmp_path, ["Invented Card Name Qzx 999", *_known_names()[1:100]], "not-ready"
    )
    assert cli.main(["--deck", str(deck_file)]) == 1
    out = capsys.readouterr().out
    assert "NOT READY" in out
    assert "NO_CARD_FACTS" in out
    assert "export_xmage_card_facts.py" in out


def test_cli_exit_code_0_and_json_for_ready_deck(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _cli_script("deck_readiness")
    deck_file = _write_deck_file(tmp_path, _known_names()[:100], "ready")
    assert cli.main(["--deck", str(deck_file)]) == 0
    assert "READY" in capsys.readouterr().out
    assert cli.main(["--deck", str(deck_file), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is True
    assert payload["decks"][0]["counts"]["OK"] == 100
    assert payload["decks"][0]["cards"][0]["status"] == "OK"


def test_comparison_require_ready_refuses_not_ready_deck(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _cli_script("run_full_game_deck_comparison")
    ready_file = _write_deck_file(tmp_path, _known_names()[:100], "ready")
    not_ready_file = _write_deck_file(
        tmp_path, ["Invented Card Name Qzx 999", *_known_names()[1:100]], "not-ready"
    )
    code = cli.main(
        [
            "--baseline",
            str(ready_file),
            "--variant",
            str(ready_file),
            "--opponent",
            str(not_ready_file),
            "--seeds",
            "1",
            "--out",
            str(tmp_path / "out"),
            "--require-ready",
        ]
    )
    assert code == 1
    assert "--require-ready" in capsys.readouterr().err


def test_comparison_require_ready_passes_ready_decks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _cli_script("run_full_game_deck_comparison")
    ready_file = _write_deck_file(tmp_path, _known_names()[:100], "ready")
    opponent_file = _write_deck_file(tmp_path, _known_names()[50:150], "ready-opponent")
    code = cli.main(
        [
            "--baseline",
            str(ready_file),
            "--variant",
            str(ready_file),
            "--opponent",
            str(opponent_file),
            "--seeds",
            "1",
            "--out",
            str(tmp_path / "out"),
            "--require-ready",
            "--plan-only",
        ]
    )
    assert code == 0
    assert "is READY" in capsys.readouterr().out
