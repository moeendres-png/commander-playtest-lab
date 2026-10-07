"""Effective v1.0.6 materialization for the current qualification boundary.

Reuses the canonical resolver (``scripts/resolve_pre_freeze_contract.py``)
rather than re-implementing the overlay, so the effective records and their
digests are produced by exactly one code path.

REUSE_AS_IS: the successor overlay algorithm, the projection-key digest spec,
and the denominator are owned by the current contract resolver.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from .source_lock import (
    CURRENT_QUALIFICATION_BOUNDARY,
    FULL107_FROZEN_SOURCE,
    repo_root,
)

RESOLVER_RELATIVE_PATH = "scripts/resolve_pre_freeze_contract.py"


@lru_cache(maxsize=1)
def _resolver(root: str) -> ModuleType:
    """Load the canonical pre-Freeze contract resolver as a module."""
    path = Path(root) / RESOLVER_RELATIVE_PATH
    spec = importlib.util.spec_from_file_location("resolve_pre_freeze_contract", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load canonical contract resolver at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class EffectiveMaterialization:
    """The effective current materialization plus the 107-row denominator."""

    bundle: dict[str, Any]
    denominator: list[str]
    canonical_bundle_digest: str
    # The corrected-fixture set the current authority names. It is carried on
    # the materialization itself because the successor overlay does not put it
    # into the bundle: the authority document is the sole source, and a
    # hard-coded fallback here previously advertised one corrected fixture
    # while nine were in effect.
    changed_fixture_ids: tuple[str, ...] = ()
    # The successor contract's bounded-secondary, non-denominator records
    # (contract 1.0.23, #441). They are never FULL107 denominator rows: the
    # loader refuses any overlap, so a bounded-secondary record can never
    # change the 107-row denominator, produce a cardinality_row or affect AF06.
    bounded_secondary: tuple[dict[str, Any], ...] = ()

    def bounded_secondary_records(self) -> list[dict[str, Any]]:
        return list(self.bounded_secondary)

    def bounded_secondary_record(self, fixture_id: str) -> dict[str, Any] | None:
        """The bounded-secondary record for ``fixture_id``, or None (fail closed)."""
        for item in self.bounded_secondary:
            if item["fixture_id"] == fixture_id:
                return item
        return None

    def record(self, fixture_id: str) -> dict[str, Any]:
        for item in self.bundle["records"]:
            if item["fixture_id"] == fixture_id:
                record: dict[str, Any] = item
                return record
        raise KeyError(f"fixture not in effective materialization: {fixture_id}")

    def records(self) -> list[dict[str, Any]]:
        return list(self.bundle["records"])

    def denominator_records(self) -> list[dict[str, Any]]:
        by_id = {item["fixture_id"]: item for item in self.bundle["records"]}
        missing = [fid for fid in self.denominator if fid not in by_id]
        if missing:
            raise RuntimeError(f"denominator rows absent from materialization: {missing}")
        return [by_id[fid] for fid in self.denominator]

    def receipt(self) -> dict[str, Any]:
        return {
            "schema_version": self.bundle["schema_version"],
            "contract_id": self.bundle.get("contract_id"),
            "qualification_boundary": CURRENT_QUALIFICATION_BOUNDARY,
            "frozen_full107_source": FULL107_FROZEN_SOURCE,
            "canonical_bundle_digest": self.canonical_bundle_digest,
            "materialization_record_count": self.bundle["record_count"],
            "provider_denominator_count": len(self.denominator),
            "changed_fixture_ids": list(self.changed_fixture_ids),
            "rules_authority": self.bundle.get("current_rules_authority"),
        }


def load_effective_materialization(root: Path | None = None) -> EffectiveMaterialization:
    """Load and validate the effective successor materialization and denominator."""
    resolved_root = root or repo_root()
    module = _resolver(str(resolved_root))
    bundle = module.load_effective_materialization()
    denominator_doc = module._load(
        resolved_root / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json"
    )
    denominator = list(denominator_doc["fixture_ids"])
    if len(denominator) != 107:
        raise RuntimeError(f"provider denominator must be 107 rows, got {len(denominator)}")
    if denominator_doc.get("denominator_decreased_to_bypass_blocker") is not False:
        raise RuntimeError("provider denominator was decreased to bypass a blocker")
    authority = module._load(resolved_root / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json")
    changed = tuple(str(item) for item in authority["full107"]["changed_fixture_ids"])
    if not changed:
        raise RuntimeError("the current authority names no corrected fixture")
    if len(set(changed)) != len(changed):
        raise RuntimeError(f"the authority's corrected-fixture set has duplicates: {changed}")
    for fixture_id in changed:
        if bundle["records"] and not any(
            record["fixture_id"] == fixture_id and record.get("repair_provenance")
            for record in bundle["records"]
        ):
            raise RuntimeError(
                f"authority names {fixture_id} as corrected but the effective materialization "
                "carries no repair provenance for it"
            )
    bounded = tuple(module.bounded_secondary_records())
    overlap = {record["fixture_id"] for record in bounded}.intersection(denominator)
    if overlap:
        # Fail closed at the boundary: a bounded-secondary record is not a
        # denominator row, and a contract that made one so would silently move
        # the 107-row denominator and AF06. Refuse the whole materialization.
        raise RuntimeError(
            f"bounded-secondary record(s) are FULL107 denominator rows: {sorted(overlap)}"
        )
    return EffectiveMaterialization(
        bundle=bundle,
        denominator=denominator,
        canonical_bundle_digest=bundle["canonical_bundle_digest"],
        changed_fixture_ids=changed,
        bounded_secondary=bounded,
    )


# ---------------------------------------------------------------------------
# PB-03: classify the starting-state requirement by MECHANISM, not by row name.
# ---------------------------------------------------------------------------
#
# The qualification runner previously decided which denominator rows were
# blocked by the missing generic starting-state seam with a hard-coded tuple of
# fixture-id prefixes:
#
#     INJECTION_BLOCKED_FAMILIES = ("WS05-MP-", "WS05-CMD-ZONE-", ...)
#
# That is a name-based classifier. It cannot classify a row it has never seen,
# it silently mis-classifies any future row whose id happens to share a prefix,
# and it hides the actual reason behind a string. It is a harness hardcode, not
# an obligation statement.
#
# The real question is semantic: is this obligation reachable from a fresh game
# start, or does it require a frozen mid-game state? That is answerable from the
# obligation's own required events. Measured against the effective
# materialization, the split is exact and the two groups share no event at all:
# every event in a mid-game row denotes a mechanism that a game-start-to-priority
# drive never reaches (a live priority ring, a stack response, a combat
# declaration, a zone change, a turn transition, a player leaving), and every
# event in a game-start row denotes a mechanism that occurs at or before the
# first turn (a commander in the command zone, a mulligan, a tax, a first-turn
# draw, mana paid).
#
# The families below are named for the mechanism, not for the row, so a future
# row is classified by what it needs rather than by what it is called.

MID_GAME_MECHANISM_FAMILIES: dict[str, tuple[str, ...]] = {
    "live_priority_ring": ("priority_ring_live_order", "priority_action_resets_pass_count"),
    "stack_response": ("response_on_stack", "APNAP_stack_order", "simultaneous_trigger_event"),
    "combat_declaration": (
        "attacker_declared:",
        "blocker_declared:",
        "legal_blocker_partition:",
        "commander_combat_damage:",
    ),
    "commander_damage_accounting": (
        "commander_damage_total:",
        "commander_damage_checked_per_commander",
    ),
    "zone_manipulation": ("commander_zone_event:", "commander_choice:", "object_leaves_game:"),
    "turn_transition": ("extra_turn_created:", "next_turn:"),
    "multiplayer_lifecycle": ("player_leaves:", "player_loses:", "multiplayer_cleanup:"),
}

# A prefix appearing in any family marks the event as a mid-game mechanism.
MID_GAME_MECHANISM_PREFIXES: tuple[str, ...] = tuple(
    sorted({event for events in MID_GAME_MECHANISM_FAMILIES.values() for event in events})
)


def mid_game_mechanisms(record: dict[str, Any]) -> list[str]:
    """The mid-game mechanisms this obligation requires, by name.

    Returns the family names whose events this record requires. An empty list
    means every required event is reachable from a fresh game start.
    """
    events = record.get("expected_events")
    if isinstance(events, dict):
        required = events.get("required_events") or []
    elif isinstance(events, list):
        required = events
    else:
        required = []
    found: list[str] = []
    for family, markers in MID_GAME_MECHANISM_FAMILIES.items():
        for event in required:
            text = str(event)
            if any(text == marker or text.startswith(marker) for marker in markers):
                found.append(family)
                break
    return found


def requires_starting_state(record: dict[str, Any]) -> bool:
    """True when this obligation cannot be reached from a fresh game start.

    This replaces the fixture-id-prefix hardcode. It is derived from the
    obligation's required events, so it classifies a row it has never seen, and
    it names the mechanisms responsible so a reviewer can audit the reason
    without reading the id.
    """
    return bool(mid_game_mechanisms(record))
