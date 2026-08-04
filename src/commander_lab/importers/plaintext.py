from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Iterable

from commander_lab.cards.catalog import CardCatalog
from commander_lab.cards.normalize import split_quantity_and_name
from commander_lab.models import CommanderConfiguration, Deck, DeckEntry, DeckZone

from .base import CatalogAwareImporter, DeckImportOptions, ImportErrorWithContext

_SECTION_RE = re.compile(r"^\s*(?:#|\[)?\s*([^\]]+?)\s*\]?\s*$")
_SECTION_MAP = {
    "commander": DeckZone.COMMANDER,
    "commanders": DeckZone.COMMANDER,
    "partner": DeckZone.COMMANDER,
    "partners": DeckZone.COMMANDER,
    "main": DeckZone.MAIN,
    "mainboard": DeckZone.MAIN,
    "deck": DeckZone.MAIN,
    "library": DeckZone.MAIN,
    "nonlands": DeckZone.MAIN,
    "lands": DeckZone.MAIN,
    "sideboard": DeckZone.SIDEBOARD,
    "maybeboard": DeckZone.MAYBEBOARD,
}


class PlaintextDeckImporter(CatalogAwareImporter):
    def import_file(self, path: str | Path, options: DeckImportOptions) -> Deck:
        text = Path(path).read_text(encoding="utf-8-sig")
        return self.import_text(text, options, source_path=path)

    def import_text(
        self,
        text: str,
        options: DeckImportOptions,
        *,
        source_path: str | Path | None = None,
    ) -> Deck:
        current_zone = DeckZone.MAIN
        entries: list[DeckEntry] = []
        explicit_commanders: list[str] = []

        for row_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("//") or line.startswith(";"):
                continue
            if line.startswith("```"):
                continue

            heading = self._parse_heading(line)
            if heading is not None:
                current_zone = heading
                continue

            if line.startswith("#"):
                continue

            try:
                quantity, raw_name = split_quantity_and_name(line)
                canonical_name = self.normalize_card_name(raw_name)
            except Exception as exc:
                raise ImportErrorWithContext(
                    str(exc), source=source_path, row=row_number
                ) from exc
            entries.append(
                DeckEntry(
                    oracle_name=canonical_name,
                    quantity=quantity,
                    zone=current_zone,
                )
            )
            if current_zone == DeckZone.COMMANDER:
                explicit_commanders.extend([canonical_name] * quantity)

        commander_names = self._resolve_commanders(options, explicit_commanders)
        uses_partner = options.uses_partner if options.uses_partner is not None else len(commander_names) == 2
        commander_set = set(commander_names)

        if not explicit_commanders:
            adjusted: list[DeckEntry] = []
            for entry in entries:
                zone = DeckZone.COMMANDER if entry.oracle_name in commander_set else entry.zone
                adjusted.append(entry.model_copy(update={"zone": zone}))
            entries = adjusted

        parsed_date = date.fromisoformat(options.data_as_of) if options.data_as_of else None
        return Deck(
            deck_id=options.deck_id,
            name=options.name,
            commander=CommanderConfiguration(
                commanders=tuple(commander_names),
                uses_partner=uses_partner,
            ),
            cards=entries,
            data_as_of=parsed_date,
            source=self.source_ref(source_path or options.source_name or "inline.txt", source_type="plaintext"),
        )

    @staticmethod
    def _parse_heading(line: str) -> DeckZone | None:
        candidate = line
        if line.startswith("#"):
            candidate = line.lstrip("#").strip()
        elif line.startswith("[") and line.endswith("]"):
            candidate = line[1:-1].strip()
        elif not line.endswith(":"):
            return None
        else:
            candidate = line[:-1].strip()
        key = candidate.casefold().replace(" ", "")
        return _SECTION_MAP.get(key)

    def _resolve_commanders(
        self, options: DeckImportOptions, explicit_commanders: Iterable[str]
    ) -> tuple[str, ...]:
        from_file = tuple(dict.fromkeys(explicit_commanders))
        from_options = (
            tuple(self.normalize_card_name(name) for name in options.commander_names)
            if options.commander_names
            else ()
        )
        if from_file and from_options and set(from_file) != set(from_options):
            raise ImportErrorWithContext(
                f"commander mismatch: file={from_file}, options={from_options}"
            )
        commanders = from_file or from_options
        if not commanders:
            raise ImportErrorWithContext("no commander specified")
        return commanders
