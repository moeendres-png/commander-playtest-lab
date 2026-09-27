from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from commander_lab.canonical_features import (
    fuse_canonical_features,
    load_canonical_feature_annotations,
)
from commander_lab.deck_registry import DeckPolicyRegistry, load_deck_policy_registry
from commander_lab.engine.structural.profiles import build_default_profile
from commander_lab.models import (
    CandidateProfile,
    CardIdentity,
    CardLegality,
    CardRole,
    Color,
    DataQuality,
    SourceRef,
    StructuralCardProfile,
)
from commander_lab.semantic_features import (
    produced_self_colors,
    sanitize_structural_profile_semantics,
    structural_roles_from_oracle,
)

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def _colors(value: str) -> frozenset[Color]:
    return frozenset(Color(symbol) for symbol in value if symbol in "WUBRG")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:52]}-{digest}"


def _deck_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def inventory_rows(
    root: Path,
    *,
    registry: DeckPolicyRegistry | None = None,
) -> list[dict[str, object]]:
    deck_registry = registry or load_deck_policy_registry(root)
    path = deck_registry.source_path("inventory_snapshot", required=False)
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    cards = payload.get("cards", [])
    return [dict(row) for row in cards if isinstance(row, dict)]


def _as_int(value: object, default: int = 0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return int(value)
    raise ValueError(f"unsupported integer value: {value!r}")


def _as_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return float(value)
    raise ValueError(f"unsupported float value: {value!r}")


def load_current_optimization_availability(
    root: str | Path,
    *,
    registry: DeckPolicyRegistry | None = None,
) -> dict[str, int]:
    """Load current free availability through the deck decision registry.

    Historical release deltas remain separate from the sealed J-P5 source and may add copies back
    to the free pool only when their declared active scope exactly matches the live registry.
    """

    root_path = Path(root).resolve()
    deck_registry = registry or load_deck_policy_registry(root_path)
    path = deck_registry.source_path("optimization_availability", required=False)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cards = payload.get("cards", {})
    if not isinstance(raw_cards, dict):
        raise ValueError("current optimization availability has no cards mapping")
    cards = {str(name): max(0, int(quantity)) for name, quantity in raw_cards.items()}

    release_path = deck_registry.source_path("inactive_release_delta", required=False)
    if not release_path.is_file():
        return cards
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release_active = release.get("active_own_decks")
    if not isinstance(release_active, list):
        raise ValueError("inactive release delta has no active_own_decks list")
    if tuple(str(value) for value in release_active) != deck_registry.active_deck_ids:
        raise ValueError("inactive release delta active scope disagrees with live deck registry")

    inactive_raw = release.get("inactive_former_own_decks", ())
    if not isinstance(inactive_raw, list):
        raise ValueError("inactive release delta has invalid inactive_former_own_decks")
    inactive = {str(value) for value in inactive_raw}
    if inactive.intersection(deck_registry.active_deck_ids):
        raise ValueError("inactive release delta overlaps the live active own-deck scope")

    released = release.get("released_allocations", {})
    if not isinstance(released, dict):
        raise ValueError("released_allocations must be a mapping")
    for name, quantity in released.items():
        amount = int(quantity)
        if amount < 0:
            raise ValueError(f"negative released allocation for {name}")
        cards[str(name)] = cards.get(str(name), 0) + amount
    return cards


def load_current_candidate_eligibility(
    root: str | Path,
    *,
    registry: DeckPolicyRegistry | None = None,
) -> dict[str, set[str]]:
    root_path = Path(root).resolve()
    deck_registry = registry or load_deck_policy_registry(root_path)
    path = deck_registry.source_path("candidate_eligibility", required=False)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("eligible_by_deck", {})
    if not isinstance(raw, dict):
        raise ValueError("current candidate eligibility has no eligible_by_deck mapping")
    result: dict[str, set[str]] = {}
    for deck_id in deck_registry.active_deck_ids:
        rows = raw.get(deck_id, {})
        if not isinstance(rows, dict):
            raise ValueError(f"candidate eligibility is invalid for active deck {deck_id}")
        result[deck_id] = {str(name) for name in rows}
    return result


def load_canonical_inventory_quantities(
    root: str | Path,
    *,
    registry: DeckPolicyRegistry | None = None,
) -> dict[str, int]:
    rows = inventory_rows(Path(root).resolve(), registry=registry)
    return {
        str(row["oracle_name"]): _as_int(row.get("quantity", 0))
        for row in rows
        if row.get("currently_owned") and _as_int(row.get("quantity", 0)) > 0
    }


def _identity_from_inventory(
    row: dict[str, object],
    *,
    inventory_source_path: str,
) -> CardIdentity:
    name = str(row["oracle_name"])
    colors = _colors(str(row.get("color_identity", "")))
    type_line = str(row.get("card_type", "Unknown") or "Unknown")
    legality_text = str(row.get("commander_legality", "unknown")).casefold()
    legality = (
        CardLegality.LEGAL
        if legality_text == "legal"
        else (CardLegality.BANNED if legality_text == "banned" else CardLegality.UNKNOWN)
    )
    return CardIdentity(
        oracle_name=name,
        mana_cost=str(row.get("mana_cost", "") or "") or None,
        mana_value=_as_float(row.get("mana_value", 0.0), 0.0),
        color_identity=colors,
        type_line=type_line,
        oracle_text=str(row.get("oracle_text", "") or "") or None,
        legalities={"commander": legality},
        is_basic_land=name in BASIC_LANDS,
        data_quality=DataQuality.PROJECT_VERIFIED,
        provenance=(
            SourceRef(
                source_type="google_drive_inventory_snapshot",
                source_name="configured current inventory snapshot",
                source_path=inventory_source_path,
                quality=DataQuality.PROJECT_VERIFIED,
                notes=(
                    "Physical identity and Oracle fields imported read-only; semantic roles are "
                    "inferred separately. Source routing comes from deck_decision_registry.json."
                ),
            ),
        ),
    )


def _inferred_roles(identity: CardIdentity) -> frozenset[CardRole]:
    return structural_roles_from_oracle(identity.oracle_text, identity.type_line)


def _produced_colors(identity: CardIdentity) -> frozenset[Color]:
    return produced_self_colors(
        identity.oracle_text,
        identity.type_line,
        oracle_name=identity.oracle_name,
    )


def _inferred_profile(identity: CardIdentity) -> StructuralCardProfile | None:
    baseline = build_default_profile(identity)
    roles = _inferred_roles(identity)
    if not roles:
        return None
    roles = frozenset(set(roles) | set(baseline.roles))
    role_strengths = {role: min(0.75, baseline.role_strengths.get(role, 1.0)) for role in roles}
    is_instant_or_sorcery = (
        "instant" in identity.type_line.casefold() or "sorcery" in identity.type_line.casefold()
    )
    floor = (
        0.60
        if roles.intersection(
            {CardRole.REMOVAL, CardRole.COUNTER, CardRole.PROTECTION, CardRole.RAMP, CardRole.DRAW}
        )
        else 0.45
    )
    immediate = (
        0.65
        if is_instant_or_sorcery
        or roles.intersection({CardRole.REMOVAL, CardRole.COUNTER, CardRole.WIPE})
        else 0.45
    )
    risk = (
        0.25
        if is_instant_or_sorcery
        else (0.60 if roles.intersection({CardRole.ENGINE, CardRole.PAYOFF}) else 0.45)
    )
    scaling = (
        0.45
        if roles.intersection({CardRole.WIPE, CardRole.FINISHER})
        else (0.25 if roles.intersection({CardRole.ENGINE, CardRole.PAYOFF}) else 0.05)
    )
    produced = _produced_colors(identity) or baseline.produces_colors
    return baseline.model_copy(
        update={
            "roles": roles,
            "role_strengths": role_strengths,
            "produces_colors": produced,
            "floor_value": floor,
            "immediate_impact": immediate,
            "turn_cycle_risk": risk,
            "multiplayer_scaling": scaling,
            "source_quality": DataQuality.PROJECT_INFERRED,
            "notes": (
                "Structural-only keyword inference from the read-only configured inventory Oracle "
                "text. Suitable for candidate screening, not Tactical Oracle or external-rules "
                "validation."
            ),
        }
    )


def _allowed_decks(
    identity: CardIdentity,
    registry: DeckPolicyRegistry,
    selected_decks: tuple[str, ...],
) -> tuple[str, ...]:
    card_colors = set(identity.color_identity)
    return tuple(
        deck_id
        for deck_id in selected_decks
        if card_colors <= set(registry.commander_identity(deck_id))
    )


def _load_curated(root: Path) -> list[CandidateProfile]:
    path = root / "data/cards/phase5_upgrade_candidates.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [CandidateProfile.model_validate(item) for item in payload.get("candidates", [])]


def _profile_for_deck_packages(
    profile: StructuralCardProfile,
    *,
    registry: DeckPolicyRegistry,
    deck_id: str,
) -> StructuralCardProfile:
    policy = registry.policy(deck_id)
    retained = frozenset(
        package_id for package_id in profile.package_ids if policy.package_id_allowed(package_id)
    )
    return (
        profile
        if retained == profile.package_ids
        else profile.model_copy(update={"package_ids": retained})
    )


def _scoped_candidate_id(base_id: str, deck_id: str, allowed_count: int) -> str:
    if allowed_count <= 1:
        return base_id
    return f"{base_id}@{_deck_slug(deck_id)}"


def load_candidate_profiles(
    root: str | Path,
    *,
    deck_id: str | None = None,
    registry: DeckPolicyRegistry | None = None,
) -> dict[str, CandidateProfile]:
    root_path = Path(root).resolve()
    deck_registry = registry or load_deck_policy_registry(root_path)
    selected_decks: tuple[str, ...]
    if deck_id is not None:
        deck_registry.assert_active(deck_id)
        selected_decks = (deck_id,)
    else:
        selected_decks = deck_registry.active_deck_ids

    curated = _load_curated(root_path)
    curated_by_name = {candidate.card.oracle_name: candidate for candidate in curated}
    annotations = {
        current_deck_id: load_canonical_feature_annotations(
            root_path,
            deck_id=current_deck_id,
            registry=deck_registry,
        )
        for current_deck_id in selected_decks
    }
    inventory_source_path = deck_registry.source_relative_path("inventory_snapshot")
    candidates: dict[str, CandidateProfile] = {}

    for row in inventory_rows(root_path, registry=deck_registry):
        if not row.get("currently_owned") or _as_int(row.get("quantity", 0)) <= 0:
            continue
        if str(row.get("commander_legality", "")).casefold() != "legal":
            continue
        name = str(row["oracle_name"])
        if name in BASIC_LANDS:
            continue
        identity = _identity_from_inventory(
            row,
            inventory_source_path=inventory_source_path,
        )
        allowed = _allowed_decks(identity, deck_registry, selected_decks)
        if not allowed:
            continue

        curated_candidate = curated_by_name.get(name)
        for current_deck_id in allowed:
            annotation = annotations[current_deck_id].get(name)
            if curated_candidate is not None:
                card = _profile_for_deck_packages(
                    curated_candidate.card,
                    registry=deck_registry,
                    deck_id=current_deck_id,
                )
                candidate = curated_candidate.model_copy(
                    update={
                        "candidate_id": _scoped_candidate_id(
                            curated_candidate.candidate_id,
                            current_deck_id,
                            len(allowed),
                        ),
                        "card": card,
                        "allowed_deck_ids": (current_deck_id,),
                        "physical_status": "canonical_inventory_verified_owned",
                        "notes": (
                            (curated_candidate.notes or "")
                            + " Current physical ownership and deck scope revalidated through the "
                            "live deck registry."
                        ).strip(),
                    }
                )
            else:
                profile = _inferred_profile(identity)
                if profile is None and annotation is not None and annotation.mapped_roles:
                    baseline = build_default_profile(identity)
                    strengths = {role: 0.65 for role in annotation.mapped_roles}
                    profile = baseline.model_copy(
                        update={
                            "roles": annotation.mapped_roles,
                            "role_strengths": strengths,
                            "source_quality": DataQuality.PROJECT_INFERRED,
                            "notes": (
                                "Conservative structural representation recovered from the "
                                "configured deck feature projection. Numeric values remain "
                                "neutral/default; this is search evidence, not card-power evidence."
                            ),
                        }
                    )
                if profile is None:
                    continue
                profile = _profile_for_deck_packages(
                    profile,
                    registry=deck_registry,
                    deck_id=current_deck_id,
                )
                candidate = CandidateProfile(
                    candidate_id=_scoped_candidate_id(
                        f"inventory/{_slug(name)}",
                        current_deck_id,
                        len(allowed),
                    ),
                    card=profile,
                    allowed_deck_ids=(current_deck_id,),
                    physical_status="canonical_inventory_verified_owned",
                    notes=(
                        "Owned and Commander-legal in the configured current inventory; card "
                        "function is structural-only inference and requires higher-fidelity "
                        "validation before recommendation."
                    ),
                )

            fused = fuse_canonical_features(candidate.card, annotation)
            fused = sanitize_structural_profile_semantics(
                fused,
                oracle_text=identity.oracle_text,
                type_line=identity.type_line,
            )
            candidate = candidate.model_copy(update={"card": fused})
            if candidate.candidate_id in candidates:
                raise ValueError(f"duplicate deck-scoped candidate id: {candidate.candidate_id}")
            candidates[candidate.candidate_id] = candidate

    return candidates


def canonical_feature_fusion_summary(
    root: str | Path,
    *,
    deck_id: str | None = None,
) -> dict[str, object]:
    registry = load_deck_policy_registry(root)
    selected_deck_id = deck_id or registry.primary_deck_id
    registry.assert_active(selected_deck_id)
    candidates = load_candidate_profiles(
        root,
        deck_id=selected_deck_id,
        registry=registry,
    )
    projected = [
        candidate
        for candidate in candidates.values()
        if any(
            source.source_type == "canonical_drive_derived_projection"
            for source in candidate.card.sources
        )
    ]
    return {
        "deck_id": selected_deck_id,
        "candidates_loaded": len(candidates),
        "canonical_overlay_candidates": len(projected),
        "heuristic_or_curated_without_overlay": len(candidates) - len(projected),
        "feature_projection_configured": (
            registry.policy(selected_deck_id).feature_projection_manifest is not None
        ),
        "truth_boundary": (
            "deck-scoped candidate/feature projection coverage; not empirical card power"
        ),
    }


def candidate_registry_snapshot_hash(root: str | Path) -> str:
    registry = load_deck_policy_registry(root)
    payload = {
        "registry": registry.as_dict(),
        "candidate_eligibility_sha256": registry.source_hash("candidate_eligibility"),
        "optimization_availability_sha256": registry.source_hash(
            "optimization_availability",
            required=False,
        ),
        "inventory_sha256": registry.source_hash("inventory_snapshot"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    "candidate_registry_snapshot_hash",
    "canonical_feature_fusion_summary",
    "inventory_rows",
    "load_candidate_profiles",
    "load_canonical_inventory_quantities",
    "load_current_candidate_eligibility",
    "load_current_optimization_availability",
]
