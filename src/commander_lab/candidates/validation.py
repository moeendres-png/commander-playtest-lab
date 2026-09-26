from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from commander_lab.deck_registry import DeckPolicyRegistry, load_deck_policy_registry
from commander_lab.repositories.candidates import (
    inventory_rows,
    load_current_optimization_availability,
)

from .contracts import HARD_FAIL_CODES, NON_ADMISSION_FIELDS
from .models import (
    CandidateValidationReport,
    CandidateValidationResult,
    DeckCandidate,
    DeckCandidateSet,
)
from .normalization import normalize_candidate_set

BASIC_LANDS = frozenset({"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"})


@dataclass(frozen=True, slots=True)
class CardHardValidityRecord:
    oracle_name: str
    owned_quantity: int
    target_available_quantity: int
    color_identity: frozenset[str]
    commander_legality: str
    oracle_text: str = ""
    physically_owned: bool = True


@dataclass(frozen=True, slots=True)
class HardValidationContext:
    target_deck_id: str
    expected_commanders: tuple[str, ...]
    commander_identity: frozenset[str]
    cards: dict[str, CardHardValidityRecord]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _target_deck_payload(
    root: Path,
    registry: DeckPolicyRegistry,
    target_deck_id: str,
) -> dict[str, Any]:
    manifest = _load_json(registry.source_path("deck_manifest"))
    decks = manifest.get("decks")
    if not isinstance(decks, dict) or not isinstance(decks.get(target_deck_id), dict):
        raise ValueError(f"target deck missing from deck manifest: {target_deck_id}")
    deck_meta = decks[target_deck_id]
    normalized_file = deck_meta.get("normalized_file")
    if not isinstance(normalized_file, str) or not normalized_file:
        raise ValueError(f"target deck has no normalized_file: {target_deck_id}")
    return _load_json(root / "data" / "decks" / normalized_file)


def _target_deck_counts(
    root: Path,
    registry: DeckPolicyRegistry,
    target_deck_id: str,
) -> Counter[str]:
    deck = _target_deck_payload(root, registry, target_deck_id)
    counts: Counter[str] = Counter()
    raw_cards = deck.get("cards")
    if not isinstance(raw_cards, list):
        raise ValueError(f"target deck cards malformed: {target_deck_id}")
    for row in raw_cards:
        if not isinstance(row, dict):
            continue
        name = row.get("oracle_name")
        quantity = row.get("quantity")
        zone = row.get("zone")
        if isinstance(name, str) and isinstance(quantity, int) and zone in {"main", "commander"}:
            counts[name] += quantity
    return counts


def _expected_commanders(
    root: Path,
    registry: DeckPolicyRegistry,
    target_deck_id: str,
) -> tuple[str, ...]:
    deck = _target_deck_payload(root, registry, target_deck_id)
    raw_cards = deck.get("cards")
    if not isinstance(raw_cards, list):
        raise ValueError(f"target deck cards malformed: {target_deck_id}")
    commanders: list[str] = []
    for row in raw_cards:
        if not isinstance(row, dict) or row.get("zone") != "commander":
            continue
        name = row.get("oracle_name")
        quantity = row.get("quantity")
        if isinstance(name, str) and isinstance(quantity, int) and quantity > 0:
            commanders.extend([name] * quantity)
    if not commanders:
        raise ValueError(f"target deck has no commander cards: {target_deck_id}")
    return tuple(commanders)


