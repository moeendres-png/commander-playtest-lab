from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from commander_lab.project_context import load_project_context

_BASIC_BY_COLOR = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
}
_BASIC_LANDS = frozenset(_BASIC_BY_COLOR.values())


@dataclass(frozen=True)
class CommanderReadiness:
    commanders: tuple[str, ...]
    configuration_type: str
    color_identity: tuple[str, ...]
    commander_copies_available: bool
    color_legal_nonbasic_support_names: int
    role_evidence: dict[str, int]
    minimum_library_cards: int
    maximum_library_capacity_with_basic_floor: int
    simultaneous_physical_buildability: bool
    structural_adapter_available: bool
    pilot_available: bool
    four_player_model_claim_allowed: bool
    evidence_boundary: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _identity(raw: object) -> frozenset[str]:
    text = str(raw or "").upper()
    return frozenset(color for color in "WUBRG" if color in text)


def _is_commander_candidate(row: dict[str, Any]) -> bool:
    if row.get("currently_owned") is not True or row.get("commander_legality") != "legal":
        return False
    card_type = str(row.get("card_type", ""))
    oracle_text = str(row.get("oracle_text", ""))
    return "Legendary Creature" in card_type or "can be your commander" in oracle_text


def _is_partner_component(row: dict[str, Any]) -> bool:
    if row.get("currently_owned") is not True or row.get("commander_legality") != "legal":
        return False
    if _is_commander_candidate(row):
        return True
    card_type = str(row.get("card_type", ""))
    return "Legendary Enchantment" in card_type and "Background" in card_type


def _partner_mode(row: dict[str, Any]) -> str | None:
    text = str(row.get("oracle_text", ""))
    lowered = text.casefold()
    if re.search(r"(^|\n)partner(\s*\([^\n]*\))?(\n|$)", lowered):
        return "partner"
    if "partner with " in lowered:
        return "partner_with"
    if "choose a background" in lowered:
        return "choose_a_background"
    if "doctor's companion" in lowered:
        return "doctors_companion"
    if "friends forever" in lowered:
        return "friends_forever"
    return None


