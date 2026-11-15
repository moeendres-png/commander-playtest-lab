"""Combo shells (#1366): deduplicate Commander Spellbook variants onto the
combo they belong to.

The spellbook file (``spellbook_card_links.csv``) counts *variants*: every
concrete way to assemble a combo, so one combo whose flexible slot has 19
printed equivalents inflates a card's count 19-fold (Pitiless Plunderer:
3,282 variants). The bulk export names the combo behind each variant in the
variant's ``of`` field; that combo is the *shell* of this module. Counting
distinct shells instead of variants removes exactly the inflation the
spellbook itself considers identical — same recipe, same produced features,
same colour identity. Shells are not merged any further: two shells that
differ only in one swapped card (Cloudshift vs. Essence Flux) stay two
shells, because the source keeps them apart (different identity or results).

A variant qualifies for a commander when its own colour identity fits the
commander's identity (the identity varies *between the variants of one
shell*, so the test is per variant, never per shell) and every card it uses
is in the commander's legal pool. Generic template slots (``requires``) have
no concrete card: they cannot fail the pool test, but they count towards the
combo's card count, like the importer already counts them for variants.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

# Chulane, Teller of Tales — the one commander this package scopes to (#1363).
CHULANE_IDENTITY = frozenset({"W", "U", "G"})


@dataclass(frozen=True)
class VariantFacts:
    """The shell facts of one spellbook variant, read from the bulk export."""

    shell_id: int
    card_names: tuple[str, ...]
    card_count: int
    identity: frozenset[str]
    with_commander: bool


@dataclass(frozen=True)
class ShellCounts:
    """Distinct qualifying shells of one card, split by shape."""

    shells: int
    two_card: int
    three_plus: int
    with_commander: int
    shell_ids: tuple[int, ...]


def _facts(record: Mapping[str, object]) -> VariantFacts | None:
    """The facts of one bulk variant record; ``None`` without a combo (``of``)."""
    of = record.get("of")
    if not isinstance(of, list) or not of or not isinstance(of[0], Mapping):
        return None
    shell = of[0].get("id")
    if not isinstance(shell, int):
        return None
    uses = record.get("uses")
    requires = record.get("requires")
    uses = uses if isinstance(uses, list) else []
    requires = requires if isinstance(requires, list) else []
    names: list[str] = []
    commander = False
    for entry in uses:
        if not isinstance(entry, Mapping):
            continue
        card = entry.get("card")
        if isinstance(card, Mapping) and isinstance(card.get("name"), str):
            names.append(card["name"])
        if entry.get("mustBeCommander") is True:
            commander = True
    for entry in requires:
        if isinstance(entry, Mapping) and entry.get("mustBeCommander") is True:
            commander = True
    identity = record.get("identity")
    return VariantFacts(
        shell_id=shell,
        card_names=tuple(names),
        card_count=len(uses) + len(requires),
        identity=frozenset(identity) if isinstance(identity, str) else frozenset(),
        with_commander=commander,
    )


def build_variant_index(
    records: Iterable[Mapping[str, object]],
    aliases: Iterable[Mapping[str, object]],
) -> dict[str, VariantFacts]:
    """Variant id → facts, for the bulk export's variants and its alias table.

    The link file is a snapshot: a variant it names may since have been
    renamed, which the export's ``aliases`` map to the current id (a retired
    variant has no successor and resolves to nothing)."""
    index: dict[str, VariantFacts] = {}
    for record in records:
        variant_id = record.get("id")
        facts = _facts(record)
        if isinstance(variant_id, str) and facts is not None:
            index[variant_id] = facts
    for alias in aliases:
        old = alias.get("id")
        successor = alias.get("variant")
        if not isinstance(old, str) or not isinstance(successor, Mapping):
            continue
        new = successor.get("id")
        if isinstance(new, str) and new in index:
            index.setdefault(old, index[new])
    return index


def count_shells(
    variant_ids: Iterable[str],
    index: Mapping[str, VariantFacts],
    pool: Collection[str],
    *,
    identity: frozenset[str] = CHULANE_IDENTITY,
) -> ShellCounts:
    """The distinct shells of one card: a shell counts once, however many of
    the card's variants belong to it, and only through a variant that fits the
    commander's identity with every used card in the pool. The card count of a
    shell is the smallest count among its qualifying variants (the slots of a
    shell are fixed, so its variants agree; the minimum keeps a disagreeing
    snapshot deterministic)."""
    by_shell: dict[int, VariantFacts] = {}
    for variant_id in variant_ids:
        facts = index.get(variant_id.strip())
        if facts is None:
            continue
        if not facts.identity <= identity:
            continue
        if any(name not in pool for name in facts.card_names):
            continue
        current = by_shell.get(facts.shell_id)
        if current is None or facts.card_count < current.card_count:
            by_shell[facts.shell_id] = VariantFacts(
                shell_id=facts.shell_id,
                card_names=facts.card_names,
                card_count=facts.card_count,
                identity=facts.identity,
                with_commander=(
                    facts.with_commander or (current.with_commander if current else False)
                ),
            )
    shells = tuple(sorted(by_shell))
    return ShellCounts(
        shells=len(shells),
        two_card=sum(1 for facts in by_shell.values() if facts.card_count == 2),
        three_plus=sum(1 for facts in by_shell.values() if facts.card_count >= 3),
        with_commander=sum(1 for facts in by_shell.values() if facts.with_commander),
        shell_ids=shells,
    )
