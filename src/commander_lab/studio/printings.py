"""The collection's own printings: parse the workbook's printing references and resolve
their card images locally from the public Scryfall default-cards bulk file.

The Owner's rule (issue #1342): a card is shown as the printing the collection actually
holds when that printing is identifiable from the workbook; the references live in the
lot sheet (``02_PHYSICAL_LOTS``) and are written to ``card_printing`` by the inventory
import. A reference that cannot be read (``unmapped[...]``, ``unknown``, a collector
number without a set) is never guessed: the row stays UNRESOLVED and the standard-printing
rule of the Scryfall import decides the picture instead.

Nothing about the collection leaves the machine (``AGENTS.md`` §12): the printings are
matched locally against the public bulk file, a plain GET download of public card data;
the evaluation runs locally, exactly as for the Scryfall catalogue import.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from . import catalog
from .store import StudioStore

_BATCH = 75

EXACT_CANDIDATE = "EXACT_CANDIDATE"
UNRESOLVED = "UNRESOLVED"
BASIS_EXACT = "EXACT_COLLECTION"

# Language codes Scryfall prints cards in (ISO 639-1 plus its historical codes). A
# two-part reference suffix that is not one of these and not a finish word is unreadable:
# the lot sheets mix both meanings in the same position.
_LANGUAGES = frozenset(
    {
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "ja",
        "ko",
        "ru",
        "zhs",
        "zht",
        "he",
        "ar",
        "la",
        "grc",
        "sa",
        "px",
        "qya",
        "ph",
    }
)
_FINISHES = frozenset({"nonfoil", "foil", "etched", "gilded", "textured", "finish_unknown"})

_REF = re.compile(r"^([A-Za-z0-9]+)#(.+)$")


def _finish(value: str | None) -> str | None:
    """A stored finish word; ``finish_unknown`` means the sheet does not know it."""
    if value is None or value == "finish_unknown":
        return None
    return value


def parse_printing_ref(
    raw: object,
) -> tuple[str, str, str | None, str | None] | None:
    """Read one ``printing_ref`` of the lot sheet.

    Returns ``(set_code, collector_number, lang, finish)`` with the set code lowercased,
    or ``None`` when the reference does not name one printing unambiguously. The forms
    in the workbook are ``SET#NR``, ``SET#NR|lang``, ``SET#NR|finish`` and
    ``SET#NR|lang|finish``; in the two-part form the suffix is a language in most lots
    and a finish in a few, so both vocabularies are accepted there. A fraction number
    (``194/361``, an old export form) names its numerator printing. ``unmapped[...]``
    lists several candidate printings on purpose, ``unknown`` and a bare ``collector#``
    prefix name none: all three read as ``None``.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.startswith("unmapped["):
        return None
    parts = text.split("|")
    match = _REF.match(parts[0].strip())
    if match is None:
        return None
    set_code = match.group(1).lower()
    if set_code == "collector":
        return None
    number = match.group(2).strip()
    if "/" in number:
        number = number.split("/", 1)[0].strip()
    if not number:
        return None
    lang: str | None = None
    finish: str | None = None
    suffixes = [part.strip().lower() for part in parts[1:] if part.strip()]
    if len(suffixes) > 2:
        return None
    for suffix in suffixes:
        if suffix in _LANGUAGES and lang is None:
            lang = suffix
        elif suffix in _FINISHES and finish is None:
            finish = _finish(suffix)
        else:
            return None
    return (set_code, number, lang, finish)


def _image(holder: Mapping[str, object]) -> str | None:
    uris = holder.get("image_uris")
    if not isinstance(uris, Mapping):
        return None
    value = uris.get("normal")
    return value if isinstance(value, str) and value else None


def _images(card: Mapping[str, object]) -> tuple[str | None, str | None]:
    """Front and back image address of one Scryfall printing, mirroring catalog._row:
    the front is the printing's own image or its first face's; the back exists only
    when the printing itself carries no image and a second face does."""
    faces = card.get("card_faces")
    face_rows: list[Mapping[str, object]] = (
        [face for face in faces if isinstance(face, Mapping)] if isinstance(faces, list) else []
    )
    front = _image(card) or (_image(face_rows[0]) if face_rows else None)
    back = _image(face_rows[1]) if len(face_rows) > 1 and _image(card) is None else None
    return front, back


Lookup = Callable[
    [Sequence[Mapping[str, str]]],
    tuple[list[Mapping[str, object]], list[Mapping[str, str]]],
]


def _pick(
    printings: Sequence[Mapping[str, object]], lang: str | None
) -> Mapping[str, object] | None:
    """The one printing of a (set, number) the reference means, or None when the answer
    is not unique: the reference's language when it is known, English when it is not,
    and a single returned printing as itself. Several printings in other languages are
    an ambiguity of the source data, never a choice to invent."""
    if lang is not None:
        named = [card for card in printings if card.get("lang") == lang]
        return named[0] if len(named) == 1 else None
    english = [card for card in printings if card.get("lang") == "en"]
    if len(english) == 1:
        return english[0]
    return printings[0] if len(printings) == 1 else None


