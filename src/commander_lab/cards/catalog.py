from __future__ import annotations

import difflib
import json
from collections.abc import Iterable
from pathlib import Path

from commander_lab.models import CardIdentity

from .normalize import oracle_lookup_key


class UnknownCardError(LookupError):
    def __init__(self, requested_name: str, suggestions: list[str] | None = None) -> None:
        self.requested_name = requested_name
        self.suggestions = suggestions or []
        suffix = f"; suggestions: {', '.join(self.suggestions)}" if self.suggestions else ""
        super().__init__(f"unknown Oracle card name: {requested_name!r}{suffix}")


class AmbiguousCardNameError(LookupError):
    pass


class CardCatalog:
    """In-memory Oracle-name index with aliases and deterministic resolution."""

    def __init__(self, cards: Iterable[CardIdentity]) -> None:
        self._cards_by_name: dict[str, CardIdentity] = {}
        self._alias_to_name: dict[str, str] = {}
        for card in cards:
            self.add(card)

    def add(self, card: CardIdentity) -> None:
        canonical_key = oracle_lookup_key(card.oracle_name)
        existing = self._cards_by_name.get(canonical_key)
        if existing is not None and existing != card:
            raise ValueError(f"duplicate conflicting card identity: {card.oracle_name}")
        self._cards_by_name[canonical_key] = card
        for alias in (card.oracle_name, *card.aliases):
            key = oracle_lookup_key(alias)
            previous = self._alias_to_name.get(key)
            if previous is not None and previous != canonical_key:
                raise AmbiguousCardNameError(f"alias {alias!r} maps to multiple cards")
            self._alias_to_name[key] = canonical_key

    @classmethod
    def from_json(cls, path: str | Path) -> CardCatalog:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "cards" in payload:
            payload = payload["cards"]
        cards = [CardIdentity.model_validate(item) for item in payload]
        return cls(cards)

    def to_json(self, path: str | Path) -> None:
        cards = sorted(self._cards_by_name.values(), key=lambda card: card.oracle_name.casefold())
        payload = {"cards": [card.model_dump(mode="json") for card in cards]}
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def resolve(self, name: str) -> CardIdentity:
        key = oracle_lookup_key(name)
        canonical_key = self._alias_to_name.get(key)
        if canonical_key is None:
            choices = [card.oracle_name for card in self._cards_by_name.values()]
            suggestions = difflib.get_close_matches(name, choices, n=5, cutoff=0.65)
            raise UnknownCardError(name, suggestions)
        return self._cards_by_name[canonical_key]

    def normalize_name(self, name: str) -> str:
        return self.resolve(name).oracle_name

    def __contains__(self, name: str) -> bool:
        try:
            self.resolve(name)
        except UnknownCardError:
            return False
        return True

    def __len__(self) -> int:
        return len(self._cards_by_name)

    @property
    def cards(self) -> tuple[CardIdentity, ...]:
        return tuple(
            sorted(self._cards_by_name.values(), key=lambda card: card.oracle_name.casefold())
        )
