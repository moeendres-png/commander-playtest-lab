from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from commander_lab.canonical_features import (
    fuse_canonical_features,
    load_canonical_feature_annotations,
)
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
DECK_COLORS: dict[str, frozenset[Color]] = {
    "rogshai/current": frozenset({Color.WHITE, Color.BLUE, Color.RED}),
}


def _colors(value: str) -> frozenset[Color]:
    return frozenset(Color(symbol) for symbol in value if symbol in "WUBRG")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:52]}-{digest}"


def _inventory_path(root: Path) -> Path:
    return root / "data/canonical_import/2026-08-07/inventory_snapshot.json"


def inventory_rows(root: Path) -> list[dict[str, object]]:
    path = _inventory_path(root)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [dict(row) for row in payload.get("cards", [])]


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


def load_current_optimization_availability(root: str | Path) -> dict[str, int]:
    """Load current availability without mutating sealed J-P5 evidence.

    J-P5 remains the frozen historical baseline. Current project-state deltas are applied from a
    separate unsealed projection so later direct user decisions do not rewrite holdout evidence.
    """

    root_path = Path(root)
    path = root_path / "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    cards = {str(name): int(quantity) for name, quantity in payload.get("cards", {}).items()}

    release_path = root_path / "data/collections/current/INACTIVE_FORMER_OWN_DECK_RELEASES.json"
    if not release_path.exists():
        return cards
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if release.get("active_own_decks") != ["rogshai/current"]:
        raise ValueError("current active-own-deck projection must contain only rogshai/current")
    if "korvold/current" not in release.get("inactive_former_own_decks", []):
        raise ValueError("Korvold must be marked inactive before its allocations are released")
    released = release.get("released_allocations", {})
    if not isinstance(released, dict):
        raise ValueError("released_allocations must be a mapping")
    for name, quantity in released.items():
        amount = int(quantity)
        if amount < 0:
            raise ValueError(f"negative released allocation for {name}")
        cards[str(name)] = cards.get(str(name), 0) + amount
    return cards


def load_current_candidate_eligibility(root: str | Path) -> dict[str, set[str]]:
    path = Path(root) / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(deck_id): {str(name) for name in rows}
        for deck_id, rows in payload.get("eligible_by_deck", {}).items()
    }


def load_canonical_inventory_quantities(root: str | Path) -> dict[str, int]:
    rows = inventory_rows(Path(root))
    return {
        str(row["oracle_name"]): _as_int(row.get("quantity", 0))
        for row in rows
        if row.get("currently_owned") and _as_int(row.get("quantity", 0)) > 0
    }


def _identity_from_inventory(row: dict[str, object]) -> CardIdentity:
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
                source_name="MTG_Kartensammlung_kanonisch_aktuell_2026-08-07.xlsx",
                source_path="drive:1_HlokwIebhVKCeQuDvVOpr3BZWYwgKBd",
                quality=DataQuality.PROJECT_VERIFIED,
                notes=(
                    "Physical identity and Oracle fields imported read-only; "
                    "semantic roles are inferred separately."
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
    # Cards with no conservative machine-identifiable function stay semantically unknown.
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
                "Structural-only keyword inference from the read-only canonical inventory Oracle text. "
                "Suitable for candidate screening, not Tactical Oracle or external-rules validation."
            ),
        }
    )


def _allowed_decks(identity: CardIdentity) -> tuple[str, ...]:
    card_colors = set(identity.color_identity)
    return tuple(deck_id for deck_id, colors in DECK_COLORS.items() if card_colors <= set(colors))


def _load_curated(root: Path) -> list[CandidateProfile]:
    path = root / "data/cards/phase5_upgrade_candidates.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [CandidateProfile.model_validate(item) for item in payload.get("candidates", [])]


def load_candidate_profiles(root: str | Path) -> dict[str, CandidateProfile]:
    root_path = Path(root)
    curated = _load_curated(root_path)
    curated_by_name = {candidate.card.oracle_name: candidate for candidate in curated}
    annotations = load_canonical_feature_annotations(root_path)
    candidates: dict[str, CandidateProfile] = {}

    for row in inventory_rows(root_path):
        if not row.get("currently_owned") or _as_int(row.get("quantity", 0)) <= 0:
            continue
        if str(row.get("commander_legality", "")).casefold() != "legal":
            continue
        name = str(row["oracle_name"])
        if name in BASIC_LANDS:
            continue
        identity = _identity_from_inventory(row)
        allowed = _allowed_decks(identity)
        if not allowed:
            continue
        curated_candidate = curated_by_name.get(name)
        if curated_candidate is not None:
            allowed = (
                tuple(deck for deck in allowed if deck in curated_candidate.allowed_deck_ids)
                or curated_candidate.allowed_deck_ids
            )
            candidate = curated_candidate.model_copy(
                update={
                    "allowed_deck_ids": allowed,
                    "physical_status": "canonical_inventory_verified_owned",
                    "notes": (curated_candidate.notes or "")
                    + " Reverified against canonical inventory 2026-08-07.",
                }
            )
        else:
            profile = _inferred_profile(identity)
            annotation = annotations.get(name)
            if profile is None and annotation is not None and annotation.mapped_roles:
                baseline = build_default_profile(identity)
                strengths = {role: 0.65 for role in annotation.mapped_roles}
                profile = baseline.model_copy(
                    update={
                        "roles": annotation.mapped_roles,
                        "role_strengths": strengths,
                        "source_quality": DataQuality.PROJECT_INFERRED,
                        "notes": (
                            "Conservative structural representation recovered from canonical "
                            "feature annotations. Numeric values remain neutral/default; this is "
                            "search evidence, not an objective card power score."
                        ),
                    }
                )
            if profile is None:
                continue
            candidate = CandidateProfile(
                candidate_id=f"inventory/{_slug(name)}",
                card=profile,
                allowed_deck_ids=allowed,
                physical_status="canonical_inventory_verified_owned",
                notes=(
                    "Owned and Commander-legal in canonical inventory 2026-08-07; card function is "
                    "structural-only keyword inference and requires "
                    "higher-fidelity validation before recommendation."
                ),
            )
        annotation = annotations.get(candidate.card.oracle_name)
        fused = fuse_canonical_features(candidate.card, annotation)
        fused = sanitize_structural_profile_semantics(
            fused, oracle_text=identity.oracle_text, type_line=identity.type_line
        )
        candidate = candidate.model_copy(update={"card": fused})
        candidates[candidate.candidate_id] = candidate

    # Preserve the historical curated candidates as a fallback if the canonical snapshot is
    # unavailable.
    if not candidates:
        return {candidate.candidate_id: candidate for candidate in curated}
    return candidates


def canonical_feature_fusion_summary(root: str | Path) -> dict[str, int]:
    candidates = load_candidate_profiles(root)
    rogshai = [
        candidate
        for candidate in candidates.values()
        if "rogshai/current" in candidate.allowed_deck_ids
    ]
    projected = [
        candidate
        for candidate in rogshai
        if any(
            source.source_type == "canonical_drive_derived_projection"
            for source in candidate.card.sources
        )
    ]
    return {
        "rogshai_candidates_loaded": len(rogshai),
        "canonical_overlay_candidates": len(projected),
        "heuristic_or_curated_without_overlay": len(rogshai) - len(projected),
    }
