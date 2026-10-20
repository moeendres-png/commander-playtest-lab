"""Import measurement: infrastructure failures are not deck failures, and every unknown card of a
deck is named, not only the first one the importer reports."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "measure_precon_imports", ROOT / "scripts/measure_precon_imports.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _deck() -> dict[str, Any]:
    return {
        "commander": {"commanders": ["Missy"]},
        "cards": [
            {"oracle_name": "Sol Ring", "quantity": 1},
            {"oracle_name": "Psychic Paper", "quantity": 1},
            {"oracle_name": "Cybership", "quantity": 1},
        ],
    }


def _importer(unknown: set[str]):
    def try_import(deck: dict[str, Any]) -> tuple[str, str]:
        names = [c["oracle_name"] for c in deck["cards"]] + deck["commander"]["commanders"]
        for name in names:
            if name in unknown:
                return (
                    "FAILED",
                    f"X: bridge message 3 failed: deck_import_failed: UNKNOWN_CARD_NAME: {name}",
                )
        return "OK", ""

    return try_import


def test_only_an_importer_rejection_is_a_deck_failure() -> None:
    module = _module()
    rejection = "RulesEngineProtocolError: bridge message 3 failed: deck_import_failed: UNKNOWN_CARD_NAME: Missy"
    assert module.classify_error(rejection) == "FAILED"
    assert (
        module.classify_error("RulesEngineTimeout: no response in 300s") == "INFRASTRUCTURE_ERROR"
    )
    assert module.classify_error("BrokenPipeError: [Errno 32]") == "INFRASTRUCTURE_ERROR"


def test_enumeration_names_every_unknown_card_with_its_role_and_keeps_the_deck() -> None:
    module = _module()
    deck = _deck()
    original = copy.deepcopy(deck)
    report = module.enumerate_missing(deck, _importer({"Missy", "Psychic Paper", "Cybership"}))
    assert report["final_status"] == "OK_AFTER_REPLACEMENT"
    assert {(m["card"], m["role"]) for m in report["missing_cards"]} == {
        ("Missy", "commander"),
        ("Psychic Paper", "mainboard"),
        ("Cybership", "mainboard"),
    }
    assert deck == original


def test_enumeration_of_a_deck_without_unknown_cards_reports_none() -> None:
    report = _module().enumerate_missing(_deck(), _importer(set()))
    assert report == {"missing_cards": [], "final_status": "OK_AFTER_REPLACEMENT"}


def test_enumeration_stops_on_another_error_and_on_a_card_it_cannot_replace() -> None:
    module = _module()
    other = module.enumerate_missing(
        _deck(), lambda d: ("FAILED", "X: deck_import_failed: DECK_SIZE")
    )
    assert other["final_status"].startswith("OTHER_ERROR")
    phantom = module.enumerate_missing(
        _deck(), lambda d: ("FAILED", "X: deck_import_failed: UNKNOWN_CARD_NAME: Not In Deck")
    )
    assert phantom["final_status"] == "NOT_REPLACEABLE: Not In Deck"