def _number_key(number: str) -> str:
    """Collector numbers compare padding-insensitively (``09`` is ``9``), mirroring
    catalog._number_key."""
    return str(int(number)) if number.isdigit() else number.casefold()


def _apply(
    store: StudioStore,
    pending: Mapping[tuple[str, str], list[sqlite3.Row]],
    batch: Sequence[tuple[str, str]],
    found: Sequence[Mapping[str, object]],
    missed: Sequence[Mapping[str, str]],
    report: dict[str, int],
) -> None:
    """Write the resolved images of one batch of (set, number) keys into card_printing."""
    by_key: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for card in found:
        card_set = card.get("set")
        card_number = card.get("collector_number")
        if isinstance(card_set, str) and isinstance(card_number, str):
            by_key.setdefault((card_set.lower(), _number_key(card_number)), []).append(card)
    missed_keys = {
        (str(miss.get("set", "")).lower(), _number_key(str(miss.get("collector_number", ""))))
        for miss in missed
    }
    updates: list[tuple[object, ...]] = []
    for key in batch:
        printings = by_key.get((key[0], _number_key(key[1])), [])
        for row in pending[key]:
            lang = row["lang"]
            chosen = _pick(printings, str(lang) if lang is not None else None)
            if chosen is None:
                if (key[0], _number_key(key[1])) in missed_keys or not printings:
                    report["not_found"] += 1
                else:
                    report["ambiguous"] += 1
                continue
            front, back = _images(chosen)
            scryfall_id = chosen.get("id")
            updates.append(
                (
                    str(scryfall_id) if isinstance(scryfall_id, str) else None,
                    front,
                    back,
                    BASIS_EXACT,
                    str(row["card_id"]),
                )
            )
            report["resolved"] += 1
    with store.connection as db:
        db.executemany(
            "UPDATE card_printing SET scryfall_id = ?, image_front = ?, image_back = ?, "
            "basis = ? WHERE card_id = ?",
            updates,
        )


def _bulk_found(
    bulk_path: str | Path, keys: Sequence[tuple[str, str]]
) -> tuple[list[Mapping[str, object]], list[Mapping[str, str]], int]:
    """Stream the local default-cards bulk source once and keep only the wanted
    printings. Returns them, the wanted keys the file does not contain, and the number
    of files read. Nothing is requested per card; the file is the public bulk download."""
    wanted = {(set_code, _number_key(number)) for set_code, number in keys}
    files = catalog._source_files(Path(bulk_path))
    found: list[Mapping[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for file_path in files:
        for card in catalog._objects(file_path):
            card_set = card.get("set")
            card_number = card.get("collector_number")
            if not isinstance(card_set, str) or not isinstance(card_number, str):
                continue
            key = (card_set.lower(), _number_key(card_number))
            if key in wanted:
                found.append(card)
                seen.add(key)
    missed: list[Mapping[str, str]] = [
        {"set": set_code, "collector_number": number}
        for set_code, number in keys
        if (set_code, _number_key(number)) not in seen
    ]
    return found, missed, len(files)


def resolve_printing_images(
    store: StudioStore,
    *,
    bulk_path: str | Path | None = None,
    lookup: Lookup | None = None,
) -> dict[str, int]:
    """Resolve the images of every exact-candidate printing that has none yet.

    The printings are matched locally: against ``bulk_path`` (a Scryfall default-cards
    bulk file or a folder of its parts) or against an injected ``lookup`` (tests). A
    printing the source does not know, or whose language variant stays ambiguous, is
    counted and keeps ``basis`` NULL — never filled with a guessed printing."""
    db = store.connection
    rows = db.execute(
        "SELECT card_id, set_code, collector_number, lang FROM card_printing "
        "WHERE ref_status = ? AND image_front IS NULL AND set_code IS NOT NULL "
        "AND collector_number IS NOT NULL ORDER BY card_id",
        (EXACT_CANDIDATE,),
    ).fetchall()
    pending: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        key = (str(row["set_code"]), str(row["collector_number"]))
        pending.setdefault(key, []).append(row)
    keys = sorted(pending)
    report = {
        "candidates": len(rows),
        "identifiers": len(keys),
        "batches": 0,
        "resolved": 0,
        "not_found": 0,
        "ambiguous": 0,
    }
    if not keys:
        return report
    if lookup is not None:
        for start in range(0, len(keys), _BATCH):
            batch = keys[start : start + _BATCH]
            identifiers: list[Mapping[str, str]] = [
                {"set": set_code, "collector_number": number} for set_code, number in batch
            ]
            found, missed = lookup(identifiers)
            report["batches"] += 1
            _apply(store, pending, batch, found, missed, report)
        return report
    if bulk_path is None:
        raise ValueError(
            "no printing source: pass the Scryfall default-cards bulk file (or a folder "
            "of its parts) — the owned printings are matched locally against it"
        )
    found, missed, files_read = _bulk_found(bulk_path, keys)
    report["batches"] = files_read
    _apply(store, pending, keys, found, missed, report)
    return report


__all__ = [
    "BASIS_EXACT",
    "EXACT_CANDIDATE",
    "UNRESOLVED",
    "Lookup",
    "parse_printing_ref",
    "resolve_printing_images",
]
