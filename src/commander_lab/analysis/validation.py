from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Iterable

from pydantic import Field

from commander_lab.cards.catalog import CardCatalog, UnknownCardError
from commander_lab.models import (
    CardLegality,
    Collection,
    Color,
    Deck,
    DeckZone,
    MutableModel,
)


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(MutableModel):
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    card_name: str | None = None
    context: dict[str, object] = Field(default_factory=dict)


class ValidationReport(MutableModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    metrics: dict[str, object] = Field(default_factory=dict)

    @classmethod
    def from_issues(
        cls, issues: list[ValidationIssue], *, metrics: dict[str, object] | None = None
    ) -> "ValidationReport":
        valid = not any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        return cls(valid=valid, issues=issues, metrics=metrics or {})


class DeckValidator:
    def __init__(
        self,
        catalog: CardCatalog,
        *,
        expected_size: int = 100,
        strict_unknown_cards: bool = True,
        require_commander_legality: bool = True,
    ) -> None:
        self.catalog = catalog
        self.expected_size = expected_size
        self.strict_unknown_cards = strict_unknown_cards
        self.require_commander_legality = require_commander_legality

    def validate(self, deck: Deck) -> ValidationReport:
        issues: list[ValidationIssue] = []
        total = deck.total_cards
        if total != self.expected_size:
            issues.append(
                ValidationIssue(
                    code="deck_size",
                    message=f"Commander deck has {total} cards; expected {self.expected_size}",
                    context={"actual": total, "expected": self.expected_size},
                )
            )

        expected_library = self.expected_size - len(deck.commander.commanders)
        if deck.library_cards != expected_library:
            issues.append(
                ValidationIssue(
                    code="library_size",
                    message=(
                        f"library has {deck.library_cards} cards; expected {expected_library} "
                        f"for {len(deck.commander.commanders)} commander(s)"
                    ),
                )
            )

        resolved = {}
        for name in deck.quantities():
            try:
                resolved[name] = self.catalog.resolve(name)
            except UnknownCardError as exc:
                severity = (
                    ValidationSeverity.ERROR if self.strict_unknown_cards else ValidationSeverity.WARNING
                )
                issues.append(
                    ValidationIssue(
                        code="unknown_card",
                        message=str(exc),
                        severity=severity,
                        card_name=name,
                    )
                )

        commander_identity: set[Color] = set()
        commander_cards = []
        for commander_name in deck.commander.commanders:
            card = resolved.get(commander_name)
            if card is None:
                continue
            commander_cards.append(card)
            commander_identity.update(card.color_identity)
            if not card.can_be_commander:
                issues.append(
                    ValidationIssue(
                        code="commander_eligibility",
                        message=f"{commander_name} is not marked as eligible to be a commander",
                        card_name=commander_name,
                    )
                )
            if self.require_commander_legality:
                legality = card.legalities.get("commander", CardLegality.UNKNOWN)
                if legality != CardLegality.LEGAL:
                    issues.append(
                        ValidationIssue(
                            code="commander_legality",
                            message=f"{commander_name} is not marked Commander-legal ({legality})",
                            card_name=commander_name,
                        )
                    )

        if deck.commander.uses_partner and len(commander_cards) == 2:
            first, second = commander_cards
            first_keywords = {keyword.casefold() for keyword in first.keywords}
            second_keywords = {keyword.casefold() for keyword in second.keywords}
            generic_partner = "partner" in first_keywords and "partner" in second_keywords
            explicit_pair = (
                second.oracle_name in first.partner_with
                and first.oracle_name in second.partner_with
            )
            if not (generic_partner or explicit_pair):
                issues.append(
                    ValidationIssue(
                        code="partner_pairing",
                        message=(
                            f"{first.oracle_name} and {second.oracle_name} are not marked as a "
                            "legal partner pair"
                        ),
                    )
                )

        if deck.commander.commander_identity_override is not None:
            commander_identity = set(deck.commander.commander_identity_override)

        for name, quantity in deck.quantities().items():
            card = resolved.get(name)
            if card is None:
                continue
            illegal_colors = set(card.color_identity) - commander_identity
            if illegal_colors:
                issues.append(
                    ValidationIssue(
                        code="color_identity",
                        message=(
                            f"{name} has color identity {sorted(c.value for c in card.color_identity)} "
                            f"outside commander identity {sorted(c.value for c in commander_identity)}"
                        ),
                        card_name=name,
                        context={"illegal_colors": sorted(color.value for color in illegal_colors)},
                    )
                )
            legality = card.legalities.get("commander", CardLegality.UNKNOWN)
            if self.require_commander_legality and legality != CardLegality.LEGAL:
                issues.append(
                    ValidationIssue(
                        code="card_legality",
                        message=f"{name} is not marked Commander-legal ({legality})",
                        card_name=name,
                    )
                )
            if card.max_deck_copies is not None and quantity > card.max_deck_copies:
                issues.append(
                    ValidationIssue(
                        code="singleton",
                        message=(
                            f"{name} appears {quantity} times; maximum is {card.max_deck_copies}"
                        ),
                        card_name=name,
                    )
                )

        commander_entries = [
            entry for entry in deck.cards if entry.zone == DeckZone.COMMANDER
        ]
        if any(entry.quantity != 1 for entry in commander_entries):
            issues.append(
                ValidationIssue(
                    code="commander_quantity",
                    message="each commander must appear exactly once in the command zone",
                )
            )

        metrics = {
            "total_cards": total,
            "library_cards": deck.library_cards,
            "unique_oracle_names": len(deck.quantities()),
            "commander_count": len(deck.commander.commanders),
            "commander_identity": sorted(color.value for color in commander_identity),
        }
        return ValidationReport.from_issues(issues, metrics=metrics)


def validate_collection_quantities(
    collection: Collection,
    decks: Iterable[Deck],
    *,
    include_reserved: bool = True,
) -> ValidationReport:
    available = collection.available_quantities(include_reserved=include_reserved)
    required: Counter[str] = Counter()
    for deck in decks:
        required.update(deck.quantities())

    issues: list[ValidationIssue] = []
    for name, quantity in sorted(required.items()):
        owned = available.get(name, 0)
        if quantity > owned:
            issues.append(
                ValidationIssue(
                    code="physical_quantity",
                    message=f"{name}: requires {quantity}, only {owned} owned copies available",
                    card_name=name,
                    context={"required": quantity, "available": owned},
                )
            )
    return ValidationReport.from_issues(
        issues,
        metrics={
            "required_unique_cards": len(required),
            "available_unique_cards": len(available),
            "required_total_cards": sum(required.values()),
            "available_total_cards": sum(available.values()),
        },
    )
