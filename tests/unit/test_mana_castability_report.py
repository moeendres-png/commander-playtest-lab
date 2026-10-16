"""CLI coverage for scripts/mana_castability_report.py (#844).

No JVM: the report only needs structural profiles and the seeded Monte Carlo.
Uses repo data only (data/decks/rogshai_current.json, project manifest).
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

from commander_lab.mana_analysis import DEFAULT_CASTABILITY_SEED

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "data/decks/rogshai_current.json"
TRIALS = 200

# Captured from the unchanged script (before the --json flag existed):
#   PYTHONPATH=src python scripts/mana_castability_report.py \
#       --deck data/decks/rogshai_current.json --trials 200
# Byte-for-byte: test_text_output_matches_golden fails if the text format changes.
GOLDEN_TEXT = "Deck: rogshai/current — Ishai + Rograkh — Current Physical Photo-Verified Build\nStructural profile: project manifest\nTrials: 200, seed: 20261016\n\nCommander: Ishai, Ojutai Dragonspeaker (MV 4, pips {U:1, W:1})\nmode  T2      T3      T4      T5      T6      T7      T8      T9      T10   \nplay  0.000    0.210    0.600    0.690    0.785    0.840    0.885    0.920    0.935  \ndraw  0.000    0.270    0.670    0.785    0.840    0.885    0.920    0.935    0.950  \nexpected earliest castable turn: play 4.73, draw 4.42\n\nCommander: Rograkh, Son of Rohgahh (MV 0, pips {})\nmode  T2      T3      T4      T5      T6      T7      T8      T9      T10   \nplay  1.000    1.000    1.000    1.000    1.000    1.000    1.000    1.000    1.000  \ndraw  1.000    1.000    1.000    1.000    1.000    1.000    1.000    1.000    1.000  \nexpected earliest castable turn: play 1.00, draw 1.00\n\n"


def _cli() -> Any:
    path = ROOT / "scripts" / "mana_castability_report.py"
    spec = importlib.util.spec_from_file_location("mana_castability_report", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_text_report(text: str) -> dict[str, dict[str, Any]]:
    """Extract the printed numbers per commander from the text report."""
    report: dict[str, dict[str, Any]] = {}
    for block in text.split("Commander: ")[1:]:
        lines = block.splitlines()
        name = lines[0].rsplit(" (MV ", 1)[0]
        probabilities: dict[str, list[float]] = {}
        expected: dict[str, float | None] = {}
        for line in lines[1:]:
            mode_match = re.match(r"^(play|draw)\s+(.+)$", line)
            if mode_match:
                probabilities[mode_match.group(1)] = [
                    float(value) for value in mode_match.group(2).split()
                ]
                continue
            expected_match = re.match(
                r"^expected earliest castable turn: play (.+), draw (.+)$", line
            )
            if expected_match:
                for mode, raw in zip(("play", "draw"), expected_match.groups(), strict=True):
                    expected[mode] = None if raw == "never by T10" else float(raw)
        report[name] = {"probability": probabilities, "expected_turn": expected}
    return report


def test_text_output_matches_golden(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _cli()
    assert cli.main(["--deck", str(DECK), "--trials", str(TRIALS)]) == 0
    assert capsys.readouterr().out == GOLDEN_TEXT


def test_json_values_match_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _cli()
    assert cli.main(["--deck", str(DECK), "--trials", str(TRIALS)]) == 0
    parsed = _parse_text_report(capsys.readouterr().out)

    assert cli.main(["--deck", str(DECK), "--trials", str(TRIALS), "--json"]) == 0
    raw = capsys.readouterr().out
    payload = json.loads(raw)
    # One JSON document on stdout: sorted keys, indent 2, nothing else.
    assert raw == json.dumps(payload, indent=2, sort_keys=True) + "\n"

    assert payload["deck_id"] == "rogshai/current"
    assert payload["name"] == "Ishai + Rograkh — Current Physical Photo-Verified Build"
    assert payload["structural_profile_source"] == "project manifest"
    assert payload["trials"] == TRIALS
    assert payload["seed"] == DEFAULT_CASTABILITY_SEED

    assert set(payload["probability"]) == set(parsed)
    assert set(payload["expected_turn"]) == set(parsed)
    for name, printed in parsed.items():
        for mode in ("play", "draw"):
            assert payload["probability"][name][mode] == {
                str(turn): value
                for turn, value in zip(range(2, 11), printed["probability"][mode], strict=True)
            }
            assert payload["expected_turn"][name][mode] == printed["expected_turn"][mode]


@pytest.mark.parametrize("extra_args", [[], ["--json"]])
def test_same_arguments_give_identical_output(
    capsys: pytest.CaptureFixture[str], extra_args: list[str]
) -> None:
    cli = _cli()
    args = ["--deck", str(DECK), "--trials", str(TRIALS), *extra_args]
    assert cli.main(args) == 0
    first = capsys.readouterr().out
    assert cli.main(args) == 0
    second = capsys.readouterr().out
    assert first == second


def test_trials_zero_is_argparse_error(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _cli()
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--deck", str(DECK), "--trials", "0"])
    assert excinfo.value.code == 2
    assert capsys.readouterr().out == ""


def _no_commander_deck(tmp_path: Path) -> Path:
    payload = {
        "deck_id": "no-commander",
        "name": "no commander",
        "commander": {"commanders": []},
        "cards": [{"oracle_name": "Plains", "zone": "main", "quantity": 60}],
    }
    path = tmp_path / "no_commander.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize("extra_args", [[], ["--json"]])
def test_deck_without_commander_keeps_loader_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], extra_args: list[str]
) -> None:
    """A deck with no commander never loads: the snapshot loader rejects it.

    This pins the current script's behavior; --json does not change it.
    """
    cli = _cli()
    deck_file = _no_commander_deck(tmp_path)
    with pytest.raises(ValueError, match="non-empty commanders list"):
        cli.main(["--deck", str(deck_file), "--trials", str(TRIALS), *extra_args])
    assert capsys.readouterr().out == ""
