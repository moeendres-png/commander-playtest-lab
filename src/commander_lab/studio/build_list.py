"""Build list by storage location (#1404): the cards of a deck grouped by where they lie.

Facts only. The locations come from the inventory workbook's lot sheet (``card_location``,
see ``allocation``); nothing is priced, rated or simulated, marks are not read. A card's needed
copies are placed on its known locations, largest known stock first (name as tie-break); the
copies the known locations do not cover stay "Standort unbekannt: k von n". A location name
"Unbekannt / nicht direkt belegt" is no box: it counts as unknown. Copies bound by another
saved deck are a note, never a lock.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import NotRequired, TypedDict, cast

from . import allocation
from .store import StudioStore

SCHEMA = "studio-build-list-1"
UNKNOWN_LOCATION_NAME = "Unbekannt / nicht direkt belegt"
UNKNOWN_GROUP_NAME = "Standort unbekannt"
ORIGIN = (
    "Standorte aus der Sammlungsdatei (Tabellen 02_PHYSICAL_LOTS und 03_LOCATIONS, je Karte "
    "und Standort summiert; „mindestens“, wenn ein Posten nur eine Untergrenze ist)."
)


class BuildListError(ValueError):
    """The list cannot be turned into a build list."""


Location = dict[str, object]  # one ``allocation`` location row


class Slice(TypedDict):
    location_id: str
    name: str
    quantity: int
    stock: int
    exact: bool
    unknown_lots: int


class Item(TypedDict):
    card_id: str
    name: str
    quantity: int
    needed: int
    status: str
    note: str | None
    exact: NotRequired[bool]
    unknown_lots: NotRequired[int]


class Basic(TypedDict):
    card_id: str
    name: str
    quantity: int


class Group(TypedDict):
    location_id: str | None
    name: str
    cards: list[Item]
    count: int


def _int(value: object) -> int:
    return int(str(value))


def _is_unknown(location: Location) -> bool:
    return (
        str(location["name"]) == UNKNOWN_LOCATION_NAME
        or str(location["location_id"]) == "location:unknown"
        or location.get("type") == "unknown"
    )


def _place(needed: int, known: Sequence[Location]) -> tuple[list[Slice], int, str]:
    """Place ``needed`` copies on the known locations; returns slices, rest and status."""
    slices: list[Slice] = []
    rest = needed
    ordered = sorted(known, key=lambda item: (-_int(item["quantity"]), str(item["name"])))
    for location in ordered:
        take = min(rest, _int(location["quantity"]))
        if take <= 0:
            continue
        rest -= take
        slices.append(
            {
                "location_id": str(location["location_id"]),
                "name": str(location["name"]),
                "quantity": take,
                "stock": _int(location["quantity"]),
                "exact": bool(location["exact"]) and not location["unknown_lots"],
                "unknown_lots": _int(location["unknown_lots"]),
            }
        )
    if not slices:
        status = "unknown"
    elif rest:
        status = "partly_unknown"
    elif all(item["exact"] for item in slices):
        status = "exact"
    else:
        status = "lower_bound"
    return slices, rest, status


def _bound_note(entry: dict[str, object] | None, needed: int, own_deck: str | None) -> str | None:
    if entry is None or entry["available"] is None:
        return None
    decks = cast("list[dict[str, object]]", entry["decks"])
    others = [item for item in decks if str(item["deck_id"]) != own_deck]
    bound = sum(_int(item["quantity"]) for item in others)
    if not bound or _int(entry["available"]) - bound >= needed:
        return None
    names = ", ".join(sorted({str(item["deck_name"]) for item in others}))
    return f"in {names} gebunden ({bound})"


def build_list(
    store: StudioStore,
    rows: Sequence[sqlite3.Row],
    *,
    expected_total: int,
    deck_id: str | None = None,
) -> dict[str, object]:
    """Group the rows (``decks.list_rows``) by location; ``expected_total`` is the list size."""
    if not rows:
        raise BuildListError("empty list")
    cards = cast("dict[str, dict[str, object]]", allocation.allocation(store)["cards"])
    commander: list[dict[str, object]] = []
    basics: list[Basic] = []
    groups: dict[str, Group] = {}
    unknown_cards: list[Item] = []
    status_counts = {"exact": 0, "lower_bound": 0, "partly_unknown": 0, "unknown": 0}
    for row in rows:
        card_id = str(row["card_id"])
        needed = int(row["quantity"])
        name = str(row["oracle_name"])
        entry = cards.get(card_id)
        located = [
            item
            for item in cast("list[Location]", (entry or {}).get("locations", []))
            if not _is_unknown(item)
        ]
        slices, rest, status = _place(needed, located)
        item: Item = {
            "card_id": card_id,
            "name": name,
            "quantity": needed,
            "needed": needed,
            "status": status,
            "note": _bound_note(entry, needed, deck_id),
        }
        if row["zone"] != "commander" and row["is_basic_land"]:
            basics.append({"card_id": card_id, "name": name, "quantity": needed})
            continue
        if row["zone"] == "commander":
            commander.append({**item, "placements": slices, "unknown": rest})
            continue
        status_counts[status] += 1
        for part in slices:
            group = groups.setdefault(
                str(part["location_id"]),
                {
                    "location_id": part["location_id"],
                    "name": part["name"],
                    "cards": [],
                    "count": 0,
                },
            )
            group["cards"].append(
                {
                    **item,
                    "quantity": part["quantity"],
                    "exact": part["exact"],
                    "unknown_lots": part["unknown_lots"],
                }
            )
        if rest:
            unknown_cards.append({**item, "quantity": rest})
    located_groups = sorted(
        groups.values(),
        key=lambda group: (str(group["name"]).casefold(), str(group["location_id"])),
    )
    if unknown_cards:
        located_groups.append(
            {
                "location_id": None,
                "name": UNKNOWN_GROUP_NAME,
                "cards": unknown_cards,
                "count": 0,
            }
        )
    for group in located_groups:
        group["cards"].sort(key=lambda item: str(item["name"]).casefold())
        group["count"] = sum(item["quantity"] for item in group["cards"])
    commander.sort(key=lambda item: str(item["name"]).casefold())
    basics.sort(key=lambda item: str(item["name"]).casefold())
    counted = (
        sum(group["count"] for group in located_groups)
        + sum(_int(item["quantity"]) for item in commander)
        + sum(_int(item["quantity"]) for item in basics)
    )
    error = None
    if counted != expected_total:
        error = (
            f"Summenprobe fehlgeschlagen: {counted} Karten in der Bauliste, "
            f"{expected_total} in der Liste."
        )
    return {
        "schema": SCHEMA,
        "origin": ORIGIN,
        "commander": commander,
        "basic_lands": {"cards": basics, "count": sum(_int(i["quantity"]) for i in basics)},
        "groups": located_groups,
        "unknown_group": UNKNOWN_GROUP_NAME,
        "totals": {
            "list_size": expected_total,
            "counted": counted,
            "commander": sum(_int(item["quantity"]) for item in commander),
            "basic_lands": sum(_int(item["quantity"]) for item in basics),
            "in_groups": sum(group["count"] for group in located_groups),
        },
        "locations_known": bool(any(group["location_id"] is not None for group in located_groups)),
        "card_status": {**status_counts, "of": sum(status_counts.values())},
        "error": error,
    }
