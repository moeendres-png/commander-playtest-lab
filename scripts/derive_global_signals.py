"""Derive ``card_global_signals.csv`` from saved EDHREC card-page JSON (#1386).

The capture route (one plain GET per pool card, public data only, no deck
or collection data leaves this machine):

    GET https://json.edhrec.com/pages/cards/<slug>.json

This is the route the stored file itself documents: its ``source_file``
column names one ``<slug>.json`` per card, and the directory README dates
the original capture to the EDHREC card pages. The route was re-verified
against the stored file in #1377 (probe of one card: same fields, plausible
drift) and again for this renewal (four probes, including a split card and
the one denominator-0 card).

This script never touches the network. It reads the raw responses saved by
that capture plus a ``provenance.json`` next to them (per slug: ``url``,
``fetched_utc``, ``http_status``, ``bytes``, ``sha256``), verifies every
SHA-256 before use (fail closed on mismatch), and writes the renewed CSV
in the exact layout ``commander_lab.studio.signals`` imports. The pool and
the row order come from the previous ``card_global_signals.csv`` (``--pool``):
the renewal replaces the values of the same 1,655 cards, it does not
redefine the pool.

Field mapping (page JSON ``container.json_dict.card`` -> CSV):
``name`` -> card_name (verified equal to the pool row), ``sanitized`` ->
card_slug (verified equal), ``num_decks`` and ``potential_decks``
unchanged, ``salt`` and ``rarity`` unchanged (empty when the page does not
publish them, never 0). ``inclusion_share`` is derived locally as
``num_decks / potential_decks`` and stays empty when the denominator is 0
(unknown, never 0 — the importer's own rule). ``fetch_status`` is
``AVAILABLE`` for every row: a row is only written from a verified HTTP 200
capture whose card object matches the pool row. ``source_file`` is
``<slug>.json``.

The page also carries ``prices``. They are never read and never written:
no price data in the tool (Owner decision; the stored file was cleansed of
its price columns on 2026-11-14, #1309 P10).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import TypedDict

COLUMNS = [
    "card_name",
    "card_slug",
    "fetch_status",
    "num_decks",
    "potential_decks",
    "inclusion_share",
    "salt",
    "rarity",
    "source_file",
]


class PageProvenance(TypedDict):
    url: str
    fetched_utc: str
    http_status: int
    bytes: int
    sha256: str


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("expected a JSON string")
    return value


def _number_text(value: object) -> str:
    """CSV text of a published number; empty when the page does not publish it."""
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return ""


def _count(value: object, field: str, slug: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{slug}: {field} is not an integer count: {value!r}")
    return value


def _load_page(raw_dir: Path, slug: str, provenance: PageProvenance) -> dict[str, object]:
    path = raw_dir / f"{slug}.json"
    blob = path.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != provenance["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {path}: {digest} != {provenance['sha256']}")
    if len(blob) != provenance["bytes"]:
        raise ValueError(f"byte count mismatch for {path}")
    if provenance["http_status"] != 200:
        raise ValueError(f"provenance for {slug} is not an HTTP 200 capture")
    page = _as_dict(json.loads(blob))
    container = _as_dict(page.get("container"))
    json_dict = _as_dict(container.get("json_dict"))
    return _as_dict(json_dict.get("card"))


def _derive_row(pool_row: dict[str, str], card: dict[str, object]) -> dict[str, str]:
    slug = pool_row["card_slug"]
    name = _as_str(card.get("name"))
    if name != pool_row["card_name"]:
        raise ValueError(f"{slug}: page name {name!r} != pool name {pool_row['card_name']!r}")
    sanitized = _as_str(card.get("sanitized"))
    if sanitized != slug:
        raise ValueError(f"{slug}: page sanitized {sanitized!r} != pool slug")
    num_decks = _count(card.get("num_decks"), "num_decks", slug)
    potential_decks = _count(card.get("potential_decks"), "potential_decks", slug)
    if num_decks < 0 or potential_decks < 0:
        raise ValueError(f"{slug}: negative deck count {num_decks}/{potential_decks}")
    if num_decks > potential_decks:
        raise ValueError(f"{slug}: num_decks {num_decks} above potential_decks {potential_decks}")
    share = repr(num_decks / potential_decks) if potential_decks > 0 else ""
    return {
        "card_name": pool_row["card_name"],
        "card_slug": slug,
        "fetch_status": "AVAILABLE",
        "num_decks": str(num_decks),
        "potential_decks": str(potential_decks),
        "inclusion_share": share,
        "salt": _number_text(card.get("salt")),
        "rarity": _as_str(card.get("rarity")) if card.get("rarity") is not None else "",
        "source_file": f"{slug}.json",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    provenance = {
        key: PageProvenance(**value)  # type: ignore[typeddict-item]
        for key, value in _as_dict(
            json.loads((args.raw_dir / "provenance.json").read_text(encoding="utf-8"))
        ).items()
    }
    with args.pool.open(encoding="utf-8", newline="") as handle:
        pool_rows = list(csv.DictReader(handle))
    rows: list[dict[str, str]] = []
    for pool_row in pool_rows:
        slug = pool_row["card_slug"]
        if slug not in provenance:
            raise ValueError(f"{slug}: no provenance entry — capture incomplete")
        card = _load_page(args.raw_dir, slug, provenance[slug])
        rows.append(_derive_row(pool_row, card))
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    empty_share = sum(1 for row in rows if not row["inclusion_share"])
    empty_salt = sum(1 for row in rows if not row["salt"])
    print(
        f"{args.out}: {len(rows)} rows, inclusion_share empty: {empty_share}, "
        f"salt empty: {empty_salt}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
