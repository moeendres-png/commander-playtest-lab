from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.full_game import FULL_GAME_EVIDENCE_CLASS

ROOT = Path(__file__).resolve().parents[2]


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "real_4p_full_game_smoke",
        ROOT / "scripts/run_real_4p_full_game_smoke.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_4p_setup_uses_four_existing_exact_100s() -> None:
    module = _load_script()
    scenario, decks, pilots = module.build_setup(ROOT)

    assert scenario.player_count == 4
    assert scenario.candidate_id == "rogshai/current"
    assert scenario.opponent_deck_ids == (
        "kaervek/current",
        "opponent/hosts-of-mordor-precon",
        "opponent/lorehold-spirit-precon",
    )
    assert tuple(deck.deck_id for deck in decks) == (
        "rogshai/current",
        "kaervek/current",
        "opponent/hosts-of-mordor-precon",
        "opponent/lorehold-spirit-precon",
    )
    assert [len(deck.mainboard) + len(deck.commander_names) for deck in decks] == [100] * 4
    assert [pilot.seat for pilot in pilots] == [1, 2, 3, 4]
    assert all(pilot.deck_id == deck.deck_id for pilot, deck in zip(pilots, decks, strict=True))
    assert all(deck.deck_hash is not None for deck in decks)


def test_real_4p_setup_preserves_exact_commander_configurations() -> None:
    module = _load_script()
    _scenario, decks, _pilots = module.build_setup(ROOT)

    assert decks[0].commander_names == (
        "Ishai, Ojutai Dragonspeaker",
        "Rograkh, Son of Rohgahh",
    )
    assert decks[1].commander_names == ("Kaervek the Merciless",)
    assert decks[2].commander_names == ("Sauron, Lord of the Rings",)
    assert decks[3].commander_names == ("Quintorius, History Chaser",)


def test_real_4p_smoke_is_technical_conformance_only() -> None:
    module = _load_script()
    assert module.FULL_GAME_EVIDENCE_CLASS == FULL_GAME_EVIDENCE_CLASS
    assert module.FULL_GAME_EVIDENCE_CLASS == "technical_conformance_only"
    assert module.XMAGE_COMMIT == "db134b9737e951367d65ef5806ad986319cc73ab"
    assert module.DEFAULT_SMOKE_DECISIONS > 0
