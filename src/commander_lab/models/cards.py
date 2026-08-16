from __future__ import annotations

from collections import Counter
from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_serializer, field_validator, model_validator

from .common import Color, DataQuality, FrozenModel, MutableModel, SourceRef


class CardLegality(StrEnum):
    LEGAL = "legal"
    NOT_LEGAL = "not_legal"
    RESTRICTED = "restricted"
    BANNED = "banned"
    UNKNOWN = "unknown"


class CardIdentity(FrozenModel):
    oracle_name: str = Field(min_length=1)
    oracle_id: str | None = None
    aliases: tuple[str, ...] = ()
    mana_cost: str | None = None
    mana_value: float | None = Field(default=None, ge=0)
    colors: frozenset[Color] = frozenset()
    color_identity: frozenset[Color] = frozenset()
    type_line: str = "Unknown"
    oracle_text: str | None = None
    keywords: tuple[str, ...] = ()
    can_be_commander: bool = False
    partner_with: tuple[str, ...] = ()
    legalities: dict[str, CardLegality] = Field(default_factory=dict)
    is_basic_land: bool = False
    max_deck_copies: int | None = Field(default=1, ge=1)
    data_quality: DataQuality = DataQuality.UNKNOWN
    provenance: tuple[SourceRef, ...] = ()

    @field_validator("oracle_name")
    @classmethod
    def strip_oracle_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("oracle_name cannot be blank")
        return normalized

    @model_validator(mode="after")
    def basic_land_copy_rule(self) -> CardIdentity:
        if self.is_basic_land and self.max_deck_copies is not None:
            object.__setattr__(self, "max_deck_copies", None)
        return self


class CardCondition(StrEnum):
    MINT = "M"
    NEAR_MINT = "NM"
    EXCELLENT = "EX"
    GOOD = "GD"
    LIGHT_PLAYED = "LP"
    PLAYED = "PL"
    POOR = "PO"
    UNKNOWN = "UNKNOWN"


class PurchaseStatus(StrEnum):
    OWNED = "owned"
    ORDERED = "ordered"
    PLANNED = "planned"
    NOT_OWNED = "not_owned"
    UNKNOWN = "unknown"


class PhysicalCard(FrozenModel):
    copy_id: str = Field(min_length=1)
    oracle_name: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    set_code: str | None = None
    collector_number: str | None = None
    printing_id: str | None = None
    language: str = "en"
    condition: CardCondition = CardCondition.UNKNOWN
    foil: bool = False
    box: str | None = None
    source: str | None = None
    purchase_status: PurchaseStatus = PurchaseStatus.OWNED
    reserved_for: str | None = None
    acquired_on: date | None = None
    notes: str | None = None

    @field_validator("oracle_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return " ".join(value.split())


class Collection(MutableModel):
    collection_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    cards: list[PhysicalCard] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    data_as_of: date | None = None
    snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    notes: str | None = None

    def available_quantities(self, *, include_reserved: bool = True) -> Counter[str]:
        counts: Counter[str] = Counter()
        for card in self.cards:
            if card.purchase_status != PurchaseStatus.OWNED:
                continue
            if not include_reserved and card.reserved_for:
                continue
            counts[card.oracle_name] += card.quantity
        return counts


class DeckZone(StrEnum):
    COMMANDER = "commander"
    MAIN = "main"
    SIDEBOARD = "sideboard"
    MAYBEBOARD = "maybeboard"


class DeckEntry(FrozenModel):
    oracle_name: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    zone: DeckZone = DeckZone.MAIN
    physical_copy_ids: tuple[str, ...] = ()
    notes: str | None = None

    @field_validator("oracle_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return " ".join(value.split())


class CommanderConfiguration(FrozenModel):
    commanders: tuple[str, ...]
    uses_partner: bool = False
    commander_identity_override: frozenset[Color] | None = None

    @field_validator("commanders")
    @classmethod
    def validate_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        stripped = tuple(" ".join(name.split()) for name in value if name.strip())
        if not stripped:
            raise ValueError("at least one commander is required")
        if len(set(stripped)) != len(stripped):
            raise ValueError("commander names must be unique")
        return stripped

    @model_validator(mode="after")
    def validate_partner_count(self) -> CommanderConfiguration:
        count = len(self.commanders)
        if self.uses_partner and count != 2:
            raise ValueError("partner configuration requires exactly two commanders")
        if not self.uses_partner and count != 1:
            raise ValueError("non-partner configuration requires exactly one commander")
        return self


class Deck(MutableModel):
    deck_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    commander: CommanderConfiguration
    cards: list[DeckEntry]
    format: str = "commander"
    data_as_of: date | None = None
    source: SourceRef | None = None
    deck_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    tags: set[str] = Field(default_factory=set)
    notes: str | None = None

    @field_serializer("tags")
    def serialize_tags(self, tags: set[str]) -> list[str]:
        """Keep deck JSON stable across processes with different hash seeds."""
        return sorted(tags)

    @model_validator(mode="after")
    def commanders_match_entries(self) -> Deck:
        commander_entries = {
            entry.oracle_name for entry in self.cards if entry.zone == DeckZone.COMMANDER
        }
        expected = set(self.commander.commanders)
        if commander_entries != expected:
            raise ValueError(
                f"commander entries {sorted(commander_entries)} do not match configuration "
                f"{sorted(expected)}"
            )
        return self

    @property
    def total_cards(self) -> int:
        return sum(entry.quantity for entry in self.cards if entry.zone != DeckZone.MAYBEBOARD)

    @property
    def library_cards(self) -> int:
        return sum(entry.quantity for entry in self.cards if entry.zone == DeckZone.MAIN)

    def quantities(self, *, include_commanders: bool = True) -> Counter[str]:
        counts: Counter[str] = Counter()
        for entry in self.cards:
            if entry.zone in {DeckZone.SIDEBOARD, DeckZone.MAYBEBOARD}:
                continue
            if entry.zone == DeckZone.COMMANDER and not include_commanders:
                continue
            counts[entry.oracle_name] += entry.quantity
        return counts

    def grouped_entries(self) -> list[DeckEntry]:
        grouped: Counter[tuple[str, DeckZone]] = Counter()
        for entry in self.cards:
            grouped[(entry.oracle_name, entry.zone)] += entry.quantity
        return [
            DeckEntry(oracle_name=name, zone=zone, quantity=quantity)
            for (name, zone), quantity in sorted(
                grouped.items(), key=lambda item: (item[0][1], item[0][0])
            )
        ]


PositiveInt = Annotated[int, Field(ge=1)]
