from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import RulesCardPrinting, RulesDeckInput


def _load_rules_card_printings(
    path: str | Path,
    *,
    deck_id: str,
) -> tuple[RulesCardPrinting, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("physical printing snapshot must contain a JSON object")
    if payload.get("deck_id") != deck_id:
        raise ValueError(
            f"physical printing deck ID mismatch: expected={deck_id!r}, "
            f"observed={payload.get('deck_id')!r}"
        )

    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise ValueError("physical printing snapshot must contain a cards list")

    declared_total = payload.get("cards_total")
    if (
        not isinstance(declared_total, int)
        or isinstance(declared_total, bool)
        or declared_total != len(cards)
    ):
        raise ValueError(
            "physical printing cards_total mismatch: "
            f"declared={declared_total!r}, observed={len(cards)}"
        )

    rows_by_position: dict[int, dict[str, object]] = {}
    for row in cards:
        if not isinstance(row, dict):
            raise ValueError("physical printing card records must be JSON objects")
        position = row.get("position")
        if (
            not isinstance(position, int)
            or isinstance(position, bool)
            or position < 1
        ):
            raise ValueError(f"invalid physical printing position: {position!r}")
        if position in rows_by_position:
            raise ValueError(f"duplicate physical printing position: {position}")
        rows_by_position[position] = row

    expected_positions = set(range(1, len(cards) + 1))
    if set(rows_by_position) != expected_positions:
        missing = sorted(expected_positions - set(rows_by_position))
        unexpected = sorted(set(rows_by_position) - expected_positions)
        raise ValueError(
            "physical printing positions must be contiguous from 1..cards_total; "
            f"missing={missing}, unexpected={unexpected}"
        )

    printings: list[RulesCardPrinting] = []
    for position in range(1, len(cards) + 1):
        row = rows_by_position[position]
        oracle_name = row.get("oracle_name")
        set_code = row.get("set")
        collector_number = row.get("collector_number")
        zone = row.get("zone", "main")

        if not isinstance(oracle_name, str):
            raise ValueError(
                f"physical printing position {position} has invalid oracle_name"
            )
        if not isinstance(set_code, str):
            raise ValueError(
                f"physical printing position {position} has invalid set"
            )
        if not isinstance(collector_number, str):
            raise ValueError(
                f"physical printing position {position} has invalid collector_number"
            )
        if not isinstance(zone, str):
            raise ValueError(
                f"physical printing position {position} has invalid zone"
            )

        printings.append(
            RulesCardPrinting(
                oracle_name=oracle_name,
                set_code=set_code,
                collector_number=collector_number,
                zone=zone,
            )
        )

    return tuple(printings)


def load_rules_deck_snapshot(
    path: str | Path,
    *,
    physical_printings_path: str | Path | None = None,
) -> RulesDeckInput:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("rules deck snapshot must contain a JSON object")

    commanders = tuple(payload["commander"]["commanders"])
    mainboard: list[str] = []
    sideboard: list[str] = []
    for entry in payload["cards"]:
        zone = entry.get("zone")
        if zone == "commander":
            continue
        if zone is None:
            zone = "main"
        target = mainboard if zone == "main" else sideboard if zone == "sideboard" else None
        if target is None:
            continue
        target.extend([entry["oracle_name"]] * int(entry.get("quantity", 1)))

    deck_id = payload["deck_id"]
    card_printings = (
        _load_rules_card_printings(physical_printings_path, deck_id=deck_id)
        if physical_printings_path is not None
        else ()
    )

    return RulesDeckInput(
        deck_id=deck_id,
        name=payload["name"],
        commander_names=commanders,
        mainboard=tuple(mainboard),
        sideboard=tuple(sideboard),
        card_printings=card_printings,
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
        if (
            not isinstance(normalized_file, str)
            or not normalized_file
            or Path(normalized_file).name != normalized_file
        ):
            raise ValueError(
                f"current deck manifest entry has invalid normalized_file: {deck_id!r}"
            )

        physical_printings_file = entry.get("physical_printings_file")
        physical_printings_path: Path | None = None
        if physical_printings_file is not None:
            if (
                not isinstance(physical_printings_file, str)
                or not physical_printings_file
                or Path(physical_printings_file).name != physical_printings_file
            ):
                raise ValueError(
                    "current deck manifest entry has invalid physical_printings_file: "
                    f"{deck_id!r}"
                )
            physical_printings_path = base / physical_printings_file

        deck = load_rules_deck_snapshot(
            base / normalized_file,
            physical_printings_path=physical_printings_path,
        )
        if deck.deck_id != deck_id:
            raise ValueError(
                f"current rules deck ID mismatch: manifest={deck_id!r}, file={deck.deck_id!r}"
            )
        decks[deck_id] = deck
    return decks


__all__ = ["load_project_rules_decks", "load_rules_deck_snapshot"]
