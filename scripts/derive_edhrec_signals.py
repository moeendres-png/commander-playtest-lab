"""Derive Studio signal CSVs from saved EDHREC commander-page JSON (#1377).

The capture route (one plain GET per page, public data only, no deck or
collection data leaves this machine):

    GET https://json.edhrec.com/pages/commanders/<slug>.json
    GET https://json.edhrec.com/pages/commanders/<slug>/<variant>.json
        for <variant> in core | upgraded | optimized | cedh

This script never touches the network. It reads the raw responses saved by
that capture plus a ``provenance.json`` next to them (per page: ``url``,
``fetched_utc``, ``http_status``, ``bytes``, ``sha256``), verifies every
SHA-256 before use (fail closed on mismatch), and writes a dated snapshot
folder in the exact file layout ``commander_lab.studio.signals`` imports:

    commander_card_signals.csv
    commander_bracket_signals_<variant>.csv   (one per variant)
    README.md                                  (provenance + counts)

Field mapping (page JSON ``container.json_dict.cardlists[]`` -> CSV):
``header``/``tag`` -> list_header/list_tag; per cardview: ``name`` ->
card_name, ``sanitized`` -> card_slug, ``id`` -> source_card_id, and
``synergy``, ``lift``, ``num_decks``, ``potential_decks``, ``trend_zscore``
unchanged. Rows keep page order. A field the page does not publish becomes
an empty cell (unknown, never 0) and is counted in the README. Variant ->
bracket number: core=2, upgraded=3, optimized=4, cedh=5 (as in the
2026-11-11/12 snapshot files under data/research/deckbuilder_1655).

With ``--compare-dir`` (a folder holding the previous snapshot files of the
same layout), the README also reports, per file, the distinct-card counts
before/after and their overlap.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import TypedDict

VARIANTS: tuple[tuple[str, str], ...] = (
    ("core", "2"),
    ("upgraded", "3"),
    ("optimized", "4"),
    ("cedh", "5"),
)

COMMANDER_COLUMNS = [
    "commander_name",
    "commander_slug",
    "list_header",
    "list_tag",
    "card_name",
    "card_slug",
    "source_card_id",
    "synergy",
    "lift",
    "num_decks",
    "potential_decks",
    "trend_zscore",
    "source_file",
]
BRACKET_COLUMNS = [
    "commander_name",
    "commander_slug",
    "bracket",
    "variant",
    "list_header",
    "list_tag",
    "card_name",
    "card_slug",
    "source_card_id",
    "synergy",
    "lift",
    "num_decks",
    "potential_decks",
    "trend_zscore",
    "source_file",
]
CARDVIEW_FIELDS = ("synergy", "lift", "num_decks", "potential_decks", "trend_zscore")


class PageProvenance(TypedDict):
    url: str
    fetched_utc: str
    http_status: int
    bytes: int
    sha256: str


class FileResult(TypedDict):
    filename: str
    provenance_key: str
    rows: int
    distinct_cards: int
    missing_fields: dict[str, int]


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _as_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("expected a JSON array")
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


def _load_page(raw_dir: Path, key: str, provenance: PageProvenance) -> dict[str, object]:
    path = raw_dir / f"{key}.json"
    blob = path.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != provenance["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {path}: {digest} != {provenance['sha256']}")
    if len(blob) != provenance["bytes"]:
        raise ValueError(f"byte count mismatch for {path}")
    if provenance["http_status"] != 200:
        raise ValueError(f"provenance for {key} is not an HTTP 200 capture")
    return _as_dict(json.loads(blob))


def _cardlists(page: dict[str, object]) -> list[dict[str, object]]:
    container = _as_dict(page.get("container"))
    json_dict = _as_dict(container.get("json_dict"))
    return [_as_dict(item) for item in _as_list(json_dict.get("cardlists"))]


def _derive_rows(
    page: dict[str, object],
    *,
    commander_name: str,
    commander_slug: str,
    source_file: str,
    bracket: str | None,
    variant: str | None,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    rows: list[dict[str, str]] = []
    missing: dict[str, int] = {}
    for cardlist in _cardlists(page):
        header = _as_str(cardlist.get("header"))
        tag = _as_str(cardlist.get("tag"))
        for view in _as_list(cardlist.get("cardviews")):
            cardview = _as_dict(view)
            row: dict[str, str] = {
                "commander_name": commander_name,
                "commander_slug": commander_slug,
                "list_header": header,
                "list_tag": tag,
                "card_name": _as_str(cardview.get("name")),
                "card_slug": _as_str(cardview.get("sanitized")),
                "source_card_id": _as_str(cardview.get("id")),
                "source_file": source_file,
            }
            if bracket is not None and variant is not None:
                row["bracket"] = bracket
                row["variant"] = variant
            for field in CARDVIEW_FIELDS:
                text = _number_text(cardview.get(field))
                if not text:
                    missing[field] = missing.get(field, 0) + 1
                row[field] = text
            rows.append(row)
    return rows, missing


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _previous_cards(folder: Path, base: str, commander_name: str) -> set[str] | None:
    """Distinct cards the previous snapshot stored for this commander, None if absent."""
    parts = sorted(folder.glob(f"{base}_*.csv")) or (
        [folder / f"{base}.csv"] if (folder / f"{base}.csv").is_file() else []
    )
    if not parts:
        return None
    names: set[str] = set()
    for part in parts:
        with part.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["commander_name"] == commander_name:
                    names.add(row["card_name"])
    return names


def _readme(
    *,
    commander_name: str,
    commander_slug: str,
    provenance: dict[str, PageProvenance],
    results: list[FileResult],
    comparisons: dict[str, tuple[int, int, int]],
) -> str:
    lines = [
        f"# EDHREC-Commander-Signale — {commander_name} (Neuabruf 2026-11-15)",
        "",
        "Erstellt durch Muse (Daten-Lane, Issue #1377). Nur objektive Zählwerte",
        "und publizierte Quellwerte mit Provenienz. Keine Decklisten, keine",
        "Sammlungs- oder Besitzdaten. Daten: EDHREC (https://edhrec.com).",
        "",
        "## Provenienz (je Seite genau ein GET, öffentliche JSON-Endpunkte)",
        "",
        "| Seite | URL | Abruf (UTC) | HTTP | Bytes | SHA-256 der Rohantwort |",
        "|---|---|---|---|---|---|",
    ]
    for result in results:
        prov = provenance[result["provenance_key"]]
        lines.append(
            f"| {result['filename']} | {prov['url']} | {prov['fetched_utc']} | "
            f"{prov['http_status']} | {prov['bytes']} | `{prov['sha256']}` |"
        )
    lines += [
        "",
        "Die Rohantworten selbst werden nicht committet (Repo-Konvention, vgl.",
        "C079-Beweisführung); ihre SHA-256 oben macht diesen Snapshot prüfbar.",
        "Ableitung: `scripts/derive_edhrec_signals.py` aus den Rohantworten,",
        "SHA-256 vor der Ableitung verifiziert (fail closed).",
        "",
        "## Inhalt",
        "",
        "| Datei | Zeilen | Distinkte Karten | Leere Felder (nicht publiziert) |",
        "|---|---|---|---|",
    ]
    for result in results:
        missing = (
            ", ".join(
                f"{field}: {count}" for field, count in sorted(result["missing_fields"].items())
            )
            or "—"
        )
        lines.append(
            f"| {result['filename']} | {result['rows']} | {result['distinct_cards']} | {missing} |"
        )
    if comparisons:
        lines += [
            "",
            "## Vergleich zum Snapshot 2026-11-11/12 (deckbuilder_1655, nur Chulane)",
            "",
            "| Datei | Distinkte Karten alt | Distinkte Karten neu | Schnittmenge |",
            "|---|---|---|---|",
        ]
        for result in results:
            base = result["filename"].removesuffix(".csv")
            if base in comparisons:
                old, new, both = comparisons[base]
                lines.append(f"| {result['filename']} | {old} | {new} | {both} |")
    lines += [
        "",
        "Feldabbildung und Zählregeln: siehe Docstring von",
        "`scripts/derive_edhrec_signals.py`. Zeilen in Seitenreihenfolge;",
        "ein Wert, den die Seite nicht publiziert, bleibt leer (unbekannt,",
        "niemals 0). Varianten -> Bracket: core=2, upgraded=3, optimized=4,",
        "cedh=5 (wie in den Snapshot-Dateien 2026-11-11/12).",
        "",
        f"Commander-Slug: `{commander_slug}`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--commander-name", required=True)
    parser.add_argument("--commander-slug", required=True)
    parser.add_argument("--compare-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    provenance = {
        key: PageProvenance(**value)  # type: ignore[typeddict-item]
        for key, value in _as_dict(
            json.loads((args.raw_dir / "provenance.json").read_text(encoding="utf-8"))
        ).items()
    }
    args.out.mkdir(parents=True, exist_ok=True)
    results: list[FileResult] = []
    comparisons: dict[str, tuple[int, int, int]] = {}

    jobs: list[tuple[str, str, list[str], str | None, str | None]] = [
        ("commander", "commander_card_signals.csv", COMMANDER_COLUMNS, None, None)
    ]
    for variant, bracket in VARIANTS:
        jobs.append(
            (
                variant,
                f"commander_bracket_signals_{variant}.csv",
                BRACKET_COLUMNS,
                bracket,
                variant,
            )
        )
    for key, filename, columns, bracket, variant in jobs:
        page = _load_page(args.raw_dir, key, provenance[key])
        source_file = f"{args.commander_slug}.json" if key == "commander" else ""
        if variant is not None:
            source_file = f"{args.commander_slug}_{variant}.json"
        rows, missing = _derive_rows(
            page,
            commander_name=args.commander_name,
            commander_slug=args.commander_slug,
            source_file=source_file,
            bracket=bracket,
            variant=variant,
        )
        _write_csv(args.out / filename, columns, rows)
        distinct = {row["card_name"] for row in rows}
        results.append(
            FileResult(
                filename=filename,
                provenance_key=key,
                rows=len(rows),
                distinct_cards=len(distinct),
                missing_fields=missing,
            )
        )
        if args.compare_dir is not None:
            base = filename.removesuffix(".csv")
            previous = _previous_cards(args.compare_dir, base, args.commander_name)
            if previous is not None:
                comparisons[base] = (len(previous), len(distinct), len(previous & distinct))

    (args.out / "README.md").write_text(
        _readme(
            commander_name=args.commander_name,
            commander_slug=args.commander_slug,
            provenance=provenance,
            results=results,
            comparisons=comparisons,
        ),
        encoding="utf-8",
    )
    for result in results:
        print(f"{result['filename']}: {result['rows']} rows, {result['distinct_cards']} cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
