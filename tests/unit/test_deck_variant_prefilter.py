"""Unit tests for the deck-variant prefilter (#852).

No JVM: pure structural comparison plus the seeded commander-castability
Monte Carlo, repo decks only. Variants are built by editing a copy of
``data/decks/rogshai_current.json`` in ``tmp_path`` (with a distinct deck id so
they resolve through the XMage card facts instead of the project manifest).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.deck_profile import load_deck
from commander_lab.deck_variant import PREFILTER_TURNS, compare_variant
from commander_lab.models import RulesDeckInput

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "data/decks/rogshai_current.json"
TRIALS = 200

LANDS_TO_CUT = ["Adarkar Wastes", "Cascade Bluffs", "Clifftop Retreat"]
NON_MANA_NONLAND = "Aerial Extortionist"
MANA_ROCK = "Arcane Signet"
INVENTED_CARD = "Zzx Invented Card Qqq"


def _write_variant(
    tmp_path: Path,
    deck_id: str,
    *,
    remove: list[str] | None = None,
    add: list[str] | None = None,
) -> Path:
    """Copy the baseline deck, apply one-copy removals/additions, new deck id."""
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    payload["deck_id"] = deck_id
    payload["name"] = f"Test variant {deck_id}"
    cards = payload["cards"]
    for name in remove or []:
        for entry in cards:
            if entry["oracle_name"] == name and entry.get("quantity", 1) >= 1:
                if entry["quantity"] == 1:
                    cards.remove(entry)
                else:
                    entry["quantity"] -= 1
                break
        else:
            raise AssertionError(f"card to remove not found: {name}")
    for name in add or []:
        for entry in cards:
            if entry["oracle_name"] == name:
                entry["quantity"] = entry.get("quantity", 1) + 1
                break
        else:
            cards.append({"oracle_name": name, "quantity": 1, "zone": "main"})
    path = tmp_path / f"{deck_id.replace('/', '_')}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _baseline() -> RulesDeckInput:
    return load_deck(BASELINE_PATH)


def _cli() -> Any:
    path = ROOT / "scripts" / "deck_variant_prefilter.py"
    spec = importlib.util.spec_from_file_location("deck_variant_prefilter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_self_comparison_has_empty_diff_zero_deltas_and_pass() -> None:
    baseline = _baseline()
    result = compare_variant(baseline, baseline, trials=TRIALS, seed=20261016)
    assert result.added == ()
    assert result.removed == ()
    assert result.land_count_delta == 0
    assert result.colored_source_delta == {}
    assert result.flexible_source_delta == 0
    assert result.definitely_tapped_land_delta == 0
    assert result.conditionally_tapped_land_delta == 0
    assert result.t1_untapped_source_delta == {}
    for cmd in result.castability:
        for mode in ("play", "draw"):
            for turn in PREFILTER_TURNS:
                assert cmd.probability_delta[mode][turn] == 0.0
    assert result.baseline_ready and result.variant_ready
    assert result.verdict == "PASS_TO_GAMES"
    assert "not a ranking" in result.verdict_reason


def test_three_lands_to_nonlands_warns(tmp_path: Path) -> None:
    baseline = _baseline()
    variant_path = _write_variant(
        tmp_path,
        "rogshai/test-nolands",
        remove=LANDS_TO_CUT,
        add=[NON_MANA_NONLAND] * 3,
    )
    variant = load_deck(variant_path)
    result = compare_variant(baseline, variant, trials=TRIALS, seed=20261016)
    assert result.land_count_delta == -3
    for cmd in result.castability:
        for mode in ("play", "draw"):
            for turn in PREFILTER_TURNS:
                assert (
                    cmd.variant_probability[mode][turn] <= cmd.baseline_probability[mode][turn]
                ), "castability must not increase when 3 lands become non-lands"
    assert result.verdict == "WARN"
    assert "not a ranking" in result.verdict_reason


def test_invented_card_is_blocked(tmp_path: Path) -> None:
    baseline = _baseline()
    variant_path = _write_variant(
        tmp_path,
        "rogshai/test-invented",
        remove=[NON_MANA_NONLAND],
        add=[INVENTED_CARD],
    )
    variant = load_deck(variant_path)
    result = compare_variant(baseline, variant, trials=TRIALS, seed=20261016)
    assert result.verdict == "BLOCKED"
    assert not result.variant_ready
    assert INVENTED_CARD in result.variant_not_ready_cards
    assert "not a ranking" in result.verdict_reason


def test_single_nonland_swap_diff_lists_exactly_the_pair(tmp_path: Path) -> None:
    baseline = _baseline()
    variant_path = _write_variant(
        tmp_path,
        "rogshai/test-swap",
        remove=[NON_MANA_NONLAND],
        add=[MANA_ROCK],
    )
    variant = load_deck(variant_path)
    result = compare_variant(baseline, variant, trials=TRIALS, seed=20261016)
    assert result.added == ((MANA_ROCK, 1),)
    assert result.removed == ((NON_MANA_NONLAND, 1),)


def test_cli_exit_code_1_for_blocked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = _cli()
    variant_path = _write_variant(
        tmp_path,
        "rogshai/test-invented",
        remove=[NON_MANA_NONLAND],
        add=[INVENTED_CARD],
    )
    code = cli.main(
        [
            "--baseline",
            str(BASELINE_PATH),
            "--variant",
            str(variant_path),
            "--trials",
            str(TRIALS),
        ]
    )
    assert code == 1
    assert "BLOCKED" in capsys.readouterr().out


def test_cli_exit_code_2_for_unloadable_deck(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _cli()
    code = cli.main(
        [
            "--baseline",
            str(tmp_path / "does-not-exist.json"),
            "--variant",
            str(BASELINE_PATH),
        ]
    )
    assert code == 2


def test_cli_planned_games_and_time_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _cli()
    variant_a = _write_variant(
        tmp_path, "rogshai/test-a", remove=[NON_MANA_NONLAND], add=[MANA_ROCK]
    )
    variant_b = _write_variant(
        tmp_path,
        "rogshai/test-b",
        remove=LANDS_TO_CUT,
        add=[NON_MANA_NONLAND] * 3,
    )
    code = cli.main(
        [
            "--baseline",
            str(BASELINE_PATH),
            "--variant",
            str(variant_a),
            "--variant",
            str(variant_b),
            "--trials",
            str(TRIALS),
            "--seeds",
            "1-25",
            "--players",
            "4",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    # (1 baseline + 2 variants) * 25 seeds * 4 players = 300 games
    assert "Planned games: 300" in out
    # 300 / 56 = 5.36 -> 5.4 h, 300 / 22 = 13.64 -> 13.6 h
    assert "5.4-13.6 h" in out


def test_cli_json_is_stable_across_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = _cli()
    variant_path = _write_variant(
        tmp_path, "rogshai/test-a", remove=[NON_MANA_NONLAND], add=[MANA_ROCK]
    )
    argv = [
        "--baseline",
        str(BASELINE_PATH),
        "--variant",
        str(variant_path),
        "--trials",
        str(TRIALS),
        "--json",
    ]
    assert cli.main(argv) == 0
    first = capsys.readouterr().out
    assert cli.main(argv) == 0
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert payload["variants"][0]["verdict"] in {
        "BLOCKED",
        "WARN",
        "PASS_TO_GAMES",
    }
    assert payload["planned_games"] == 8  # (1 baseline + 1 variant) * 1 seed * 4 players
