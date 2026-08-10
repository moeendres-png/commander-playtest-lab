from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from commander_lab.engine.structural.profiles import build_default_profile
from commander_lab.models import (
    CandidateProfile,
    CardIdentity,
    Deck,
    DeckZone,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.storage import load_model, sha256_value
from commander_lab.tools.candidates import (
    BASIC_LANDS,
    _allowed_decks,
    _as_int,
    _identity_from_inventory,
    _inventory_rows,
    _slug,
    load_candidate_profiles,
)

ROGSHAI_DECK_ID = "rogshai/current"
ROGSHAI_COMMANDERS = (
    "Ishai, Ojutai Dragonspeaker",
    "Rograkh, Son of Rohgahh",
)
FRESH_ROGSHAI_PREFIX = "rogshai/fresh/"
K1_CANDIDATE_SHA256 = "43287c9d372c7d8ae5980f9ceea872fe55aa12e5af80cca2a9dec2e32946e39e"


@dataclass(frozen=True, slots=True)
class FreshRogShaiUniverse:
    """Bias-neutral RogShai construction universe.

    Candidate membership is derived only from owned quantity, Commander legality and
    Jeskai color identity. The current RogShai deck, protected-card metadata and
    optimizer/history artifacts are deliberately not inputs. Existing Korvold usage
    is represented only in ``available_quantities`` as a simultaneous physical
    buildability constraint.

    Cards without a structural profile remain present in ``candidate_names`` and
    ``review_required``. They are never assigned a synthetic quality score merely
    to make search convenient.
    """

    candidates: Mapping[str, CandidateProfile]
    review_required: Mapping[str, CardIdentity]
    candidate_names: frozenset[str]
    available_quantities: Mapping[str, int]
    verified_physical_names: frozenset[str]
    source_inventory_path: str
    data_snapshot_hash: str

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


def _fresh_inventory_rows(root: Path) -> list[dict[str, object]]:
    """Return the checked-in read-only inventory snapshot.

    Current K1 candidate membership is separately pinned and compared by acceptance
    tests. This function deliberately does not fabricate Drive deltas.
    """

    return _inventory_rows(root)


def _fresh_data_snapshot_hash(root: Path) -> str:
    manifest = json.loads((root / "data/decks/manifest.json").read_text(encoding="utf-8"))
    return sha256_value(
        {
            "base_data_snapshot_hash": str(manifest["data_snapshot_hash"]),
            "k1_rogshai_candidate_sha256": K1_CANDIDATE_SHA256,
        }
    )


def _korvold_nonbasic_reservations(root: Path) -> Counter[str]:
    """Return only the physical reservation needed for simultaneous Korvold buildability.

    Reading Korvold here is allowed because it is an availability constraint, not a
    RogShai quality prior. The RogShai current deck is intentionally never opened.
    """

    path = root / "data/decks/korvold_current.json"
    if not path.exists():
        return Counter()
    deck = load_model(path, Deck)
    reservations: Counter[str] = Counter()
    for entry in deck.cards:
        if entry.zone in {DeckZone.SIDEBOARD, DeckZone.MAYBEBOARD}:
            continue
        if entry.oracle_name in BASIC_LANDS:
            continue
        reservations[entry.oracle_name] += entry.quantity
    return reservations


def load_fresh_rogshai_universe(root: str | Path) -> FreshRogShaiUniverse:
    root_path = Path(root)
    rows = _fresh_inventory_rows(root_path)
    profiled = load_candidate_profiles(root_path)
    profiled_by_name = {candidate.card.oracle_name: candidate for candidate in profiled.values()}
    korvold_reserved = _korvold_nonbasic_reservations(root_path)

    candidates: dict[str, CandidateProfile] = {}
    review_required: dict[str, CardIdentity] = {}
    candidate_names: set[str] = set()
    available_quantities: dict[str, int] = {}

    for row in rows:
        if not row.get("currently_owned") or _as_int(row.get("quantity", 0)) <= 0:
            continue
        if str(row.get("commander_legality", "")).casefold() != "legal":
            continue
        identity = _identity_from_inventory(row)
        if ROGSHAI_DECK_ID not in _allowed_decks(identity):
            continue

        name = identity.oracle_name
        quantity = _as_int(row.get("quantity", 0))
        candidate_names.add(name)

        if name in BASIC_LANDS:
            available_quantities[name] = max(50, quantity)
        else:
            available_quantities[name] = max(0, quantity - korvold_reserved.get(name, 0))

        candidate = profiled_by_name.get(name)
        if candidate is not None:
            candidates[candidate.candidate_id] = candidate.model_copy(
                update={
                    "allowed_deck_ids": (ROGSHAI_DECK_ID,),
                    "physical_status": "fresh_rebuild_inventory_verified_owned",
                    "notes": (
                        (candidate.notes or "")
                        + " Fresh-rebuild membership is independent of current RogShai deck membership."
                    ).strip(),
                }
            )
            continue

        if name in BASIC_LANDS:
            profile = build_default_profile(identity)
            candidate_id = f"fresh/{_slug(name)}"
            candidates[candidate_id] = CandidateProfile(
                candidate_id=candidate_id,
                card=profile,
                allowed_deck_ids=(ROGSHAI_DECK_ID,),
                physical_status="fresh_rebuild_basic_land_policy",
                notes="Basic land admitted by project policy; not a quality prior.",
            )
            continue

        review_required[name] = identity

    verified = frozenset(name for name in candidate_names if available_quantities.get(name, 0) > 0)
    return FreshRogShaiUniverse(
        candidates=candidates,
        review_required=review_required,
        candidate_names=frozenset(candidate_names),
        available_quantities=available_quantities,
        verified_physical_names=verified,
        source_inventory_path="data/canonical_import/2026-08-07/inventory_snapshot.json",
        data_snapshot_hash=_fresh_data_snapshot_hash(root_path),
    )


def build_fresh_rogshai_profile(
    root: str | Path,
    mainboard_names: tuple[str, ...],
    *,
    variant_label: str = "candidate",
    profile_overrides: Mapping[str, StructuralCardProfile] | None = None,
    universe: FreshRogShaiUniverse | None = None,
) -> StructuralDeckProfile:
    """Materialize an arbitrary legal/physical 98-card RogShai mainboard for simulation.

    This is intentionally independent of ``rogshai_current.json``. Unknown structural
    semantics are a hard pre-simulation review gate, not an implicit bad/neutral score.
    """

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
        name for name, count in counts.items() if universe.available_quantities.get(name, 0) < count
    )
    if unavailable:
        raise ValueError(
            "simultaneous physical buildability failed after other active-deck reservations: "
            f"{unavailable}"
        )

    by_name = universe.candidate_by_name()
    unresolved = sorted(
        name
        for name in set(mainboard_names)
        if name in universe.review_required and name not in overrides
    )
    if unresolved:
        raise ValueError(f"mechanistic profile required before structural scoring/simulation: {unresolved}")

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

    identities = {
        str(row["oracle_name"]): _identity_from_inventory(row)
        for row in _fresh_inventory_rows(root_path)
        if str(row.get("oracle_name", "")) in ROGSHAI_COMMANDERS
    }
    missing_commanders = sorted(set(ROGSHAI_COMMANDERS) - set(identities))
    if missing_commanders:
        raise ValueError(
            f"commander identity missing from canonical inventory: {missing_commanders}"
        )
    cards.extend(build_default_profile(identities[name]) for name in ROGSHAI_COMMANDERS)

    snapshot_hash = universe.data_snapshot_hash
    deck_hash = sha256_value(
        {
            "mode": "fresh_rebuild",
            "commanders": ROGSHAI_COMMANDERS,
            "mainboard": sorted(counts.items()),
            "profile_override_names": sorted(overrides),
            "data_snapshot_hash": snapshot_hash,
        }
    )
    safe_label = "".join(ch for ch in variant_label.casefold() if ch.isalnum() or ch in {"-", "_"})[
        :32
    ]
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
