"""The Deckbau candidate must mirror the current recorded Chulane list."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_chulane_baseline_mirrors_100_card_owner_list() -> None:
    source = (ROOT / "data/decks/chulane_current.txt").read_text(encoding="utf-8")
    snapshot = json.loads(
        (ROOT / "data/decks/deckbau/chulane_current.json").read_text(encoding="utf-8")
    )
    sections: dict[str, Counter[str]] = {"Commander": Counter(), "Deck": Counter()}
    section = ""
    for line in source.splitlines():
        if line in sections:
            section = line
            continue
        match = re.fullmatch(r"(\d+) (.+)", line)
        if match is not None:
            sections[section][match.group(2)] += int(match.group(1))

    assert snapshot["deck_id"] == "custom/chulane"
    assert snapshot["commander"]["commanders"] == ["Chulane, Teller of Tales"]
    assert sections["Commander"] == Counter(snapshot["commander"]["commanders"])

    main: Counter[str] = Counter()
    for row in snapshot["cards"]:
        if row["zone"] == "main":
            main[row["oracle_name"]] += row["quantity"]
    assert main == sections["Deck"]
    assert sum(main.values()) == 99
    assert main["Whitemane Lion"] == 1
    assert main["Elvish Mystic"] == 1
    assert "Aether Adept" not in main
    assert "Kor Skyfisher" not in main


def test_deckbau_shortlist_does_not_target_old_owner_deck() -> None:
    for path in ("scripts/deckbau_eval.py", "scripts/deckbau_pool_readiness.py"):
        content = (ROOT / path).read_text(encoding="utf-8")
        assert 'Path("data/decks/rogshai_current.json")' not in content
    pool = (ROOT / "scripts/deckbau_pool_readiness.py").read_text(encoding="utf-8")
    assert 'Path("data/decks/deckbau/chulane_current.json")' in pool
