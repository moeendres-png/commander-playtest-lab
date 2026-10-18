"""Plan output labels the detectable difference as an assumption (#906).

Both plan outputs (run_full_game_deck_comparison.py --plan-only and
deck_variant_prefilter.py) must carry a second sentence after the
"Detectable win-share difference ..." line: the figure assumes independent
games (per-pair sd 0.63); pairs ending identically make the real figure
smaller, and the run prints its own figure at the end.

The prefix "Detectable win-share difference per variant (80% power, 100 pairs)"
must stay byte-identical (asserted elsewhere); this test only checks the new
sentence is present.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Key phrases of the required second sentence (robust to minor rewording).
REQUIRED_PHRASES = (
    "assumes independent games",
    "per-pair sd 0.63",
    "identically",
    "prints its own figure",
)


def _comparison_cli() -> Any:
    path = ROOT / "scripts" / "run_full_game_deck_comparison.py"
    spec = importlib.util.spec_from_file_location("comparison_cli_906", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prefilter_cli() -> Any:
    path = ROOT / "scripts" / "deck_variant_prefilter.py"
    spec = importlib.util.spec_from_file_location("prefilter_cli_906", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_comparison_plan_labels_detectable_as_assumption(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _comparison_cli()
    code = cli.main(
        [
            "--baseline",
            str(ROOT / "data/decks/rogshai_current.json"),
            "--swap",
            "Sol Ring=>Mind Stone",
            "--opponent",
            str(ROOT / "data/opponents/hosts_of_mordor_precon.json"),
            "--opponent",
            str(ROOT / "data/opponents/lorehold_spirit_precon.json"),
            "--opponent",
            str(ROOT / "data/decks/opponents/kaervek/current/deck.json"),
            "--seeds",
            "1-25",
            "--out",
            str(tmp_path / "out"),
            "--plan-only",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    # Prefix unchanged (also asserted byte-identical elsewhere).
    assert "Detectable win-share difference per variant (80% power, 100 pairs)" in out
    for phrase in REQUIRED_PHRASES:
        assert phrase in out, f"missing phrase in comparison plan output: {phrase!r}"


def test_prefilter_plan_labels_detectable_as_assumption(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _prefilter_cli()
    code = cli.main(
        [
            "--baseline",
            str(ROOT / "data/decks/rogshai_current.json"),
            "--variant",
            str(ROOT / "data/decks/rogshai_current.json"),
            "--trials",
            "10",
            "--seeds",
            "1-2",
            "--players",
            "4",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Detectable win-share difference per variant (80% power," in out
    for phrase in REQUIRED_PHRASES:
        assert phrase in out, f"missing phrase in prefilter plan output: {phrase!r}"