def load_hard_validation_context(
    root: str | Path,
    *,
    target_deck_id: str | None = None,
) -> HardValidationContext:
    """Load read-only physical/legal truth for one active candidate target.

    The target deck's own currently allocated copies are added back to free optimization
    availability because an external candidate replaces that comparison arm rather than being
    allocated alongside it. Allocations belonging to other active decks remain unavailable.
    """

    root_path = Path(root).resolve()
    registry = load_deck_policy_registry(root_path)
    target = target_deck_id or registry.primary_deck_id
    registry.assert_active(target)

    free = load_current_optimization_availability(root_path, registry=registry)
    released_target = _target_deck_counts(root_path, registry, target)
    available = Counter({name: int(quantity) for name, quantity in free.items()})
    available.update(released_target)

    cards: dict[str, CardHardValidityRecord] = {}
    for row in inventory_rows(root_path, registry=registry):
        name = row.get("oracle_name")
        if not isinstance(name, str) or not name.strip():
            continue
        physically_owned = row.get("currently_owned") is True
        raw_quantity = row.get("quantity", 0)
        quantity = raw_quantity if physically_owned and isinstance(raw_quantity, int) else 0
        raw_identity = str(row.get("color_identity", "") or "")
        identity = frozenset(symbol for symbol in raw_identity if symbol in "WUBRG")
        cards[name] = CardHardValidityRecord(
            oracle_name=name,
            owned_quantity=max(0, quantity),
            target_available_quantity=max(0, int(available.get(name, 0))),
            color_identity=identity,
            commander_legality=str(
                row.get("commander_legality", "unknown") or "unknown"
            ).casefold(),
            oracle_text=str(row.get("oracle_text", "") or ""),
            physically_owned=physically_owned,
        )

    return HardValidationContext(
        target_deck_id=target,
        expected_commanders=_expected_commanders(root_path, registry, target),
        commander_identity=frozenset(color.value for color in registry.commander_identity(target)),
        cards=cards,
    )


def _has_unlimited_copy_rule(card: CardHardValidityRecord) -> bool:
    return "a deck can have any number of cards named" in card.oracle_text.casefold()


def _validate_candidate(
    candidate: DeckCandidate,
    *,
    declared_identity: frozenset[str],
    context: HardValidationContext,
) -> tuple[str, ...]:
    reasons: set[str] = set()
    commanders = tuple(candidate.commander_names)
    expected = tuple(context.expected_commanders)
    if len(commanders) not in {1, 2}:
        reasons.add("COMMANDER_COUNT_INVALID")
    if set(commanders) != set(expected):
        reasons.add("COMMANDER_IDENTITY_INVALID")
    if len(expected) == 2 and len(commanders) != 2:
        reasons.add("PARTNER_PAIRING_INVALID")
    if declared_identity != context.commander_identity:
        reasons.add("COMMANDER_IDENTITY_INVALID")

    total = len(commanders) + sum(candidate.mainboard.values())
    if total != 100:
        reasons.add("DECK_SIZE_INVALID")
    if any(name in candidate.mainboard for name in commanders):
        reasons.add("MALFORMED_CARD_IDENTITY")

    required = Counter(candidate.mainboard)
    required.update(commanders)
    commander_set = set(commanders)
    for name, quantity in required.items():
        card = context.cards.get(name)
        if card is None:
            reasons.add("UNKNOWN_REQUIRED_CARD")
            continue
        if not card.physically_owned:
            reasons.add("PHYSICAL_AVAILABILITY_INVALID")
        if card.commander_legality == "banned":
            reasons.add("BANNED_CARD_INVALID")
        elif card.commander_legality != "legal":
            reasons.add(
                "COMMANDER_LEGALITY_INVALID" if name in commander_set else "CARD_LEGALITY_INVALID"
            )
        if not card.color_identity.issubset(declared_identity):
            reasons.add("COLOR_IDENTITY_INVALID")
        if quantity > card.owned_quantity:
            reasons.add("PHYSICAL_QUANTITY_INVALID")
        elif quantity > card.target_available_quantity:
            reasons.add("ACTIVE_ALLOCATION_CONFLICT")
        if quantity > 1 and name not in BASIC_LANDS and not _has_unlimited_copy_rule(card):
            reasons.add("SINGLETON_INVALID")

    unknown = reasons - HARD_FAIL_CODES
    if unknown:
        raise AssertionError(f"validator emitted undocumented hard fail code(s): {sorted(unknown)}")
    return tuple(sorted(reasons))


