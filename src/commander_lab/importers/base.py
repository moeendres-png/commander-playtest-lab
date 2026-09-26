from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from commander_lab.cards.catalog import CardCatalog
from commander_lab.models import SourceRef


@dataclass(frozen=True, slots=True)
class DeckImportOptions:
    deck_id: str
    name: str
    commander_names: tuple[str, ...] | None = None
    uses_partner: bool | None = None
    data_as_of: str | None = None
    source_name: str | None = None


class ImportErrorWithContext(ValueError):
    def __init__(self, message: str, *, source: str | Path | None = None, row: int | None = None):
        self.source = str(source) if source is not None else None
        self.row = row
        location = ""
        if self.source:
            location += f" in {self.source}"
        if self.row is not None:
            location += f" at row {self.row}"
        super().__init__(message + location)


class CatalogAwareImporter:
    def __init__(self, catalog: CardCatalog) -> None:
        self.catalog = catalog

    def normalize_card_name(self, name: str) -> str:
        return self.catalog.normalize_name(name)

    @staticmethod
    def source_ref(path: str | Path, *, source_type: str) -> SourceRef:
        path_obj = Path(path)
        return SourceRef(
            source_type=source_type,
            source_name=path_obj.name,
            source_path=str(path_obj),
        )
