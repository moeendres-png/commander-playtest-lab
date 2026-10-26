"""Meta-Lane PR4: guardrail caps, meta floor, and game veto (design §5.1-§5.3).

Caps bound the weight of an external meta signal by source tier; the floor
bounds how far the meta deduction may push an objective; the veto records
that paired games overruled a package. No test here uses snapshots, games,
or collection data.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.models import (
    FormatBand,
    MetaCategory,
    MetaDeckSnapshot,
    MetaEvidenceRating,
    MetaKnowledgeBaseSnapshot,
    MetaPackage,
    MetaSnapshotManifest,
    MetaSource,
    MetaTier,
)
from commander_lab.whole_deck import (
    build_meta_functional_profile,
    functional_meta_distance,
    get_policy,
    profile_card_names,
    profile_structural_deck,
)
from commander_lab.whole_deck.meta import (
    META_TIER_WEIGHT_CAPS,
    capped_meta_weight,
    mark_package_vetoed,
    reference_source_tier,
    vetoed_package_ids,
)
from commander_lab.whole_deck.models import DeckDesignPolicy, PolicyId
from commander_lab.whole_deck.search_meta_score import _MetaScoreMixin, apply_meta_floor
from commander_lab.whole_deck.search_models import ManaBasePolicy

ROGSHAI = "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh"
WHOLE_DECK_META_SNAPSHOT_ID = "meta-2026-08-13-whole-deck-phase2-1"


def _nonzero_reference(repo_root: Path):
    """Candidate/reference pair with a nonzero meta distance (HIGH_POWER)."""
    decks = load_project_structural_decks(repo_root)
    current = decks["rogshai/current"]
    candidate = profile_structural_deck(current, format_band=FormatBand.HIGH_POWER)
    cards = tuple(card.oracle_name for card in current.cards if card.oracle_name != "Counterspell")
    profiles = {card.oracle_name: card for card in current.cards}
    reference = profile_card_names(
        cards,
        profiles,
        format_band=FormatBand.HIGH_POWER,
        source_snapshot_id="different",
        profile_id="different",
    )
    return candidate, reference


def _snapshot_with_tiers(pairs: tuple[tuple[str, MetaTier | None], ...]):
    """Minimal snapshot with one deck per (source_id, tier) pair."""
    sources = tuple(
        MetaSource(
            source_id=source_id,
            title=f"Source {source_id}",
            retrieved_at=datetime(2026, 10, 25, tzinfo=UTC),
            source_type="aggregator",
            categories=(MetaCategory.HIGH_POWER,),
            evidence_quality=MetaEvidenceRating.AGGREGATOR,
            tier=tier,
        )
        for source_id, tier in pairs
    )
    decks = tuple(
        MetaDeckSnapshot(
            source_id=source_id,
            commander="Test Commander",
            deck_hash=f"{index + 1:064x}",
            retrieved_at=datetime(2026, 10, 25, tzinfo=UTC),
            format_band=FormatBand.HIGH_POWER,
            categories=(MetaCategory.HIGH_POWER,),
            decklist=("Lightning Bolt",),
        )
        for index, (source_id, _tier) in enumerate(pairs)
    )
    return MetaKnowledgeBaseSnapshot(
        manifest=MetaSnapshotManifest(
            snapshot_id="test-pr4-1",
            created_at=datetime(2026, 10, 25, tzinfo=UTC),
            source_ids=tuple(source_id for source_id, _ in pairs),
            deck_hashes=tuple(deck.deck_hash for deck in decks),
            categories=(MetaCategory.HIGH_POWER,),
        ),
        sources=sources,
        deck_snapshots=decks,
    )


def _veto_snapshot() -> MetaKnowledgeBaseSnapshot:
    packages = (
        MetaPackage(
            package_id="pkg-a",
            name="A",
            cards=("Lightning Bolt",),
            roles=("removal",),
            categories=(MetaCategory.HIGH_POWER,),
        ),
        MetaPackage(
            package_id="pkg-b",
            name="B",
            cards=("Counterspell",),
            roles=("counter",),
            categories=(MetaCategory.HIGH_POWER,),
            vetoed_by_games=True,
        ),
    )
    return MetaKnowledgeBaseSnapshot(
        manifest=MetaSnapshotManifest(
            snapshot_id="test-pr4-veto",
            created_at=datetime(2026, 10, 25, tzinfo=UTC),
            source_ids=(),
            deck_hashes=(),
            categories=(MetaCategory.HIGH_POWER,),
        ),
        sources=(),
        deck_snapshots=(),
        packages=packages,
    )


def _objective_engine(utility: dict[str, float]) -> _MetaScoreMixin:
    """_objective without a search engine: only _utility/policy/mana used."""
    engine = _MetaScoreMixin.__new__(_MetaScoreMixin)
    engine._utility = dict(utility)
    engine.policy = DeckDesignPolicy(policy_id=PolicyId.OWNED_POOL_NEUTRAL)
    engine.mana_policy = ManaBasePolicy(
        preferred_land_minimum=0,
        preferred_land_maximum=0,
        hard_land_minimum=0,
        hard_land_maximum=0,
    )
    return engine


def test_tier_cap_table_matches_design() -> None:
    assert META_TIER_WEIGHT_CAPS == {
        MetaTier.A: 0.45,
        MetaTier.B: 0.30,
        MetaTier.C: 0.0,
    }


@pytest.mark.parametrize(
    ("weight", "tier", "expected"),
    [
        (0.20, MetaTier.B, 0.20),  # below cap: unchanged
        (0.30, MetaTier.B, 0.30),  # exactly at the cap: unchanged
        (0.31, MetaTier.B, 0.30),  # just above the cap: clamped
        (0.80, MetaTier.B, 0.30),
        (0.45, MetaTier.A, 0.45),  # exactly at the cap: unchanged
        (0.46, MetaTier.A, 0.45),  # just above the cap: clamped
        (0.80, MetaTier.A, 0.45),
        (1.0, MetaTier.A, 0.45),  # no tiered external prior runs at 1.0
        (0.80, MetaTier.C, 0.0),  # Tier C never enters scoring
        (0.0, MetaTier.C, 0.0),
        (1.0, None, 1.0),  # untiered legacy/internal: policy weight stands
        (0.80, None, 0.80),
    ],
)
def test_capped_meta_weight_boundaries(
    weight: float, tier: MetaTier | None, expected: float
) -> None:
    assert capped_meta_weight(weight, tier) == expected


def test_functional_meta_distance_tier_caps(repo_root: Path) -> None:
    candidate, reference = _nonzero_reference(repo_root)
    assert reference.source_tier is None  # candidate path carries no tier
    high = get_policy(PolicyId.META_HIGH)
    plain = functional_meta_distance(candidate, reference, policy=high)
    assert plain.raw_distance is not None and plain.raw_distance > 0
    assert plain.policy_weighted_distance == pytest.approx(plain.raw_distance * 0.80)
    tier_a = functional_meta_distance(candidate, reference, policy=high, source_tier=MetaTier.A)
    assert tier_a.raw_distance == plain.raw_distance  # caps weight only, not raw
    assert tier_a.policy_weighted_distance == pytest.approx(plain.raw_distance * 0.45)
    tier_b = functional_meta_distance(candidate, reference, policy=high, source_tier=MetaTier.B)
    assert tier_b.policy_weighted_distance == pytest.approx(plain.raw_distance * 0.30)
    tier_c = functional_meta_distance(candidate, reference, policy=high, source_tier=MetaTier.C)
    assert tier_c.policy_weighted_distance == 0.0
    no_tier = functional_meta_distance(candidate, reference, policy=high, source_tier=None)
    assert no_tier == plain


def test_functional_meta_distance_boundary_and_untiered_reservation(
    repo_root: Path,
) -> None:
    candidate, reference = _nonzero_reference(repo_root)
    medium = get_policy(PolicyId.META_MEDIUM)
    medium_plain = functional_meta_distance(candidate, reference, policy=medium)
    medium_a = functional_meta_distance(candidate, reference, policy=medium, source_tier=MetaTier.A)
    assert medium_a == medium_plain  # 0.45 weight sits exactly at the Tier-A cap
    feasible = get_policy(PolicyId.MAX_FEASIBLE_META_SHAPE)
    feasible_plain = functional_meta_distance(candidate, reference, policy=feasible)
    assert feasible_plain.raw_distance is not None
    assert feasible_plain.policy_weighted_distance == pytest.approx(
        feasible_plain.raw_distance * 1.0
    )
    feasible_a = functional_meta_distance(
        candidate, reference, policy=feasible, source_tier=MetaTier.A
    )
    assert feasible_a.policy_weighted_distance == pytest.approx(feasible_plain.raw_distance * 0.45)


def test_no_tier_no_change(repo_root: Path) -> None:
    """Without a tier, scoring is exactly as before PR4."""
    candidate, reference = _nonzero_reference(repo_root)
    for policy_id in (
        PolicyId.META_LIGHT,
        PolicyId.META_MEDIUM,
        PolicyId.META_HIGH,
        PolicyId.MAX_FEASIBLE_META_SHAPE,
    ):
        policy = get_policy(policy_id)
        assert functional_meta_distance(
            candidate, reference, policy=policy
        ) == functional_meta_distance(candidate, reference, policy=policy, source_tier=None)


def test_pinned_snapshot_reference_stays_untiered(repo_root: Path) -> None:
    """The production pinned snapshot (pre-PR1, no tiers) keeps full weight."""
    from commander_lab.engine.structural.profiles import StructuralProfileCatalog
    from commander_lab.meta.store import MetaKnowledgeBase

    profiles = {
        profile.oracle_name: profile
        for profile in StructuralProfileCatalog.from_json(
            repo_root / "data/cards/structural_role_profiles.json"
        ).profiles
    }
    snapshot = MetaKnowledgeBase(repo_root).load_snapshot(WHOLE_DECK_META_SNAPSHOT_ID)
    profile = build_meta_functional_profile(
        snapshot,
        commander=ROGSHAI,
        format_band=FormatBand.HIGH_POWER,
        profiles=profiles,
        now=datetime(2026, 10, 26, tzinfo=UTC),
    )
    assert profile.source_tier is None


def test_reference_source_tier_weakest_wins() -> None:
    snapshot_ab = _snapshot_with_tiers((("src-a", MetaTier.A), ("src-b", MetaTier.B)))
    assert reference_source_tier(snapshot_ab, snapshot_ab.deck_snapshots) == MetaTier.B
    assert reference_source_tier(snapshot_ab, snapshot_ab.deck_snapshots[:1]) == MetaTier.A
    snapshot_abc = _snapshot_with_tiers(
        (("src-a", MetaTier.A), ("src-b", MetaTier.B), ("src-c", MetaTier.C))
    )
    assert reference_source_tier(snapshot_abc, snapshot_abc.deck_snapshots) == MetaTier.C
    snapshot_none = _snapshot_with_tiers((("src-n", None),))
    assert reference_source_tier(snapshot_none, snapshot_none.deck_snapshots) is None


def test_build_meta_functional_profile_attaches_tier() -> None:
    snapshot = _snapshot_with_tiers((("src-a", MetaTier.A), ("src-b", MetaTier.B)))
    profile = build_meta_functional_profile(
        snapshot,
        commander="Test Commander",
        format_band=FormatBand.HIGH_POWER,
        profiles={},
        now=datetime(2026, 10, 26, tzinfo=UTC),
    )
    assert profile.source_tier == MetaTier.B
    assert profile.reference_deck_count == 2
    rebuilt = build_meta_functional_profile(
        snapshot,
        commander="Test Commander",
        format_band=FormatBand.HIGH_POWER,
        profiles={},
        now=datetime(2026, 10, 26, tzinfo=UTC),
    )
    assert rebuilt.profile_hash == profile.profile_hash


def test_apply_meta_floor() -> None:
    assert apply_meta_floor(5.0, 8.0) == 0.0  # domination floored at zero
    assert apply_meta_floor(5.0, 3.0) == 2.0  # normal deduction untouched
    assert apply_meta_floor(-2.0, 5.0) == -2.0  # already-negative: meta adds nothing
    assert apply_meta_floor(0.0, 5.0) == 0.0
    assert apply_meta_floor(5.0, 0.0) == 5.0
    assert apply_meta_floor(5.0, -1.0) == 5.0


def test_objective_meta_floor_and_no_change() -> None:
    engine = _objective_engine({"X": 100.0})
    assert engine._objective(("X",), {}, {}, {}) == 100.0
    assert engine._objective(("X",), {}, {}, {"high_power": 0.0}) == 100.0
    assert engine._objective(("X",), {}, {}, {"high_power": 0.5}) == 99.5
    assert engine._objective(("X",), {}, {}, {"high_power": 30.0}) == 70.0
    assert engine._objective(("X",), {}, {}, {"high_power": 1000.0}) == 0.0
    assert (
        engine._objective(("X",), {}, {}, {"high_power": 30.0, "normal_four_player": 40.0}) == 30.0
    )
    negative = _objective_engine({"X": -5.0})
    assert negative._objective(("X",), {}, {}, {}) == -5.0
    assert negative._objective(("X",), {}, {}, {"high_power": 1000.0}) == -5.0


def test_veto_path() -> None:
    snapshot = _veto_snapshot()
    assert vetoed_package_ids(snapshot) == {"pkg-b"}
    marked = mark_package_vetoed(snapshot, "pkg-a")
    assert vetoed_package_ids(marked) == {"pkg-a", "pkg-b"}
    assert vetoed_package_ids(snapshot) == {"pkg-b"}  # input unchanged
    assert mark_package_vetoed(marked, "pkg-a") == marked  # idempotent
    with pytest.raises(ValueError, match="unknown package_id"):
        mark_package_vetoed(snapshot, "pkg-zz")