def _partner_with_target(row: dict[str, Any]) -> str | None:
    text = str(row.get("oracle_text", ""))
    match = re.search(r"Partner with ([^\n(]+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _role_evidence(row: dict[str, Any]) -> set[str]:
    text = str(row.get("oracle_text", "")).casefold()
    card_type = str(row.get("card_type", "")).casefold()
    roles: set[str] = set()
    if "draw a card" in text or "draw two cards" in text or "draw three cards" in text:
        roles.add("draw")
    if "look at the top" in text or "scry " in text or "surveil " in text:
        roles.add("selection")
    if "add {" in text or ("search your library" in text and "land" in text):
        roles.add("ramp_or_fixing")
    if any(token in text for token in ("destroy target", "exile target", "counter target spell")):
        roles.add("interaction")
    if "return target" in text and "to its owner's hand" in text:
        roles.add("interaction")
    if any(token in text for token in ("hexproof", "indestructible", "protection from")):
        roles.add("protection_signal")
    if any(token in text for token in ("destroy all", "exile all", "all creatures get -")):
        roles.add("board_wipe_signal")
    if "from your graveyard" in text and "return" in text:
        roles.add("recursion_signal")
    if "exile target card from a graveyard" in text or "exile all cards from" in text:
        roles.add("graveyard_interaction_signal")
    if "each opponent" in text or "each player loses" in text:
        roles.add("multiplayer_scaling_signal")
    if "land" in card_type:
        roles.add("land")
    return roles


class SecondDeckReadinessWorkflow:
    """Read-only, deterministic future-deck readiness from current physical availability.

    The current availability projection is the Gate-A synchronized read-only projection of the
    canonical physical pool after active own-deck allocations and opponent reservations. This
    workflow does not rebuild those semantics from historical repo deck snapshots.
    """

    def __init__(self, root: str | Path, *, basic_land_floor: int = 50) -> None:
        if basic_land_floor < 0:
            raise ValueError("basic_land_floor must be non-negative")
        self.root = Path(root).resolve()
        self.basic_land_floor = basic_land_floor
        self.context = load_project_context(self.root)
        inventory_payload = _load_json(
            self.root / "data/canonical_import/2026-08-07/inventory_snapshot.json"
        )
        self.inventory_rows = [
            dict(row) for row in inventory_payload.get("cards", []) if isinstance(row, dict)
        ]
        self.inventory_by_name = {
            str(row["oracle_name"]): row for row in self.inventory_rows if row.get("oracle_name")
        }
        self.availability_path = (
            self.root / "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json"
        )

    def remaining_pool(self) -> Counter[str]:
        payload = _load_json(self.availability_path)
        cards = payload.get("cards")
        if not isinstance(cards, dict):
            raise ValueError("current optimization availability has no cards mapping")
        remaining: Counter[str] = Counter()
        for raw_name, raw_quantity in cards.items():
            name = str(raw_name)
            quantity = int(raw_quantity)
            if quantity < 0:
                raise ValueError(f"negative current physical availability for {name}: {quantity}")
            if quantity > 0:
                remaining[name] = quantity
        return remaining

    def _support_evidence(
        self,
        commander_names: tuple[str, ...],
        identity: frozenset[str],
        remaining: Counter[str],
    ) -> tuple[int, dict[str, int], int]:
        excluded = set(commander_names)
        role_counts: Counter[str] = Counter()
        nonbasic_names = 0
        for name, quantity in remaining.items():
            if quantity <= 0 or name in excluded:
                continue
            row = self.inventory_by_name.get(name)
            if row is None or row.get("commander_legality") != "legal":
                continue
            if not _identity(row.get("color_identity")).issubset(identity):
                continue
            if name not in _BASIC_LANDS:
                nonbasic_names += 1
            for role in _role_evidence(row):
                role_counts[role] += 1
        basic_capacity = self.basic_land_floor * len(identity)
        return nonbasic_names, dict(sorted(role_counts.items())), nonbasic_names + basic_capacity

    def _readiness(
        self,
        commander_names: tuple[str, ...],
        configuration_type: str,
        remaining: Counter[str],
    ) -> CommanderReadiness:
        rows = [self.inventory_by_name[name] for name in commander_names]
        identity = frozenset().union(*(_identity(row.get("color_identity")) for row in rows))
        copies = all(
            remaining.get(name, 0) >= commander_names.count(name) for name in set(commander_names)
        )
        support_names, role_counts, capacity = self._support_evidence(
            commander_names, identity, remaining
        )
        library_size = 100 - len(commander_names)
        buildable = copies and capacity >= library_size
        return CommanderReadiness(
            commanders=commander_names,
            configuration_type=configuration_type,
            color_identity=tuple(color for color in "WUBRG" if color in identity),
            commander_copies_available=copies,
            color_legal_nonbasic_support_names=support_names,
            role_evidence=role_counts,
            minimum_library_cards=library_size,
            maximum_library_capacity_with_basic_floor=capacity,
            simultaneous_physical_buildability=buildable,
            structural_adapter_available=False,
            pilot_available=False,
            four_player_model_claim_allowed=False,
            evidence_boundary=(
                "Physical/legal support-depth evidence only. No universal commander power score, "
                "deck construction, reservation, or simulated 4-player performance is inferred."
            ),
        )

    def _partner_configurations(
        self, components: list[dict[str, Any]], remaining: Counter[str]
    ) -> list[CommanderReadiness]:
        by_name = {str(row["oracle_name"]): row for row in components}
        configs: dict[tuple[str, str], CommanderReadiness] = {}
        names = sorted(by_name, key=str.casefold)
        for index, left_name in enumerate(names):
            left = by_name[left_name]
            left_mode = _partner_mode(left)
            for right_name in names[index + 1 :]:
                right = by_name[right_name]
                right_mode = _partner_mode(right)
                legal = False
                config_type = ""
                if left_mode == right_mode == "partner":
                    legal, config_type = True, "partner"
                elif left_mode == right_mode == "friends_forever":
                    legal, config_type = True, "friends_forever"
                elif left_mode == "partner_with" or right_mode == "partner_with":
                    left_target = _partner_with_target(left)
                    right_target = _partner_with_target(right)
                    if (left_target and left_target.casefold() == right_name.casefold()) or (
                        right_target and right_target.casefold() == left_name.casefold()
                    ):
                        legal, config_type = True, "partner_with"
                elif left_mode == "choose_a_background" and "Background" in str(
                    right.get("card_type", "")
                ):
                    legal, config_type = True, "choose_a_background"
                elif right_mode == "choose_a_background" and "Background" in str(
                    left.get("card_type", "")
                ):
                    legal, config_type = True, "choose_a_background"
                elif left_mode == "doctors_companion" and "Time Lord Doctor" in str(
                    right.get("card_type", "")
                ):
                    legal, config_type = True, "doctors_companion"
                elif right_mode == "doctors_companion" and "Time Lord Doctor" in str(
                    left.get("card_type", "")
                ):
                    legal, config_type = True, "doctors_companion"
                if legal:
                    key = (left_name, right_name)
                    configs[key] = self._readiness(key, config_type, remaining)
        return [configs[key] for key in sorted(configs)]

    def run(self) -> dict[str, object]:
        remaining = self.remaining_pool()
        commanders = [
            row
            for row in self.inventory_rows
            if _is_commander_candidate(row) and remaining.get(str(row.get("oracle_name")), 0) > 0
        ]
        partner_components = [
            row
            for row in self.inventory_rows
            if _is_partner_component(row) and remaining.get(str(row.get("oracle_name")), 0) > 0
        ]
        single = [
            self._readiness((str(row["oracle_name"]),), "single_commander", remaining)
            for row in sorted(commanders, key=lambda row: str(row["oracle_name"]).casefold())
        ]
        partner = self._partner_configurations(partner_components, remaining)
        return {
            "workflow": "second_deck_readiness",
            "active_own_decks_subtracted": list(self.context.active_own_deck_ids),
            "primary_deckbuilding_focus": self.context.primary_deckbuilding_focus,
            "historical_decks_do_not_block_availability": True,
            "current_availability_projection": str(self.availability_path.relative_to(self.root)),
            "availability_semantics": (
                "Gate-A current projection: active own-deck allocations and opponent reservations "
                "already reflected; historical former-deck allocations do not block availability."
            ),
            "remaining_physical_unique_names": len(remaining),
            "remaining_physical_total_cards": sum(remaining.values()),
            "single_commander_candidate_count": len(single),
            "partner_component_count": len(partner_components),
            "partner_configuration_count": len(partner),
            "single_commander_candidates": [row.as_dict() for row in single],
            "partner_configurations": [row.as_dict() for row in partner],
            "partner_configurations_are_separate_bonus_path": True,
            "creates_second_deck": False,
            "creates_reservation": False,
            "universal_commander_power_score": None,
            "four_player_performance_claim": None,
            "basic_land_floor_per_available_color": self.basic_land_floor,
            "evidence_class": "physical_legal_support_depth",
            "truth_boundary": (
                "Discovery and support depth only. A discovered commander/configuration receives no "
                "structural 4-player performance estimate until an actual legal 99, structural model, "
                "pilot/policy support, and scenario context exist."
            ),
        }


__all__ = ["CommanderReadiness", "SecondDeckReadinessWorkflow"]
