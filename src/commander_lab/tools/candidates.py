from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

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

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
DECK_COLORS: dict[str, frozenset[Color]] = {
    "korvold/current": frozenset({Color.BLACK, Color.RED, Color.GREEN}),
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


def _inventory_rows(root: Path) -> list[dict[str, object]]:
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
    path = Path(root) / "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(name): int(quantity) for name, quantity in payload.get("cards", {}).items()}


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
    rows = _inventory_rows(Path(root))
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
    text = (identity.oracle_text or "").casefold()
    type_line = identity.type_line.casefold()
    roles: set[CardRole] = set()

    is_land = "land" in type_line or identity.is_basic_land
    if is_land:
        roles.add(CardRole.MANA_SOURCE)

    if (
        ("add {" in text and not is_land)
        or "treasure token" in text
        or ("search your library for" in text and "land card" in text)
        or ("put a land card" in text and "battlefield" in text)
    ):
        roles.add(CardRole.RAMP)
    if (
        "draw a card" in text
        or "draw two cards" in text
        or "draw three cards" in text
        or "draw x cards" in text
    ):
        roles.add(CardRole.DRAW)
    if any(
        token in text
        for token in ("scry ", "surveil ", "look at the top", "look at the top ", "reveal the top")
    ):
        roles.add(CardRole.SELECTION)
    if any(
        token in text
        for token in (
            "destroy target",
            "exile target",
            "return target creature",
            "return target nonland permanent",
            "return target permanent",
            "target creature gets -",
            "deals damage to target creature",
            "damage to target creature or planeswalker",
        )
    ):
        roles.add(CardRole.REMOVAL)
    if (
        "counter target spell" in text
        or "counter target activated" in text
        or "counter target triggered" in text
    ):
        roles.add(CardRole.COUNTER)
    if any(
        token in text
        for token in (
            "gains hexproof",
            "gain hexproof",
            "gains indestructible",
            "gain indestructible",
            "phases out",
            "phase out",
            "protection from",
            "can't be countered",
        )
    ):
        roles.add(CardRole.PROTECTION)
    if any(
        token in text
        for token in (
            "destroy all creatures",
            "exile all creatures",
            "destroy all nonland permanents",
            "exile all nonland permanents",
            "all creatures get -",
            "each creature gets -",
            "damage to each creature",
            "destroy all artifacts",
            "destroy all enchantments",
        )
    ):
        roles.add(CardRole.WIPE)
    if any(
        token in text
        for token in (
            "from your graveyard to your hand",
            "from your graveyard to the battlefield",
            "return target card from your graveyard",
            "return target creature card from your graveyard",
            "play lands from your graveyard",
            "cast spells from your graveyard",
        )
    ):
        roles.add(CardRole.RECURSION)
    if any(
        token in text
        for token in (
            "exile target card from a graveyard",
            "exile all cards from target player's graveyard",
            "exile all graveyards",
            "cards in graveyards",
            "from opponents' graveyards",
        )
    ):
        roles.add(CardRole.GRAVEYARD_HATE)
    if "create " in text and " token" in text:
        roles.add(CardRole.TOKEN_SOURCE)
    if (
        re.search(r"sacrifice (?:a|an|another|one|two|three|x) ", text)
        or "sacrifice a permanent:" in text
    ):
        roles.add(CardRole.SACRIFICE_OUTLET)
    if any(
        token in text
        for token in (
            "landfall",
            "whenever a land enters",
            "whenever one or more lands enter",
            "land card from your graveyard",
            "play an additional land",
            "lands you control",
            "sacrifice a land",
        )
    ):
        roles.add(CardRole.LAND_SYNERGY)
    if any(
        token in text
        for token in (
            "double strike",
            "combat damage to a player",
            "combat damage to an opponent",
            "can't be blocked",
            "additional combat phase",
            "extra combat phase",
        )
    ):
        roles.add(CardRole.COMBAT_PAYOFF)
    if any(
        token in text
        for token in (
            "each opponent loses",
            "damage to each opponent",
            "deals damage to each opponent",
            "you win the game",
        )
    ):
        roles.update({CardRole.PAYOFF, CardRole.FINISHER})
    if "whenever" in text and roles.intersection(
        {
            CardRole.DRAW,
            CardRole.RAMP,
            CardRole.TOKEN_SOURCE,
            CardRole.PAYOFF,
            CardRole.LAND_SYNERGY,
        }
    ):
        roles.add(CardRole.ENGINE)
    if roles.intersection(
        {CardRole.TOKEN_SOURCE, CardRole.SACRIFICE_OUTLET, CardRole.LAND_SYNERGY, CardRole.RAMP}
    ):
        roles.add(CardRole.ENABLER)
    if "whenever" in text and any(
        token in text for token in ("loses life", "deals damage", "+1/+1 counter")
    ):
        roles.add(CardRole.PAYOFF)
    if not roles:
        roles.add(CardRole.ENABLER)
    return frozenset(roles)


def _produced_colors(identity: CardIdentity) -> frozenset[Color]:
    text = identity.oracle_text or ""
    produced = {
        Color(symbol) for symbol in "WUBRG" if f"{{{symbol}}}" in text and "add" in text.casefold()
    }
    type_line = identity.type_line.casefold()
    for subtype, color in (
        ("plains", Color.WHITE),
        ("island", Color.BLUE),
        ("swamp", Color.BLACK),
        ("mountain", Color.RED),
        ("forest", Color.GREEN),
    ):
        if subtype in type_line:
            produced.add(color)
    return frozenset(produced)


def _inferred_profile(identity: CardIdentity) -> StructuralCardProfile | None:
    baseline = build_default_profile(identity)
    roles = _inferred_roles(identity)
    # Cards with no machine-identifiable function are not admitted to automatic structural
    # screening.
    if roles == frozenset({CardRole.ENABLER}) and baseline.roles == frozenset({CardRole.ENABLER}):
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
    candidates: dict[str, CandidateProfile] = {}

    for row in _inventory_rows(root_path):
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
        candidates[candidate.candidate_id] = candidate

    # Preserve the historical curated candidates as a fallback if the canonical snapshot is
    # unavailable.
    if not candidates:
        return {candidate.candidate_id: candidate for candidate in curated}
    return candidates