def validate_candidate_set(
    candidate_set: DeckCandidateSet,
    context: HardValidationContext,
) -> tuple[DeckCandidateSet, CandidateValidationReport]:
    """Hard-validate and annotate a complete externally supplied candidate set.

    No objective, policy, meta, mana-soft, structural, fidelity, QD, frontier, Current-nearness,
    or routing signal is read for admission. The only pre-game reduction is exact-deck
    deduplication after hard validity, with all source candidate IDs retained as provenance.
    """

    normalized = normalize_candidate_set(candidate_set)
    declared_identity = frozenset(normalized.commander_identity)
    results: list[CandidateValidationResult] = []
    retained_by_hash: dict[str, str] = {}
    source_ids_by_hash: dict[str, list[str]] = {}
    hard_invalid = 0
    duplicate_count = 0

    preliminary: list[tuple[DeckCandidate, tuple[str, ...]]] = []
    for candidate in normalized.candidates:
        if candidate.deck_hash is None:
            raise AssertionError("normalization must assign a canonical deck hash")
        reasons = _validate_candidate(
            candidate,
            declared_identity=declared_identity,
            context=context,
        )
        preliminary.append((candidate, reasons))
        if not reasons:
            source_ids_by_hash.setdefault(candidate.deck_hash, []).append(candidate.candidate_id)

    annotated_candidates: list[DeckCandidate] = []
    for candidate, reasons in preliminary:
        if candidate.deck_hash is None:
            raise AssertionError("normalization must assign a canonical deck hash")
        duplicate = False
        duplicate_of: str | None = None
        status: Literal["PASS", "FAIL"]
        simulation_required: bool
        result_reasons = reasons
        if reasons:
            hard_invalid += 1
            status = "FAIL"
            simulation_required = False
        elif candidate.deck_hash in retained_by_hash:
            duplicate = True
            duplicate_count += 1
            duplicate_of = retained_by_hash[candidate.deck_hash]
            status = "PASS"
            simulation_required = False
            result_reasons = ("DUPLICATE_IDENTICAL_DECK",)
        else:
            retained_by_hash[candidate.deck_hash] = candidate.candidate_id
            status = "PASS"
            simulation_required = True
        diagnostic = {
            key: candidate.metadata[key]
            for key in sorted(candidate.metadata)
            if key in NON_ADMISSION_FIELDS
        }
        source_ids = tuple(source_ids_by_hash.get(candidate.deck_hash, [candidate.candidate_id]))
        results.append(
            CandidateValidationResult(
                candidate_id=candidate.candidate_id,
                deck_hash=candidate.deck_hash,
                hard_validity=status,
                hard_validity_reasons=result_reasons,
                duplicate_identical_deck=duplicate,
                duplicate_of_candidate_id=duplicate_of,
                simulation_required=simulation_required,
                source_candidate_ids=source_ids,
                diagnostic_metadata=diagnostic,
            )
        )
        annotated_candidates.append(
            candidate.model_copy(
                update={
                    "hard_validity": status,
                    "hard_validity_reasons": result_reasons,
                    "simulation_required": simulation_required,
                }
            )
        )

    hard_valid_count = len(normalized.candidates) - hard_invalid
    hard_valid_unique = hard_valid_count - duplicate_count
    observed = sorted({reason for result in results for reason in result.hard_validity_reasons})
    report = CandidateValidationReport(
        candidate_set_id=normalized.candidate_set_id,
        source_identity=normalized.source_identity,
        input_candidate_count=len(normalized.candidates),
        hard_valid_candidate_count=hard_valid_count,
        hard_invalid_candidate_count=hard_invalid,
        duplicate_identical_deck_count=duplicate_count,
        hard_valid_unique_count=hard_valid_unique,
        results=tuple(results),
        hard_fail_codes_observed=tuple(observed),
        no_pre_simulation_heuristic_admission=True,
    )
    annotated = normalized.model_copy(update={"candidates": tuple(annotated_candidates)})
    return annotated, report


__all__ = [
    "CardHardValidityRecord",
    "HardValidationContext",
    "load_hard_validation_context",
    "validate_candidate_set",
]
