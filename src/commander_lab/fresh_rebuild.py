from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from commander_lab.models import (
    CandidateProfile,
    CardIdentity,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.storage import sha256_value
from commander_lab.tools.candidates import (
    BASIC_LANDS,
    _allowed_decks,
    _as_int,
    _identity_from_inventory,
    _inventory_rows,
    _slug,
)

ROGSHAI_DECK_ID = "rogshai/current"
ROGSHAI_COMMANDERS = (
    "Ishai, Ojutai Dragonspeaker",
    "Rograkh, Son of Rohgahh",
)
FRESH_ROGSHAI_PREFIX = "rogshai/fresh/"
RUNTIME_CONTRACT_PATH = Path("data/rogshai_mvp/K1_K2_RUNTIME_CONTRACT.json")
STRUCTURAL_PROFILE_PATH = Path("data/cards/structural_role_profiles.json")


class FreshRebuildDataError(RuntimeError):
    """Fail-closed error for stale or inconsistent RogShai fresh-rebuild inputs."""


@dataclass(frozen=True, slots=True)
class FreshRogShaiUniverse:
    """Current, bias-neutral RogShai construction universe."""

    candidates: Mapping[str, CandidateProfile]
    review_required: Mapping[str, CardIdentity]
    candidate_names: frozenset[str]
    available_quantities: Mapping[str, int]
    verified_physical_names: frozenset[str]
    coverage_status_by_name: Mapping[str, str]
    candidate_facts_by_name: Mapping[str, Mapping[str, object]]
    source_inventory_path: str
    runtime_sha256: str

    @property
    def candidate_count(self) -> int:
        return len(self.candidate_names)

    @property
    def structurally_scorable_count(self) -> int:
        return len({candidate.card.oracle_name for candidate in self.candidates.values()})

    @property
    def review_required_count(self) -> int:
        return len(self.review_required)

    def candidate_by_name(self) -> dict[str, CandidateProfile]:
        return {candidate.card.oracle_name: candidate for candidate in self.candidates.values()}


def _contract(root: Path) -> dict[str, Any]:
    path = root / RUNTIME_CONTRACT_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreshRebuildDataError(f"cannot read RogShai MVP contract: {path}") from exc
    if not isinstance(payload, dict):
        raise FreshRebuildDataError("RogShai MVP contract must be a JSON object")
    return cast(dict[str, Any], payload)


def _candidate_rows(root: Path, contract: Mapping[str, object]) -> list[dict[str, object]]:
    """Return base inventory plus the small verified 2026-08-10 Drive delta."""

    rows = [dict(row) for row in _inventory_rows(root)]
    delta = contract.get("current_drive_inventory_delta", [])
    if not isinstance(delta, list):
        raise FreshRebuildDataError("current_drive_inventory_delta must be a list")
    by_name = {str(row.get("oracle_name", "")): row for row in rows}
    for item in delta:
        if not isinstance(item, dict):
            raise FreshRebuildDataError("inventory delta row must be an object")
        row = dict(item)
        name = str(row.get("oracle_name", ""))
        if not name:
            raise FreshRebuildDataError("inventory delta row missing oracle_name")
        by_name[name] = row
    return list(by_name.values())


def _current_rogshai_eligibility(root: Path) -> dict[str, dict[str, object]]:
    """Load the canonical current RogShai candidate/availability projection.

    Historical own-deck membership is deliberately excluded from this current physical
    availability contract. Inactive Korvold must never reduce RogShai availability.
    """

    path = root / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreshRebuildDataError(f"cannot read current candidate eligibility: {path}") from exc
    raw = payload.get("eligible_by_deck", {}).get(ROGSHAI_DECK_ID)
    if not isinstance(raw, dict):
        raise FreshRebuildDataError("current RogShai candidate eligibility is missing")
    rows: dict[str, dict[str, object]] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise FreshRebuildDataError(f"invalid current eligibility row for {name}")
        rows[str(name)] = dict(value)
    return rows


def _explicit_profiles(root: Path) -> dict[str, StructuralCardProfile]:
    path = root / STRUCTURAL_PROFILE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("profiles", [])
    if not isinstance(rows, list):
        raise FreshRebuildDataError("structural profile registry malformed")
    profiles: dict[str, StructuralCardProfile] = {}
    for item in rows:
        if isinstance(item, dict):
            profile = StructuralCardProfile.model_validate(item)
            profiles[profile.oracle_name] = profile
    return profiles


def _candidate_set_hash(names: set[str]) -> str:
    payload = "\n".join(sorted(names)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_fresh_rebuild_runtime(root: str | Path) -> dict[str, object]:
    """Expose the current K1/K2 facts without loading the current RogShai control list."""

    project = Path(root)
    contract = _contract(project)
    pool = cast(dict[str, object], contract["rogshai_candidate_pool"])
    invariants = cast(dict[str, object], contract["fresh_rebuild_invariants"])
    bias_policy = {
        "current_deck_membership_prior": "disabled",
        "historical_include_prior": "disabled",
        "historical_cut_prior": "disabled",
        "optimizer_history_prior": "disabled",
        "protected_card_quality_bonus": "disabled",
        "allocation_quality_prior": "disabled",
        "structural_coverage_quality_prior": "disabled",
        "control_deck_visible_in_independent_stage": invariants[
            "current_control_visible_before_finalist_freeze"
        ],
        "allocation_may_affect_physical_feasibility_only": True,
        "unmodeled_cards_remain_in_candidate_universe": invariants[
            "unmodeled_cards_remain_in_candidate_universe"
        ],
        "synthetic_opponent_completion_is_observation": invariants[
            "synthetic_opponent_completion_is_observation"
        ],
    }
    coverage = {
        "STRUCTURALLY_MODELED": _as_int(pool["k1_modeled"]),
        "PARTIALLY_MODELED": _as_int(pool["k1_partially_modeled"]),
        "STRUCTURALLY_UNMODELED": _as_int(pool["k1_unmodeled"]),
    }
    evidence_rows = contract.get("opponent_evidence", [])
    return {
        "candidate_universe": {
            "count": _as_int(pool["expected_count"]),
            "coverage_counts": coverage,
        },
        "bias_policy": bias_policy,
        "primary_4p_rogshai": cast(dict[str, object], contract["primary_4p_rogshai"]),
        "opponent_registry": {"opponents": evidence_rows},
        "technical_package_smoke": cast(dict[str, object], contract["technical_package_smoke"]),
        "sources": cast(dict[str, object], contract["sources"]),
    }


def load_fresh_rogshai_universe(root: str | Path) -> FreshRogShaiUniverse:
    project = Path(root)
    contract = _contract(project)
    pool = cast(dict[str, object], contract["rogshai_candidate_pool"])
    rows = _candidate_rows(project, contract)
    current_eligibility = _current_rogshai_eligibility(project)
    profiles = _explicit_profiles(project)

    candidates: dict[str, CandidateProfile] = {}
    review_required: dict[str, CardIdentity] = {}
    names: set[str] = set()
    available: dict[str, int] = {}
    coverage_status: dict[str, str] = {}
    facts: dict[str, Mapping[str, object]] = {}

    for row in rows:
        if not row.get("currently_owned") or _as_int(row.get("quantity", 0)) <= 0:
            continue
        if str(row.get("commander_legality", "")).casefold() != "legal":
            continue
        identity = _identity_from_inventory(row)
        if ROGSHAI_DECK_ID not in _allowed_decks(identity):
            continue
        name = identity.oracle_name
        names.add(name)
        facts[name] = {
            "oracle_name": name,
            "color_identity": [color.value for color in identity.color_identity],
            "commander_legal": True,
        }
        current_row = current_eligibility.get(name)
        if current_row is None:
            raise FreshRebuildDataError(
                f"current RogShai eligibility lost candidate from canonical universe: {name}"
            )
        available[name] = _as_int(current_row.get("physical_available_quantity", 0))
        if name in BASIC_LANDS:
            available[name] = max(50, available[name])
        profile = profiles.get(name)
        if profile is None:
            coverage_status[name] = str(row.get("coverage_status", "REVIEW_REQUIRED"))
            review_required[name] = identity
            continue
        coverage_status[name] = "STRUCTURALLY_MODELED"
        candidate_id = f"fresh/profile/{_slug(name)}"
        candidates[candidate_id] = CandidateProfile(
            candidate_id=candidate_id,
            card=profile,
            allowed_deck_ids=(ROGSHAI_DECK_ID,),
            physical_status="current_drive_verified_fresh_availability",
            notes=(
                "Explicit structural profile; Fresh-Rebuild membership is independent "
                "of current RogShai deck membership."
            ),
        )

    expected_count = _as_int(pool["expected_count"])
    if len(names) != expected_count:
        raise FreshRebuildDataError(f"candidate count mismatch: {len(names)} != {expected_count}")
    expected_hash = str(pool["sorted_oracle_names_sha256"])
    observed_hash = _candidate_set_hash(names)
    if observed_hash != expected_hash:
        raise FreshRebuildDataError(
            f"candidate set hash mismatch: {observed_hash} != {expected_hash}"
        )
    expected_modeled = _as_int(pool["k1_modeled"])
    if len(candidates) != expected_modeled:
        raise FreshRebuildDataError(
            f"modeled candidate join mismatch: {len(candidates)} != {expected_modeled}"
        )

    runtime_hash = sha256_value(
        {
            "candidate_pool_sha256": pool["content_sha256"],
            "candidate_names_sha256": expected_hash,
            "inventory_delta": contract["current_drive_inventory_delta"],
            "current_candidate_eligibility": current_eligibility,
            "fresh_rebuild_invariants": contract["fresh_rebuild_invariants"],
        }
    )
    verified = frozenset(name for name in names if available.get(name, 0) > 0)
    return FreshRogShaiUniverse(
        candidates=candidates,
        review_required=review_required,
        candidate_names=frozenset(names),
        available_quantities=available,
        verified_physical_names=verified,
        coverage_status_by_name=coverage_status,
        candidate_facts_by_name=facts,
        source_inventory_path=(
            "data/canonical_import/2026-08-07/inventory_snapshot.json + "
            "K1_K2_RUNTIME_CONTRACT.current_drive_inventory_delta"
        ),
        runtime_sha256=runtime_hash,
    )


def build_independent_smoke_mainboard(
    root_or_universe: str | Path | FreshRogShaiUniverse,
    *,
    universe: FreshRogShaiUniverse | None = None,
) -> tuple[str, ...]:
    """Build a deterministic control-blind technical fixture, not a strength candidate."""

    active = (
        root_or_universe
        if isinstance(root_or_universe, FreshRogShaiUniverse)
        else universe or load_fresh_rogshai_universe(root_or_universe)
    )
    by_name = active.candidate_by_name()
    selected: list[str] = []
    for name in ("Combat Research", "Staggering Insight", "Counterspell", "Boros Charm"):
        candidate = by_name.get(name)
        if (
            candidate is not None
            and active.available_quantities.get(name, 0) > 0
            and name not in ROGSHAI_COMMANDERS
            and not candidate.card.is_land
        ):
            selected.append(name)
    nonlands = sorted(
        (
            candidate.card
            for candidate in active.candidates.values()
            if candidate.card.oracle_name not in ROGSHAI_COMMANDERS
            and not candidate.card.is_land
            and active.available_quantities.get(candidate.card.oracle_name, 0) > 0
        ),
        key=lambda card: (card.mana_value, card.oracle_name),
    )
    for card in nonlands:
        if card.oracle_name not in selected:
            selected.append(card.oracle_name)
        if len(selected) == 62:
            break
    if len(selected) != 62:
        raise FreshRebuildDataError(
            f"insufficient explicitly modeled nonland candidates for smoke fixture: {len(selected)}"
        )
    return tuple(selected + ["Plains"] * 12 + ["Island"] * 12 + ["Mountain"] * 12)


def build_fresh_rogshai_profile(
    root: str | Path,
    mainboard_names: tuple[str, ...],
    *,
    variant_label: str = "candidate",
    profile_overrides: Mapping[str, StructuralCardProfile] | None = None,
    universe: FreshRogShaiUniverse | None = None,
) -> StructuralDeckProfile:
    """Materialize a legal/physical 98-card mainboard plus both RogShai commanders."""

    project = Path(root)
    active = universe or load_fresh_rogshai_universe(project)
    overrides = dict(profile_overrides or {})
    if len(mainboard_names) != 98:
        raise ValueError(
            f"RogShai fresh mainboard must contain exactly 98 cards; got {len(mainboard_names)}"
        )
    if any(name in ROGSHAI_COMMANDERS for name in mainboard_names):
        raise ValueError("commanders must not be duplicated in the 98-card mainboard")
    counts = Counter(mainboard_names)
    duplicates = sorted(
        name for name, count in counts.items() if name not in BASIC_LANDS and count > 1
    )
    if duplicates:
        raise ValueError(f"singleton violation: {duplicates}")
    if any(count > 50 for name, count in counts.items() if name in BASIC_LANDS):
        raise ValueError("basic-land project availability exceeded")
    outside = sorted(set(mainboard_names) - set(active.candidate_names))
    if outside:
        raise ValueError(f"cards outside fresh RogShai candidate universe: {outside}")
    unavailable = sorted(
        name for name, count in counts.items() if active.available_quantities.get(name, 0) < count
    )
    if unavailable:
        raise ValueError(f"simultaneous physical buildability failed: {unavailable}")
    unresolved = sorted(
        name
        for name in set(mainboard_names)
        if name in active.review_required and name not in overrides
    )
    if unresolved:
        raise ValueError (
            f"mechanistic profile required before structural scoring/simulation: {unresolved}"
        )

    by_name = active.candidate_by_name()
    cards: list[StructuralCardProfile] = []
    for name in mainboard_names:
        override = overrides.get(name)
        if override is not None:
            if override.oracle_name != name:
                raise ValueError(f"profile override name mismatch for {name!r}")
            cards.append(override)
        else:
            cards.append(by_name[name].card)
    missing_commanders = sorted(set(ROGSHAI_COMMANDERS) - set(by_name))
    if missing_commanders:
        raise FreshRebuildDataError(
            f"commander structural profiles missing from modeled universe: {missing_commanders}"
        )
    for commander in ROGSHAI_COMMANDERS:
        if active.available_quantities.get(commander, 0) < 1:
            raise ValueError(f"commander is not physically available: {commander}")
        cards.append(by_name[commander].card)

    deck_hash = sha256_value(
        {
            "mode": "fresh_rebuild",
            "commanders": ROGSHAI_COMMANDERS,
            "mainboard": sorted(counts.items()),
            "profile_override_names": sorted(overrides),
            "data_snapshot_hash": active.runtime_sha256,
        }
    )
    safe_label = "".join(ch for ch in variant_label.casefold() if ch.isalnum() or ch in {"-", "_"})[:32]
    return StructuralDeckProfile(
        deck_id=f"{FRESH_ROGSHAI_PREFIX}{safe_label or deck_hash[:12]}-{deck_hash[:10]}",
        deck_hash=deck_hash,
        commander_names=ROGSHAI_COMMANDERS,
        cards=tuple(cards),
        commander_base_costs={
            "Ishai, Ojutai Dragonspeaker": 4.0,
            "Rograkh, Son of Rohgahh": 0.0,
        },
        commander_base_power={
            "Ishai, Ojutai Dragonspeaker": 1.0,
            "Rograkh, Son of Rohgahh": 0.0,
        },
        commander_strategy="rogshai",
        data_snapshot_hash=active.runtime_sha256,
    )


def run_k2_bias_suite(root: str | Path) -> dict[str, object]:
    """Execute K2 bias invariants against current runtime without loading the control deck."""

    runtime = load_fresh_rebuild_runtime(root)
    universe = load_fresh_rogshai_universe(root)
    bias = cast(dict[str, object], runtime["bias_policy"])
    evidence = cast(dict[str, object], runtime["opponent_registry"])
    rows = evidence.get("opponents", [])
    synthetic_boundary = True
    if isinstance(rows, list):
        for item in rows:
            if not isinstance(item, dict):
                continue
            synthetic = "synthetic" in str(item.get("deck_source_type", ""))
            observed = str(item.get("deck_status", "")).casefold() in {
                "observed",
                "directly_observed",
                "verified_full_deck",
            }
            if synthetic and observed:
                synthetic_boundary = False
    tests = {
        "K2-BIAS-A-current-deck-blindness": (
            bias.get("current_deck_membership_prior") == "disabled"
            and bias.get("control_deck_visible_in_independent_stage") is False
        ),
        "K2-BIAS-B-Historical-cut-blindness": (
            bias.get("historical_include_prior") == "disabled"
            and bias.get("historical_cut_prior") == "disabled"
            and bias.get("optimizer_history_prior") == "disabled"
         ),
        "K2-BIAS-C-protected-card-blindness": (
            bias.get("protected_card_quality_bonus") == "disabled"
        ),
        "K2-BIAS-D-allocation-blindness": (
            bias.get("allocation_quality_prior") == "disabled"
            and bias.get("allocation_may_affect_physical_feasibility_only") is True
        ),
        "K2-BIAS-E-coverage-neutrality": (
            bias.get("structural_coverage_quality_prior") == "disabled"
            and universe.review_required_count > 0
            and universe.candidate_count
            == universe.structurally_scorable_count + universe.review_required_count
        ),
        "K2-BIAS-F-synthetic-boundary": (
            bias.get("synthetic_opponent_completion_is_observation") is False and synthetic_boundary
        ),
        "K2-BIAS-G-control-isolation": (
            bias.get("control_deck_visible_in_independent_stage") is False
        ),
    }
    return {
        "status": "PASS" if all(tests.values()) else "FAIL",
        "tests": tests,
        "candidate_count": universe.candidate_count,
        "structurally_scorable": universe.structurally_scorable_count,
        "review_required": universe.review_required_count,
    }
