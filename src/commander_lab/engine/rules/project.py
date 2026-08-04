from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import RulesDeckInput


def load_rules_deck_snapshot(path: str | Path) -> RulesDeckInput:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    commanders = tuple(payload["commander"]["commanders"])
    mainboard: list[str] = []
    sideboard: list[str] = []
    for entry in payload["cards"]:
        zone = entry["zone"]
        target = mainboard if zone == "main" else sideboard if zone == "sideboard" else None
        if target is None:
            continue
        target.extend([entry["oracle_name"]] * int(entry["quantity"]))
    return RulesDeckInput(
        deck_id=payload["deck_id"],
        name=payload["name"],
        commander_names=commanders,
        mainboard=tuple(mainboard),
        sideboard=tuple(sideboard),
        deck_hash=payload.get("deck_hash"),
        source_path=str(path),
    )


def load_project_rules_decks(root: str | Path) -> dict[str, RulesDeckInput]:
    base = Path(root) / "data" / "decks"
    return {
        "korvold/current": load_rules_deck_snapshot(base / "korvold_current.json"),
        "rogshai/current": load_rules_deck_snapshot(base / "rogshai_current.json"),
    }


__all__ = ["load_project_rules_decks", "load_rules_deck_snapshot"]
