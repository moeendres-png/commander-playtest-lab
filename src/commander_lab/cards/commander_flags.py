"""Game Changers and Commander bans from a local Scryfall bulk file (E11, R2-01).

The flags come from one stored Oracle bulk file (``oracle-cards-<UTC stamp>.jsonl[.gz]``), read
from disk: nothing here opens a network connection, and no deck or card list leaves the machine.
``derive_flags`` reads the bulk once and yields the small committed file
``data/cards/commander_flags.json``; ``label_deck`` counts a deck's cards against it.

The result is a label, not a rule: the count of Game Changers and the cards Scryfall lists as
banned in Commander. It is not a Commander Brackets assessment (tutors, extra turns, mass land
denial and two-card combos are not covered), and the bracket thresholds are not coded here.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from .normalize import oracle_lookup_key

SCHEMA = "commander-card-flags-1.0.0"
SCOPE = (
    "Label only: the number of Game Changers in a deck and the cards banned in Commander, from one "
    "stored Scryfall Oracle bulk file. Not a Commander Brackets assessment (tutors, extra turns, "
    "mass land denial and two-card combos are not covered). Derived offline; nothing is sent to "
    "any service."
)
DEFAULT_FLAGS_PATH = Path(__file__).resolve().parents[3] / "data" / "cards" / "commander_flags.json"
_BULK_NAME = re.compile(
    r"^oracle-cards-(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\.jsonl(?:\.gz)?$"
)
_FACE_SEPARATOR = " // "


@dataclass(frozen=True)
class CommanderFlags:
    """The loaded flags file: positive lists only, keyed by the normalized card name."""

    source: Mapping[str, object]
    game_changers: Mapping[str, str]
    commander_banned: Mapping[str, str]


@dataclass(frozen=True)
class DeckLabel:
    """Counts for one deck. Each card counts once, however often the list names it."""

    game_changer_count: int
    game_changers: tuple[str, ...]
    commander_banned: tuple[str, ...]
    data_as_of: str
    bulk_sha256: str
    scope: str

    def as_dict(self) -> dict[str, object]:
        return {
            "game_changer_count": self.game_changer_count,
            "game_changers": list(self.game_changers),
            "commander_banned": list(self.commander_banned),
            "data_as_of": self.data_as_of,
            "bulk_sha256": self.bulk_sha256,
            "scope": self.scope,
        }


def bulk_data_as_of(path: Path) -> str:
    """The UTC time in the bulk file name; a file with another name is refused, not guessed."""
    match = _BULK_NAME.match(path.name)
    if match is None:
        raise ValueError(
            f"bulk file name must look like oracle-cards-YYYYMMDDHHMMSS.jsonl[.gz]: {path.name}"
        )
    year, month, day, hour, minute, second = match.groups()
    return f"{year}-{month}-{day}T{hour}:{minute}:{second}Z"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _open_text(path: Path) -> IO[str]:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def _cards(path: Path) -> Iterator[dict[str, object]]:
    with _open_text(path) as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            card = json.loads(line)
            if not isinstance(card, dict):
                raise ValueError(f"{path.name} line {number}: a card must be a JSON object")
            yield card


def derive_flags(bulk_path: Path) -> dict[str, object]:
    """The flags file content for one Oracle bulk file. Sorted, so the same bulk gives the same bytes."""
    data_as_of = bulk_data_as_of(bulk_path)
    game_changers: dict[str, str] = {}
    banned: dict[str, str] = {}
    legality_counts: dict[str, int] = {}
    card_count = 0
    for card in _cards(bulk_path):
        card_count += 1
        name = str(card["name"])
        oracle_id = str(card["oracle_id"])
        legalities = card.get("legalities")
        status = (
            str(legalities.get("commander", "unknown"))
            if isinstance(legalities, dict)
            else "unknown"
        )
        legality_counts[status] = legality_counts.get(status, 0) + 1
        if card.get("game_changer") is True:
            game_changers[name] = oracle_id
        if status == "banned":
            banned[name] = oracle_id
    if card_count == 0:
        raise ValueError(f"{bulk_path.name} holds no cards")
    return {
        "schema": SCHEMA,
        "scope": SCOPE,
        "source": {
            "kind": "scryfall_oracle_cards_bulk",
            "bulk_file": bulk_path.name,
            "bulk_sha256": _sha256_file(bulk_path),
            "data_as_of": data_as_of,
            "card_count": card_count,
            "commander_legality_counts": dict(sorted(legality_counts.items())),
        },
        "game_changers": [
            {"name": name, "oracle_id": game_changers[name]} for name in sorted(game_changers)
        ],
        "commander_banned": [{"name": name, "oracle_id": banned[name]} for name in sorted(banned)],
    }


def _index(rows: object, label: str) -> dict[str, str]:
    if not isinstance(rows, list):
        raise ValueError(f"commander flags: {label} must be a list")
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            raise ValueError(f"commander flags: {label} rows need a name")
        name = row["name"]
        out[oracle_lookup_key(name)] = name
        if _FACE_SEPARATOR in name:  # a deck may list a double-faced card by its front face
            out[oracle_lookup_key(name.split(_FACE_SEPARATOR)[0])] = name
    return out


def load_flags(path: Path | None = None) -> CommanderFlags:
    """Read the committed flags file. A missing or malformed file is an error, never an empty set."""
    target = path or DEFAULT_FLAGS_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError(f"commander flags: unexpected schema in {target.name}")
    source = payload.get("source")
    if (
        not isinstance(source, dict)
        or not source.get("data_as_of")
        or not source.get("bulk_sha256")
    ):
        raise ValueError("commander flags: source needs data_as_of and bulk_sha256")
    return CommanderFlags(
        source=source,
        game_changers=_index(payload.get("game_changers"), "game_changers"),
        commander_banned=_index(payload.get("commander_banned"), "commander_banned"),
    )


def label_deck(card_names: Iterable[str], flags: CommanderFlags | None = None) -> DeckLabel:
    """Count a deck's Game Changers and banned cards. Unknown names are simply not flagged."""
    loaded = flags or load_flags()
    found_gc: dict[str, None] = {}
    found_banned: dict[str, None] = {}
    for raw in card_names:
        key = oracle_lookup_key(raw)
        if key in loaded.game_changers:
            found_gc[loaded.game_changers[key]] = None
        if key in loaded.commander_banned:
            found_banned[loaded.commander_banned[key]] = None
    return DeckLabel(
        game_changer_count=len(found_gc),
        game_changers=tuple(sorted(found_gc)),
        commander_banned=tuple(sorted(found_banned)),
        data_as_of=str(loaded.source["data_as_of"]),
        bulk_sha256=str(loaded.source["bulk_sha256"]),
        scope=SCOPE,
    )
