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
    manifest_path = base / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = payload.get("decks")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("current deck manifest contains no operational decks")

    decks: dict[str, RulesDeckInput] = {}
    for deck_id, entry in entries.items():
        if not isinstance(entry, dict):
            raise ValueError(f"invalid current deck manifest entry for {deck_id!r}")
        normalized_file = entry.get("normalized_file")
        if not isinstance(normalized_file, str) or not normalized_file:
            raise ValueError(f"current deck manifest entry missing normalized_file: {deck_id!r}")
        deck = load_rules_deck_snapshot(base / normalized_file)
        if deck.deck_id != deck_id:
            raise ValueError(
                f"current rules deck ID mismatch: manifest={deck_id!r}, file={deck.deck_id!r}"
            )
        decks[deck_id] = deck
    return decks


__all__ = ["load_project_rules_decks", "load_rules_deck_snapshot"]
