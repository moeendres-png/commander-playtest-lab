from __future__ import annotations

import base64
import gzip
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from commander_lab.models import (
    CandidateProfile,
    CardIdentity,
    CardLegality,
    Color,
    DataQuality,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.storage import sha256_value

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
ROGSHAI_DECK_ID = "rogshai/current"
ROGSHAI_COMMANDERS = (
    "Ishai, Ojutai Dragonspeaker",
    "Rograkh, Son of Rohgahh",
)
ROGSHAI_COLORS = frozenset({Color.WHITE, Color.BLUE, Color.RED})
FRESH_ROGSHAI_PREFIX = "rogshai/fresh/"
RUNTIME_CONTRACT_PATH = Path("data/rogshai_mvp/K1_K2_RUNTIME_CONTRACT.json")
RUNTIME_SNAPSHOT_PATH = Path("data/rogshai_mvp/CURRENT_DRIVE_RUNTIME.json.gz.b64")
STRUCTURAL_PROFILE_PATH = Path("data/cards/structural_role_profiles.json")
DISABLED_QUALITY_PRIORS = {
    "current_deck_membership_prior": "disabled",
    "historical_include_prior": "disabled",
    "historical_cut_prior": "disabled",
    "optimizer_history_prior": "disabled",
    "protected_card_quality_bonus": "disabled",
    "allocation_quality_prior": "disabled",
    "popularity_prior": "disabled",
    "structural_coverage_quality_prior": "disabled",
}


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


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:52]}-{digest}"


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise FreshRebuildDataError(f"required RogShai MVP input missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreshRebuildDataError(f"cannot read RogShai MVP input: {path}") from exc
    if not isinstance(payload, dict):
        raise FreshRebuildDataError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _decode_runtime(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\x1f\x8b"):
            compressed = raw
        else:
            compressed = base64.b64decode(raw.strip(), validate=True)
        payload = json.loads(gzip.decompress(compressed).decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, gzip.BadGzipFile, json.JSONDecodeError) as exc:
        raise FreshRebuildDataError(f"cannot decode current Drive runtime: {path}") from exc
    if not isinstance(payload, dict):
        raise FreshRebuildDataError("current Drive runtime must be a JSON object")
    return cast(dict[str, Any], payload)


def load_fresh_rebuild_runtime(root: str | Path) -> dict[str, Any]:
    """Load the checked-in current-Drive projection and reject drift fail-closed."""

    root_path = Path(root)
    contract = _json_object(root_path / RUNTIME_CONTRACT_PATH)
    runtime_spec = contract.get("current_drive_runtime")
    if not isinstance(runtime_spec, dict):
        raise FreshRebuildDataError("current_drive_runtime contract is missing")

    relative_path = Path(str(runtime_spec.get("path", RUNTIME_SNAPSHOT_PATH.as_posix())))
    runtime_path = root_path / relative_path
    observed_sha = _sha256_file(runtime_path)
    expected_sha = str(runtime_spec.get("content_sha256", ""))
    if observed_sha != expected_sha:
        raise FreshRebuildDataError(
            f"current Drive runtime hash mismatch: {observed_sha} != {expected_sha}"
        )

    compact = _decode_runtime(runtime_path)
    raw_cards = compact.get("cards")
    if not isinstance(raw_cards, list):
        raise FreshRebuildDataError("current Drive runtime cards must be a list")
    expected_count = int(runtime_spec.get("candidate_count", 0))
    if len(raw_cards) != expected_count or int(compact.get("expected", -1)) != expected_count:
        raise FreshRebuildDataError(
            f"current RogShai candidate universe incomplete: {len(raw_cards)} != {expected_count}"
        )

    cards: list[dict[str, object]] = []
    for raw in raw_cards:
        if not isinstance(raw, dict):
            raise FreshRebuildDataError("candidate row must be an object")
        cards.append(
            {
                "card_id": str(raw.get("id", "")),
                "oracle_name": str(raw.get("n", "")),
                "color_identity": list(str(raw.get("ci", ""))),
                "commander_legal": raw.get("l") is True,
                "mana_cost": str(raw.get("mc", "") or ""),
                "mana_value": float(raw.get("mv", 0.0) or 0.0),
                "type_line": str(raw.get("t", "Unknown") or "Unknown"),
                "oracle_text": str(raw.get("ot", "") or ""),
                "basic_land": raw.get("b") is True,
                "physical": {
                    "available": int(raw.get("a", 0) or 0),
                    "allocated_to_korvold": int(raw.get("k", 0) or 0),
                },
                "coverage": {
                    "status": str(raw.get("cv", "UNKNOWN")),
                    "requires_model_review": raw.get("cv") != "STRUCTURALLY_MODELED",
                },
                "roles": list(raw.get("roles", [])) if isinstance(raw.get("roles"), list) else [],
                "synergy_hooks": (
                    list(raw.get("hooks", [])) if isinstance(raw.get("hooks"), list) else []
                ),
                "interaction_targets": (
                    list(raw.get("targets", [])) if isinstance(raw.get("targets"), list) else []
                ),
                "instant_speed_capable": raw.get("instant") is True,
            }
        )

    names = [str(row["oracle_name"]) for row in cards]
    card_ids = [str(row["card_id"]) for row in cards]
    if "" in names or len(set(names)) != expected_count:
        raise FreshRebuildDataError("candidate universe has missing or duplicate oracle names")
    if "" in card_ids or len(set(card_ids)) != expected_count:
        raise FreshRebuildDataError("candidate universe has missing or duplicate card IDs")

    observed_coverage = dict(
        sorted(
            Counter(
                str(cast(dict[str, object], row["coverage"])["status"])
                for row in cards
            ).items()
        )
    )
    expected_coverage = compact.get("coverage_counts")
    if observed_coverage != expected_coverage:
        raise FreshRebuildDataError(
            f"coverage-count drift: {observed_coverage} != {expected_coverage}"
        )

    bias = compact.get("bias")
    if not isinstance(bias, dict):
        raise FreshRebuildDataError("fresh-rebuild bias policy is missing")
    for key, expected in DISABLED_QUALITY_PRIORS.items():
        if bias.get(key) != expected:
            raise FreshRebuildDataError(f"forbidden quality prior is not disabled: {key}")
    if bias.get("allocation_may_affect_physical_feasibility_only") is not True:
        raise FreshRebuildDataError("allocation is not constrained to physical feasibility")
    if bias.get("control_deck_visible_in_independent_stage") is not False:
        raise FreshRebuildDataError("current RogShai control is visible in independent stage")
    if bias.get("unmodeled_cards_remain_in_candidate_universe") is not True:
        raise FreshRebuildDataError("unmodeled cards are not retained in the candidate universe")
    if bias.get("synthetic_opponent_completion_is_observation") is not False:
        raise FreshRebuildDataError("synthetic opponent completion is mislabeled as observation")

    raw_relations = compact.get("relations", [])
    if not isinstance(raw_relations, list):
        raise FreshRebuildDataError("runtime relations must be a list")
    relations: list[dict[str, object]] = []
    for row in raw_relations:
        if not isinstance(row, dict):
            continue
        relations.append(
            {
                "source_name": str(row.get("s", "")),
                "target": str(row.get("t", "")),
                "relationship_type": str(row.get("rt", "")),
                "confidence": str(row.get("c", "")),
                "mechanism": str(row.get("m", "")),
            }
        )

    opponent_registry = compact.get("opponent_registry")
    primary = compact.get("primary_4p_rogshai")
    sources = compact.get("sources")
    if not isinstance(opponent_registry, dict) or not isinstance(primary, dict):
        raise FreshRebuildDataError("current opponent registry or primary RogShai pod is missing")
    if not isinstance(sources, dict):
        raise FreshRebuildDataError("runtime source manifest is missing")

    return {
        "schema_version": str(compact.get("schema_version", "")),
        "candidate_universe": {
            "count": expected_count,
            "cards": cards,
            "coverage_counts": observed_coverage,
        },
        "bias_policy": cast(dict[str, object], bias),
        "synergy_relations": relations,
        "opponent_registry": cast(dict[str, object], opponent_registry),
        "primary_4p_rogshai": cast(dict[str, object], primary),
        "pod_scenarios": compact.get("pod_scenarios", {}),
        "sources": cast(dict[str, dict[str, object]], sources),
        "runtime_file_sha256": observed_sha,
    }


def _identity_from_fact(row: Mapping[str, object]) -> CardIdentity:
    color_values = row.get("color_identity", [])
    colors = frozenset(
        Color(str(value))
        for value in cast(list[object], color_values)
        if str(value) in {"W", "U", "B", "R", "G"}
    )
    return CardIdentity(
        oracle_name=str(row["oracle_name"]),
        mana_cost=str(row.get("mana_cost", "") or "") or None,
        mana_value=float(row.get("mana_value", 0.0) or 0.0),
        color_identity=colors,
        type_line=str(row.get("type_line", "Unknown") or "Unknown"),
        oracle_text=str(row.get("oracle_text", "") or "") or None,
        legalities={
            "commander": (
                CardLegality.LEGAL
                if row.get("commander_legal") is True
                else CardLegality.UNKNOWN
            )
        },
        is_basic_land=row.get("basic_land") is True,
        data_quality=DataQuality.PROJECT_VERIFIED,
    )


def _load_explicit_profiles(root: Path) -> dict[str, StructuralCardProfile]:
    payload = _json_object(root / STRUCTURAL_PROFILE_PATH)
    rows = payload.get("profiles", [])
    if not isinstance(rows, list):
        raise FreshRebuildDataError("structural profile registry is malformed")
    profiles: dict[str, StructuralCardProfile] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        profile = StructuralCardProfile.model_validate(raw)
        profiles[profile.oracle_name] = profile
    return profiles


def load_fresh_rogshai_universe(root: str | Path) -> FreshRogShaiUniverse:
    root_path = Path(root)
    runtime = load_fresh_rebuild_runtime(root_path)
    universe_payload = cast(dict[str, object], runtime["candidate_universe"])
    rows = cast(list[dict[str, object]], universe_payload["cards"])
    explicit_profiles = _load_explicit_profiles(root_path)

    candidates: dict[str, CandidateProfile] = {}
    review_required: dict[str, CardIdentity] = {}
    candidate_names: set[str] = set()
    available_quantities: dict[str, int] = {}
    coverage_status_by_name: dict[str, str] = {}
    facts_by_name: dict[str, Mapping[str, object]] = {}

    for row in rows:
        identity = _identity_from_fact(row)
        name = identity.oracle_name
        candidate_names.add(name)
        facts_by_name[name] = row

        physical = cast(dict[str, object], row["physical"])
        available = int(physical.get("available", 0) or 0)
        if name in BASIC_LANDS:
            available = max(50, available)
        available_quantities[name] = available

        coverage = cast(dict[str, object], row["coverage"])
        status = str(coverage.get("status", "UNKNOWN"))
        coverage_status_by_name[name] = status
        if status == "STRUCTURALLY_MODELED":
            try:
                profile = explicit_profiles[name]
            except KeyError as exc:
                raise FreshRebuildDataError(
                    f"K1 marks {name!r} structurally modeled but current main has no explicit profile"
                ) from exc
            candidate_id = f"fresh/profile/{_slug(name)}"
            candidates[candidate_id] = CandidateProfile(
                candidate_id=candidate_id,
                card=profile,
                allowed_deck_ids=(ROGSHAI_DECK_ID,),
                physical_status="current_drive_verified_fresh_availability",
                notes=(
                    "Explicit current structural profile. Fresh-rebuild membership is independent "
                    "of current RogShai deck membership."
                ),
            )
        else:
            review_required[name] = identity

    coverage_counts = cast(dict[str, int], universe_payload["coverage_counts"])
    expected_modeled = int(coverage_counts.get("STRUCTURALLY_MODELED", 0))
    if len(candidates) != expected_modeled:
        raise FreshRebuildDataError(
            f"modeled-candidate join mismatch: {len(candidates)} != {expected_modeled}"
        )
    if len(candidate_names) != int(universe_payload["count"]):
        raise FreshRebuildDataError("candidate count changed during runtime materialization")

    verified = frozenset(
        name for name in candidate_names if available_quantities.get(name, 0) > 0
    )
    return FreshRogShaiUniverse(
        candidates=candidates,
        review_required=review_required,
        candidate_names=frozenset(candidate_names),
        available_quantities=available_quantities,
        verified_physical_names=verified,
        coverage_status_by_name=coverage_status_by_name,
        candidate_facts_by_name=facts_by_name,
        source_inventory_path=RUNTIME_SNAPSHOT_PATH.as_posix(),
        runtime_sha256=str(runtime["runtime_file_sha256"]),
    )


def build_independent_smoke_mainboard(
    root_or_universe: str | Path | FreshRogShaiUniverse,
    *,
    universe: FreshRogShaiUniverse | None = None,
) -> tuple[str, ...]:
    """Build a deterministic control-blind technical fixture; never use it for strength inference."""

    if isinstance(root_or_universe, FreshRogShaiUniverse):
        active = root_or_universe
    else:
        active = universe or load_fresh_rogshai_universe(root_or_universe)

    by_name = active.candidate_by_name()
    required_package_cards = (
        "Combat Research",
        "Staggering Insight",
        "Counterspell",
        "Boros Charm",
    )
    selected: list[str] = []
    for name in required_package_cards:
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
        if card.oracle_name in selected:
            continue
        selected.append(card.oracle_name)
        if len(selected) == 62:
            break
    if len(selected) != 62:
        raise FreshRebuildDataError(
            f"insufficient explicitly modeled nonland candidates for smoke fixture: {len(selected)}"
        )

    mainboard = tuple(selected + ["Plains"] * 12 + ["Island"] * 12 + ["Mountain"] * 12)
    if len(mainboard) != 98:
        raise FreshRebuildDataError("internal smoke fixture did not reach 98 cards")
    return mainboard


def build_fresh_rogshai_profile(
    root: str | Path,
    mainboard_names: tuple[str, ...],
    *,
    variant_label: str = "candidate",
    profile_overrides: Mapping[str, StructuralCardProfile] | None = None,
    universe: FreshRogShaiUniverse | None = None,
) -> StructuralDeckProfile:
    """Materialize an arbitrary legal/physical 98-card RogShai mainboard for simulation."""

    root_path = Path(root)
    universe = universe or load_fresh_rogshai_universe(root_path)
    overrides = dict(profile_overrides or {})

    if len(mainboard_names) != 98:
        raise ValueError(
            f"RogShai fresh mainboard must contain exactly 98 cards; got {len(mainboard_names)}"
        )
    if any(name in ROGSHAI_COMMANDERS for name in mainboard_names):
        raise ValueError("commanders must not be duplicated in the 98-card mainboard")

    counts = Counter(mainboard_names)
    duplicate_nonbasics = sorted(
        name for name, count in counts.items() if name not in BASIC_LANDS and count > 1
    )
    if duplicate_nonbasics:
        raise ValueError(f"singleton violation: {duplicate_nonbasics}")
    over_basic_policy = sorted(
        name for name, count in counts.items() if name in BASIC_LANDS and count > 50
    )
    if over_basic_policy:
        raise ValueError(f"basic-land project availability exceeded: {over_basic_policy}")

    missing_universe = sorted(set(mainboard_names) - set(universe.candidate_names))
    if missing_universe:
        raise ValueError(f"cards outside fresh RogShai candidate universe: {missing_universe}")

    unavailable = sorted(
        name
        for name, count in counts.items()
        if universe.available_quantities.get(name, 0) < count
    )
    if unavailable:
        raise ValueError(
            "simultaneous physical buildability failed after Korvold-only availability "
            f"constraints: {unavailable}"
        )

    by_name = universe.candidate_by_name()
    unresolved = sorted(
        name
        for name in set(mainboard_names)
        if name in universe.review_required and name not in overrides
    )
    if unresolved:
        raise ValueError(
            f"mechanistic profile required before structural scoring/simulation: {unresolved}"
        )

    cards: list[StructuralCardProfile] = []
    for name in mainboard_names:
        override = overrides.get(name)
        if override is not None:
            if override.oracle_name != name:
                raise ValueError(f"profile override name mismatch for {name!r}")
            cards.append(override)
            continue
        try:
            cards.append(by_name[name].card)
        except KeyError as exc:
            raise ValueError(f"missing structural profile for {name!r}") from exc

    missing_commanders = sorted(set(ROGSHAI_COMMANDERS) - set(by_name))
    if missing_commanders:
        raise FreshRebuildDataError(
            f"commander structural profiles missing from current modeled universe: {missing_commanders}"
        )
    for commander in ROGSHAI_COMMANDERS:
        if universe.available_quantities.get(commander, 0) < 1:
            raise ValueError(f"commander is not physically available: {commander}")
        cards.append(by_name[commander].card)

    snapshot_hash = universe.runtime_sha256
    deck_hash = sha256_value(
        {
            "mode": "fresh_rebuild",
            "commanders": ROGSHAI_COMMANDERS,
            "mainboard": sorted(counts.items()),
            "profile_override_names": sorted(overrides),
            "data_snapshot_hash": snapshot_hash,
        }
    )
    safe_label = "".join(
        ch for ch in variant_label.casefold() if ch.isalnum() or ch in {"-", "_"}
    )[:32]
    deck_id = f"{FRESH_ROGSHAI_PREFIX}{safe_label or deck_hash[:12]}-{deck_hash[:10]}"
    return StructuralDeckProfile(
        deck_id=deck_id,
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
        data_snapshot_hash=snapshot_hash,
    )


def run_k2_bias_suite(root: str | Path) -> dict[str, object]:
    """Execute the K2 bias invariants against the current runtime, without loading control."""

    runtime = load_fresh_rebuild_runtime(root)
    universe = load_fresh_rogshai_universe(root)
    bias = cast(dict[str, object], runtime["bias_policy"])
    registry = cast(dict[str, object], runtime["opponent_registry"])
    opponent_rows = registry.get("opponents", [])
    synthetic_boundary = True
    if isinstance(opponent_rows, list):
        for row in opponent_rows:
            if not isinstance(row, dict):
                continue
            if "synthetic" in str(row.get("deck_source_type", "")):
                if str(row.get("deck_status", "")).casefold() in {
                    "observed",
                    "directly_observed",
                    "verified_full_deck",
                }:
                    synthetic_boundary = False

    tests = {
        "K2-BIAS-A-current-deck-blindness": (
            bias.get("current_deck_membership_prior") == "disabled"
            and bias.get("control_deck_visible_in_independent_stage") is False
        ),
        "K2-BIAS-B-historical-cut-blindness": (
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
            bias.get("synthetic_opponent_completion_is_observation") is False
            and synthetic_boundary
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
