from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

from commander_lab.models import CommanderConfiguration, Deck, DeckEntry, DeckZone

from .base import CatalogAwareImporter, DeckImportOptions, ImportErrorWithContext

_NAME_COLUMNS = ("oracle_name", "card_name", "card", "name", "karte", "kartenname")
_QUANTITY_COLUMNS = ("quantity", "qty", "count", "amount", "anzahl", "menge")
_ZONE_COLUMNS = ("zone", "section", "board", "bereich", "typ")
_COMMANDER_COLUMNS = ("is_commander", "commander", "kommandeur", "partner")


def _find_column(fieldnames: Iterable[str], aliases: tuple[str, ...]) -> str | None:
    normalized = {field.casefold().strip(): field for field in fieldnames}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "ja", "x"}


def _int_value(value: object, default: int = 1) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return int(value)
    raise ValueError(f"unsupported integer value: {value!r}")


def _zone_from_value(value: object, *, is_commander: bool = False) -> DeckZone:
    if is_commander:
        return DeckZone.COMMANDER
    key = str(value or "main").strip().casefold().replace(" ", "")
    mapping = {
        "commander": DeckZone.COMMANDER,
        "commandzone": DeckZone.COMMANDER,
        "partner": DeckZone.COMMANDER,
        "main": DeckZone.MAIN,
        "mainboard": DeckZone.MAIN,
        "deck": DeckZone.MAIN,
        "library": DeckZone.MAIN,
        "land": DeckZone.MAIN,
        "lands": DeckZone.MAIN,
        "nonland": DeckZone.MAIN,
        "nonlands": DeckZone.MAIN,
        "sideboard": DeckZone.SIDEBOARD,
        "maybeboard": DeckZone.MAYBEBOARD,
    }
    return mapping.get(key, DeckZone.MAIN)


class CsvDeckImporter(CatalogAwareImporter):
    def import_file(self, path: str | Path, options: DeckImportOptions) -> Deck:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(handle, dialect=dialect)
            return self.import_rows(reader, options, source_path=path)

    def import_rows(
        self,
        rows: Iterable[Mapping[str, object]],
        options: DeckImportOptions,
        *,
        source_path: str | Path | None = None,
    ) -> Deck:
        rows = list(rows)
        if not rows:
            raise ImportErrorWithContext("CSV contains no rows", source=source_path)
        fieldnames = list(rows[0].keys())
        name_column = _find_column(fieldnames, _NAME_COLUMNS)
        if name_column is None:
            raise ImportErrorWithContext(
                f"no card-name column found; expected one of {_NAME_COLUMNS}", source=source_path
            )
        quantity_column = _find_column(fieldnames, _QUANTITY_COLUMNS)
        zone_column = _find_column(fieldnames, _ZONE_COLUMNS)
        commander_column = _find_column(fieldnames, _COMMANDER_COLUMNS)

        entries: list[DeckEntry] = []
        explicit_commanders: list[str] = []
        for index, row in enumerate(rows, start=2):
            raw_name = str(row.get(name_column, "") or "").strip()
            if not raw_name:
                continue
            try:
                name = self.normalize_card_name(raw_name)
                quantity = _int_value(row.get(quantity_column), 1) if quantity_column else 1
                is_commander = _truthy(row.get(commander_column)) if commander_column else False
                zone_value = row.get(zone_column) if zone_column is not None else None
                zone = _zone_from_value(zone_value, is_commander=is_commander)
            except Exception as exc:
                raise ImportErrorWithContext(str(exc), source=source_path, row=index) from exc
            entries.append(DeckEntry(oracle_name=name, quantity=quantity, zone=zone))
            if zone == DeckZone.COMMANDER:
                explicit_commanders.append(name)

        option_commanders = tuple(
            self.normalize_card_name(name) for name in (options.commander_names or ())
        )
        commanders = tuple(dict.fromkeys(explicit_commanders)) or option_commanders
        if not commanders:
            raise ImportErrorWithContext("no commander specified", source=source_path)
        if explicit_commanders and option_commanders and set(commanders) != set(option_commanders):
            raise ImportErrorWithContext(
                "commander mismatch between rows and options", source=source_path
            )

        if not explicit_commanders:
            commander_set = set(commanders)
            entries = [
                entry.model_copy(
                    update={
                        "zone": DeckZone.COMMANDER
                        if entry.oracle_name in commander_set
                        else entry.zone
                    }
                )
                for entry in entries
            ]

        uses_partner = (
            options.uses_partner if options.uses_partner is not None else len(commanders) == 2
        )
        parsed_date = date.fromisoformat(options.data_as_of) if options.data_as_of else None
        return Deck(
            deck_id=options.deck_id,
            name=options.name,
            commander=CommanderConfiguration(commanders=commanders, uses_partner=uses_partner),
            cards=entries,
            data_as_of=parsed_date,
            source=self.source_ref(source_path or "rows.csv", source_type="csv"),
        )
