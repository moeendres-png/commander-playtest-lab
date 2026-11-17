"""Deck Plan: Derives a concise, structured game plan for each deck before a game.

Format and provenance are marked as 'abgeleitet, nicht gemessen'.
Derives how the deck operates, how it wins, which cards are engines, and which cards are answers,
using existing deck guides (data/deck_guides/guides/*.json) and repository card roles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

from commander_lab.agents.card_knowledge import card_facts, card_roles
from commander_lab.models import CardRole, RulesDeckInput

PLAN_PROVENANCE: Final[str] = "abgeleitet, nicht gemessen"

_DEFAULT_GUIDES_DIR: Final[Path] = (
    Path(__file__).resolve().parents[3] / "data" / "deck_guides" / "guides"
)
_DEFAULT_SPELLBOOK_PATH: Final[Path] = (
    Path(__file__).resolve().parents[3] / "data" / "meta" / "spellbook_combos.json"
)
_MAX_COMBO_LINES: Final[int] = 24


def _norm_name(name: str) -> str:
    return name.split(" // ", 1)[0].strip().casefold()


@dataclass(frozen=True)
class _SpellbookCombo:
    combo_id: str
    cards: tuple[str, ...]
    cards_folded: frozenset[str]
    any_of: tuple[tuple[str, ...], ...]
    any_of_folded: tuple[frozenset[str], ...]
    result: str
    tier: str


@dataclass(frozen=True)
class _SpellbookIndex:
    entries: tuple[_SpellbookCombo, ...]
    by_anchor: dict[str, tuple[int, ...]]


@lru_cache(maxsize=4)
def _load_spellbook_index(path_str: str) -> _SpellbookIndex:
    path = Path(path_str)
    if not path.is_file():
        return _SpellbookIndex(entries=(), by_anchor={})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _SpellbookIndex(entries=(), by_anchor={})
    raw_combos = payload.get("combos") if isinstance(payload, dict) else None
    if not isinstance(raw_combos, list):
        return _SpellbookIndex(entries=(), by_anchor={})

    entries: list[_SpellbookCombo] = []
    anchor_buckets: dict[str, list[int]] = {}
    for row in raw_combos:
        if not isinstance(row, dict):
            continue
        raw_cards = row.get("cards")
        if not isinstance(raw_cards, list) or not raw_cards:
            continue
        cards = tuple(str(c).strip() for c in raw_cards if isinstance(c, str) and c.strip())
        if len(cards) < 2:
            continue
        cards_folded = frozenset(_norm_name(c) for c in cards)
        if len(cards_folded) < 2:
            continue
        raw_any = row.get("any_of")
        any_groups: list[tuple[str, ...]] = []
        any_folded: list[frozenset[str]] = []
        if isinstance(raw_any, list):
            for group in raw_any:
                if isinstance(group, list):
                    cleaned = tuple(
                        str(c).strip() for c in group if isinstance(c, str) and c.strip()
                    )
                    if cleaned:
                        any_groups.append(cleaned)
                        any_folded.append(frozenset(_norm_name(c) for c in cleaned))
        idx = len(entries)
        entries.append(
            _SpellbookCombo(
                combo_id=str(row.get("combo_id") or f"combo-{idx}"),
                cards=cards,
                cards_folded=cards_folded,
                any_of=tuple(any_groups),
                any_of_folded=tuple(any_folded),
                result=str(row.get("result") or ""),
                tier=str(row.get("tier") or ""),
            )
        )
        anchor = min(cards_folded)
        anchor_buckets.setdefault(anchor, []).append(idx)

    return _SpellbookIndex(
        entries=tuple(entries),
        by_anchor={anchor: tuple(indices) for anchor, indices in anchor_buckets.items()},
    )


@dataclass(frozen=True)
class DeckPlan:
    deck_id: str
    focus: str
    win_condition: str
    engines: tuple[str, ...]
    answers: tuple[str, ...]
    key_cards: tuple[str, ...]
    provenance: str = PLAN_PROVENANCE
    combos: tuple[dict[str, object], ...] = ()
    combo_cards: tuple[str, ...] = ()
    combo_partners: tuple[tuple[str, tuple[str, ...]], ...] = ()
    win_axes: tuple[str, ...] = ()
    protection_targets: tuple[str, ...] = ()
    tutor_priorities: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "deck_id": self.deck_id,
            "focus": self.focus,
            "win_condition": self.win_condition,
            "engines": list(self.engines),
            "answers": list(self.answers),
            "key_cards": list(self.key_cards),
            "provenance": self.provenance,
            "combos": [
                {
                    **combo,
                    "cards": list(combo_cards)
                    if isinstance((combo_cards := combo.get("cards")), list)
                    else [],
                }
                for combo in self.combos
            ],
            "combo_cards": list(self.combo_cards),
            "combo_partners": {card: list(partners) for card, partners in self.combo_partners},
            "win_axes": list(self.win_axes),
            "protection_targets": list(self.protection_targets),
            "tutor_priorities": list(self.tutor_priorities),
        }


def _find_guide(deck_id: str, guides_dir: Path) -> dict[str, object] | None:
    if not guides_dir.is_dir():
        return None

    # 1. Exact slug match or normalized deck_id
    normalized = deck_id.replace("/", "_").replace("-", "_")
    candidates = [
        guides_dir / f"{deck_id}.json",
        guides_dir / f"{normalized}.json",
        guides_dir / f"{deck_id.split('/')[-1]}.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                pass

    # 2. Iterate and match deck_id inside guide
    for guide_file in sorted(guides_dir.glob("*.json")):
        try:
            data = json.loads(guide_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("deck_id") == deck_id:
                return data
        except (OSError, ValueError):
            continue
    return None


def _match_deck_combos(
    deck_cards: tuple[str, ...],
    index: _SpellbookIndex,
) -> tuple[
    tuple[dict[str, object], ...],
    tuple[str, ...],
    tuple[tuple[str, tuple[str, ...]], ...],
]:
    if not index.entries or not deck_cards:
        return (), (), ()
    canonical_by_folded: dict[str, str] = {}
    for card in deck_cards:
        canonical_by_folded.setdefault(_norm_name(card), card)
    deck_folded = frozenset(canonical_by_folded.keys())

    matched: list[tuple[tuple[int, int, str], dict[str, object]]] = []
    seen_card_sets: set[frozenset[str]] = set()
    for anchor in sorted(deck_folded & index.by_anchor.keys()):
        for idx in index.by_anchor[anchor]:
            entry = index.entries[idx]
            if not entry.cards_folded <= deck_folded:
                continue
            resolved_names = [canonical_by_folded[cf] for cf in sorted(entry.cards_folded)]
            any_ok = True
            for group_folded in entry.any_of_folded:
                hits = sorted(group_folded & deck_folded)
                if not hits:
                    any_ok = False
                    break
                resolved_names.append(canonical_by_folded[hits[0]])
            if not any_ok:
                continue
            full_folded = frozenset(_norm_name(n) for n in resolved_names)
            if full_folded in seen_card_sets:
                continue
            seen_card_sets.add(full_folded)
            unique_names = sorted(dict.fromkeys(resolved_names))
            is_win = 0 if "win the game" in entry.result.casefold() else 1
            sort_key = (is_win, len(unique_names), entry.combo_id)
            matched.append(
                (
                    sort_key,
                    {
                        "combo_id": entry.combo_id,
                        "cards": unique_names,
                        "result": entry.result,
                        "tier": entry.tier,
                    },
                )
            )
    matched.sort(key=lambda item: item[0])
    top_combos = tuple(item[1] for item in matched[:_MAX_COMBO_LINES])

    partner_map: dict[str, list[str]] = {}
    combo_card_order: list[str] = []
    seen_combo_cards: set[str] = set()
    for combo in top_combos:
        combo_list = combo.get("cards")
        if not isinstance(combo_list, list):
            continue
        for card in combo_list:
            if not isinstance(card, str):
                continue
            if card not in seen_combo_cards:
                seen_combo_cards.add(card)
                combo_card_order.append(card)
            others = [other for other in combo_list if isinstance(other, str) and other != card]
            bucket = partner_map.setdefault(card, [])
            for other in others:
                if other not in bucket:
                    bucket.append(other)

    combo_partners = tuple(
        sorted((card, tuple(partners)) for card, partners in partner_map.items())
    )
    return top_combos, tuple(combo_card_order), combo_partners


def _ordered_unique(groups: tuple[tuple[str, ...], ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for card in group:
            norm = _norm_name(card)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            result.append(card)
    return tuple(result)


@lru_cache(maxsize=256)
def _derive_deck_plan_cached(
    deck_id: str,
    commander_names: tuple[str, ...],
    sorted_mainboard: tuple[str, ...],
    guides_dir_str: str,
    spellbook_path_str: str,
) -> DeckPlan:
    guide = _find_guide(deck_id, Path(guides_dir_str))
    all_cards = list(sorted_mainboard) + list(commander_names)
    role_map: dict[str, set[CardRole]] = {}
    for card in dict.fromkeys(all_cards):
        facts = card_facts(card)
        role_map[card] = set(card_roles(facts).keys()) if facts is not None else set()

    engines: list[str] = [card for card, roles in role_map.items() if CardRole.ENGINE in roles]
    answers: list[str] = [
        card
        for card, roles in role_map.items()
        if roles & {CardRole.REMOVAL, CardRole.COUNTER, CardRole.WIPE, CardRole.PROTECTION}
    ]
    finishers: list[str] = [
        card
        for card, roles in role_map.items()
        if roles & {CardRole.FINISHER, CardRole.COMBAT_PAYOFF}
    ]
    tutors_or_draw = [
        card for card, roles in role_map.items() if roles & {CardRole.DRAW, CardRole.SELECTION}
    ]

    if guide is not None:
        win_condition = str(guide.get("win_plan") or "")
        if not win_condition:
            angriffs_fokus = str(guide.get("angriffs_fokus") or "")
            if angriffs_fokus:
                win_condition = f"Angriffs-Fokus: {angriffs_fokus}"
            else:
                win_condition = (
                    f"Synergie- und Kampflinie über {', '.join(commander_names)} "
                    f"({len(finishers)} Finisher/Payoffs)"
                )

        archetypes = guide.get("archetypen")
        if isinstance(archetypes, list) and archetypes:
            focus = str(archetypes[0])
        elif guide.get("angriffs_fokus"):
            focus = str(guide.get("angriffs_fokus"))
        else:
            focus = "value_engine"

        schluesselkarten = guide.get("schluesselkarten")
        if isinstance(schluesselkarten, list) and schluesselkarten:
            key_cards = tuple(str(c) for c in schluesselkarten)
        else:
            key_cards = tuple(engines[:3] + finishers[:3])[:6]
    else:
        focus = "kreaturen_und_synergie" if finishers else "kontrolle_und_value"
        win_condition = (
            f"Kampflinie über {', '.join(commander_names)} "
            f"({len(finishers)} Finisher, {len(engines)} Motoren)"
        )
        key_cards = tuple(list(commander_names) + engines[:2] + finishers[:2])[:6]

    sorted_engines = tuple(sorted(set(engines)))
    sorted_answers = tuple(sorted(set(answers)))
    sorted_finishers = tuple(sorted(set(finishers)))

    spellbook_index = _load_spellbook_index(spellbook_path_str)
    combos, combo_cards, combo_partners = _match_deck_combos(
        tuple(dict.fromkeys(all_cards)), spellbook_index
    )

    commander_folded = {_norm_name(c) for c in commander_names}
    non_commander_combos = tuple(c for c in combo_cards if _norm_name(c) not in commander_folded)
    non_commander_keys = tuple(c for c in key_cards if _norm_name(c) not in commander_folded)

    win_axes_list: list[str] = []
    if combos:
        win_axes_list.append(f"combo ({len(combos)} Linie(n))")
    if sorted_finishers:
        win_axes_list.append(f"finisher ({len(sorted_finishers)})")
    if commander_names:
        win_axes_list.append(f"commander ({', '.join(commander_names)})")

    protection_targets = _ordered_unique(
        (commander_names, non_commander_combos[:6], non_commander_keys[:6], sorted_engines[:4])
    )
    tutor_priorities = _ordered_unique(
        (
            non_commander_combos,
            non_commander_keys,
            sorted_engines,
            sorted_finishers,
            sorted_answers,
            tuple(sorted(set(tutors_or_draw))),
        )
    )

    return DeckPlan(
        deck_id=deck_id,
        focus=focus,
        win_condition=win_condition,
        engines=sorted_engines,
        answers=sorted_answers,
        key_cards=key_cards,
        provenance=PLAN_PROVENANCE,
        combos=combos,
        combo_cards=combo_cards,
        combo_partners=combo_partners,
        win_axes=tuple(win_axes_list),
        protection_targets=protection_targets,
        tutor_priorities=tutor_priorities,
    )


def derive_deck_plan(
    deck: RulesDeckInput,
    guides_dir: Path | None = None,
    *,
    spellbook_path: Path | None = None,
) -> DeckPlan:
    """Derive a concise DeckPlan from guides, Spellbook combos, and card roles (memoized)."""
    directory = (guides_dir or _DEFAULT_GUIDES_DIR).resolve()
    sb_path = (spellbook_path or _DEFAULT_SPELLBOOK_PATH).resolve()
    return _derive_deck_plan_cached(
        deck.deck_id,
        tuple(deck.commander_names),
        tuple(sorted(deck.mainboard)),
        str(directory),
        str(sb_path),
    )
