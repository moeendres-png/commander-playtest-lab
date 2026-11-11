"""Evidence source registry and research coverage specification for Commander Studio.

See docs/research/SOURCE_INVENTORY_AND_GAP_MATRIX.md and Issue #1185 (P0 Deliverable 1).
Defines the machine-readable inventory of external evidence sources, their strict
evidence layers, licensing terms, rate limits, bias characteristics, and coverage status.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, TypedDict

from .builder import ALL_DECKS, pool_cards
from .store import StudioStore, now_utc

SourceStatus = Literal["VERIFIED", "REVIEW", "UNAVAILABLE"]

EvidenceLayer = Literal[
    "FACT",
    "DERIVED_MECHANICAL",
    "OBSERVED_DECK",
    "OBSERVED_GAME",
    "COMBO_VERIFIED",
    "SIMULATED_RESULT",
    "MODELED",
    "EXTERNAL_OPINION",
]

CoverageGrade = Literal[
    "COMPLETE",
    "PARTIAL",
    "SPARSE",
    "UNOBSERVED_IN_CORPUS",
]


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """Systematic metadata record for one qualified evidence source (P0 Deliverable 1).

    Captures all 17 required governance, legal, technical and bias dimensions:
    source_id, priority (1..7), title, direct_url, reference_urls, publisher,
    retrieved_at_utc, observation_period, snapshot_id, schema_format, card_identifier,
    coverage_scope, evidence_layer, has_exact_numerator_denominator, game_context,
    double_counting_risk, license_terms, allowed_retrieval_method, reproducibility,
    bias_risks, status, and status_rationale.
    """

    source_id: str
    priority: int
    title: str
    direct_url: str
    reference_urls: tuple[str, ...]
    publisher: str
    retrieved_at_utc: str | None
    observation_period: str | None
    snapshot_id: str | None
    schema_format: str
    card_identifier: str
    coverage_scope: str
    evidence_layer: EvidenceLayer
    has_exact_numerator_denominator: bool
    game_context: dict[str, object]
    double_counting_risk: str
    license_terms: str
    allowed_retrieval_method: str
    reproducibility: str
    bias_risks: tuple[str, ...]
    status: SourceStatus
    status_rationale: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CardCoverageRecord:
    """Evidence gap and research priority record for one legal pool card."""

    oracle_id: str
    card_name: str
    mana_value: float
    color_identity: str
    type_line: str
    has_scryfall_facts: bool
    has_xmage_rules: bool
    corpus_hits: int
    corpus_denominator: int
    edhrec_hits: int | None
    edhrec_denominator: int | None
    edhrec_lift: float | None
    has_spellbook_combos: bool
    playgroup_observed_games: int | None
    tournament_hits: int | None
    coverage_grade: CoverageGrade
    research_priority_score: float
    is_long_tail_candidate: bool
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# ---------------------------------------------------------------------------
# The 7 Prioritized Sources (Qualified in Exact Priority Order 1..7)
# ---------------------------------------------------------------------------

QUALIFIED_SOURCES: tuple[EvidenceSource, ...] = (
    EvidenceSource(
        source_id="scryfall:bulk-oracle",
        priority=1,
        title="Scryfall Bulk Manifest & Oracle Cards",
        direct_url="https://api.scryfall.com/bulk-data",
        reference_urls=(
            "https://scryfall.com/docs/api",
            "https://scryfall.com/docs/faqs/i-m-having-trouble-accessing-the-scryfall-api-or-i-m-blocked-17",
        ),
        publisher="Scryfall, LLC",
        retrieved_at_utc="2026-11-10T00:00:00Z",
        observation_period="All released MTG sets through November 2026",
        snapshot_id="scryfall-oracle-cards-20261110",
        schema_format="JSON (Scryfall Bulk oracle_cards)",
        card_identifier="oracle_id",
        coverage_scope="100% of all MTG cards; 801 / 801 format- and color-legal Chulane cards",
        evidence_layer="FACT",
        has_exact_numerator_denominator=True,
        game_context={"format": "Commander", "pod_size": None, "commander": None},
        double_counting_risk="None; cards fold strictly 1:1 to canonical oracle_id across printings.",
        license_terms="Scryfall API Terms: free personal / non-commercial use with fan content attribution.",
        allowed_retrieval_method="Bulk GET (daily manifest, conditional ETag requests; no single-card polling loop).",
        reproducibility="DETERMINISTIC_OFFLINE_SNAPSHOT",
        bias_risks=(
            "Facts and mechanics, no evaluation of gameplay strength or deck fit",
            "Scryfall Tagger roles are subjective community classifications and not authoritative Oracle facts",
        ),
        status="VERIFIED",
        status_rationale=(
            "Fully verified daily bulk dataset imported into studio.sqlite3 (scryfall_card, 35,353 cards); "
            "covers 801 / 801 legal Chulane cards."
        ),
    ),
    EvidenceSource(
        source_id="playgroup:card-atlas",
        priority=2,
        title="Playgroup.gg Card Atlas & Gameplay Research",
        direct_url="https://playgroup.gg/cards",
        reference_urls=(
            "https://playgroup.gg/about",
            "https://playgroup.gg/research",
            "https://playgroup.gg/api-docs/index.html",
        ),
        publisher="Playgroup.gg",
        retrieved_at_utc=None,
        observation_period="Ongoing (Playgroup Live Sessions 2024-2026)",
        snapshot_id=None,
        schema_format="HTML / Web Application (proprietary)",
        card_identifier="card_name / slug",
        coverage_scope="Subset of cards actively cast in Playgroup Live games",
        evidence_layer="OBSERVED_GAME",
        has_exact_numerator_denominator=False,
        game_context={
            "format": "Commander Free-for-All",
            "pod_size": "mostly 4P",
            "power_level": "Casual / Mid-Power",
        },
        double_counting_risk=(
            "Pod clustering: repeated games by the same local playgroups skew frequencies; "
            "paper games tracked without digital card logging lack card events."
        ),
        license_terms=(
            "Aggregated statistics CC BY 4.0 with attribution; raw game events, client code "
            "and card graphics are proprietary and not licensed."
        ),
        allowed_retrieval_method="MANUAL_INSPECTION_ONLY (No public unauthenticated bulk export; automated scraping violates ToS).",
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Observed correlations are NOT causal proof of card efficacy",
            "Survivorship bias: drawn-to-played measures only cards drawn in surviving game states",
            "Pilot- and pod-clustering bias",
            "Missing long-tail coverage: cards with few live appearances remain completely unobserved",
        ),
        status="REVIEW",
        status_rationale=(
            "Methodology is valuable for metric definition (cast turn, drawn-to-played); "
            "automated data extraction is blocked by lack of open bulk API. Documented as gap."
        ),
    ),
    EvidenceSource(
        source_id="playgroup:chulane",
        priority=3,
        title="Playgroup.gg Chulane Commander Performance",
        direct_url="https://playgroup.gg/commanders/2143-chulane-teller-of-tales",
        reference_urls=(
            "https://playgroup.gg/about",
            "https://playgroup.gg/research",
        ),
        publisher="Playgroup.gg",
        retrieved_at_utc=None,
        observation_period="Aggregated live games through November 2026 (~2,094 recorded games)",
        snapshot_id=None,
        schema_format="HTML / Web Page",
        card_identifier="card_name",
        coverage_scope="Chulane cards with sufficient live appearances in Playgroup Live",
        evidence_layer="OBSERVED_GAME",
        has_exact_numerator_denominator=False,
        game_context={
            "commander": "Chulane, Teller of Tales",
            "format": "Commander Free-for-All",
            "pod_size": 4,
        },
        double_counting_risk="Repeated matches of the same deck/pilot combination in a recurring playgroup.",
        license_terms="CC BY 4.0 for aggregated statistics; no licensed raw data feed.",
        allowed_retrieval_method="MANUAL_INSPECTION_ONLY",
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Seat position skew: Seat 1 shows 45.3% winrate (674 games), Seat 5 shows 16.3% (43 games)",
            "Archetype skew: Playgroup Chulane population is heavily Landfall-focused",
            "Small sample sizes for non-staple cards (n < 30)",
        ),
        status="REVIEW",
        status_rationale=(
            "Chulane winrate (36%) and card lifts are documented, but lack open bulk export "
            "and carry heavy pilot/seat confounding. Gaps must remain explicit."
        ),
    ),
    EvidenceSource(
        source_id="edhrec:chulane",
        priority=4,
        title="EDHREC Chulane Recommendations & Relative Lift",
        direct_url="https://edhrec.com/commanders/chulane-teller-of-tales",
        reference_urls=(
            "https://edhrec.com/articles/changelog-replacing-synergy-with-lift-on-edhrecs-card-pages",
            "https://edhrec.com/guides/how-to-use-edhrec",
            "https://json.edhrec.com/pages/commanders/chulane-teller-of-tales.json",
        ),
        publisher="EDHREC (Space Cow Media / MTGGoldfish)",
        retrieved_at_utc="2026-11-11T12:55:00Z",
        observation_period="Two-year rolling window of online decklists (Archidekt, Moxfield)",
        snapshot_id="edhrec-chulane-20261111-20http",
        schema_format="JSON (EDHREC Web API / Cardlist JSON)",
        card_identifier="sanitized / Card Name (crosswalked to oracle_id)",
        coverage_scope="Top ~1,300 cards appearing in online Chulane decks; long-tail (<1%) omitted",
        evidence_layer="OBSERVED_DECK",
        has_exact_numerator_denominator=True,
        game_context={
            "commander": "Chulane, Teller of Tales",
            "color_identity": "WUG",
            "format": "Commander",
        },
        double_counting_risk=(
            "Thematic and budget subviews overlap with the main commander page; "
            "must never be summed across cohorts."
        ),
        license_terms="EDHREC Public API / Web usage: Non-commercial citation; rate limiting required.",
        allowed_retrieval_method="Polite GET with retry/backoff; conditional caching; respect robots.txt.",
        reproducibility="REPRODUCIBLE_API",
        bias_risks=(
            "Popularity bias: deckbuilding presence != gameplay strength or winrate",
            "Lift is relative deck co-occurrence, NOT winrate lift!",
            "Echo-chamber bias: popular precons and internet lists dominate builder selections",
        ),
        status="VERIFIED",
        status_rationale=(
            "20 fresh HTTP200 snapshots from 2026-11-11 are SHA-256 verified (Run #43024442970, Refs #1186). "
            "1,304 legacy rows remain explicitly qualified with retrieved_at_utc=NULL."
        ),
    ),
    EvidenceSource(
        source_id="spellbook:variants-api",
        priority=5,
        title="Commander Spellbook Combo Variants API",
        direct_url="https://backend.commanderspellbook.com/variants/",
        reference_urls=(
            "https://commanderspellbook.com/",
            "https://spacecowmedia.github.io/commander-spellbook-backend/index.html",
        ),
        publisher="Commander Spellbook (Space Cow Media / Community)",
        retrieved_at_utc="2026-11-11T14:00:00Z",
        observation_period="Current verified combo catalog (continuous)",
        snapshot_id="spellbook-backend-v1",
        schema_format="JSON REST API",
        card_identifier="oracle_name / Card Name",
        coverage_scope="All known and rule-verified MTG combos matching Chulane color identity (Bant / WUG)",
        evidence_layer="COMBO_VERIFIED",
        has_exact_numerator_denominator=True,
        game_context={
            "format": "Commander",
            "color_identity": "WUG",
            "commander": "Chulane, Teller of Tales",
        },
        double_counting_risk=(
            "Redundant combo variants (e.g. same loop with different bounce targets) "
            "must not be counted as independent strength claims."
        ),
        license_terms="MIT License (Backend) / CC BY 4.0 (Combo Dataset); completely open for free use.",
        allowed_retrieval_method="REST API GET (with commander filter); local caching; polite polling.",
        reproducibility="REPRODUCIBLE_API",
        bias_risks=(
            "Existence of a combo is NOT proof of consistency, speed, resilience or in-game winrate",
            "Complex 4+ piece combos are rarely executed in real games",
        ),
        status="VERIFIED",
        status_rationale=(
            "Fully open and licensed REST API. Adapter in src/commander_lab/commander_spellbook.py "
            "is verified and operational."
        ),
    ),
    EvidenceSource(
        source_id="active_drive:chulane-corpus-975",
        priority=6,
        title="ACTIVE-Drive Curated Chulane 99-Card Deck Corpus",
        direct_url="local:data/hub/03_MAINBOARD_99_COMPACT_*.jsonl",
        reference_urls=(
            "local:data/hub/01_DECK_CATALOG_994_SOURCES.csv",
            "docs/STUDIO_DECKBUILDER.md",
        ),
        publisher="Commander Studio ACTIVE Archive / Owner",
        retrieved_at_utc="2026-11-10T00:00:00Z",
        observation_period="Curated Chulane decklists 2024-2026",
        snapshot_id="active-hub-975-unique",
        schema_format="JSONL / CSV",
        card_identifier="oracle_id",
        coverage_scope="975 deduplicated full 99-card Chulane decks (429 observed, 372 unobserved cards in 801 pool)",
        evidence_layer="OBSERVED_DECK",
        has_exact_numerator_denominator=True,
        game_context={
            "commander": "Chulane, Teller of Tales",
            "deck_size": 99,
            "format": "Commander",
        },
        double_counting_risk="19 content duplicates in the 994 registered sources resolved to 975 unique decks.",
        license_terms="Local private project research data; strictly local under AGENTS.md §12.",
        allowed_retrieval_method="Local file import (SQLite / JSONL / CSV).",
        reproducibility="DETERMINISTIC_OFFLINE_SNAPSHOT",
        bias_risks=(
            "Corpus reflects historical collection choices and specific community deck sources",
            "Null-case trap: 372 pool cards have 0 hits, which means unobserved, never weak",
        ),
        status="VERIFIED",
        status_rationale=(
            "Fully imported into studio.sqlite3 (corpus_deck, corpus_deck_card) with "
            "deduplicated denominator N=975."
        ),
    ),
    EvidenceSource(
        source_id="tournament:cedh-meta",
        priority=7,
        title="cEDH Tournament Placement & Competitive Meta",
        direct_url="https://edhtop16.com/commander/Chulane,%20Teller%20of%20Tales",
        reference_urls=(
            "https://mtgtop8.com/",
            "https://topdeck.gg/",
        ),
        publisher="EDHTop16 / TopDeck.gg",
        retrieved_at_utc=None,
        observation_period="Competitive Commander (cEDH) Tournaments 2023-2026",
        snapshot_id=None,
        schema_format="JSON API / Web",
        card_identifier="card_name",
        coverage_scope="Top-16 tournament placements only",
        evidence_layer="EXTERNAL_OPINION",
        has_exact_numerator_denominator=False,
        game_context={
            "format": "Competitive Commander (cEDH)",
            "tournament_type": "Competitive REL",
            "pod_size": 4,
        },
        double_counting_risk="Same player entering sequential tournaments with minor card swaps.",
        license_terms="Terms of service vary; no automated scraping without license agreement.",
        allowed_retrieval_method="MANUAL_INSPECTION_ONLY (or authorized partner API).",
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Extreme selection bias: cEDH optimizes for turn 2-3 wins and fast mana incompatible with casual play",
            "Very low sample size for Chulane in current competitive tier lists",
        ),
        status="REVIEW",
        status_rationale=(
            "Valuable supplementary perspective, but requires manual audit due to cEDH "
            "selection divergence and non-bulk license terms."
        ),
    ),
    EvidenceSource(
        source_id="xmage:card-facts",
        priority=8,
        title="XMage Engine Card Facts & Rules Support",
        direct_url="local:data/cards/xmage_card_facts.json",
        reference_urls=(
            "https://github.com/magefree/mage",
            "src/commander_lab/deck_readiness.py",
        ),
        publisher="XMage Project / Commander Lab",
        retrieved_at_utc="2026-11-10T00:00:00Z",
        observation_period="All cards implemented in the canonical pinned XMage Rules Core (7,231 verified cards)",
        snapshot_id="xmage-card-facts-v1",
        schema_format="JSON (xmage_card_facts.json)",
        card_identifier="engine_name / oracle_name",
        coverage_scope="7,231 cards implemented in pinned XMage engine; 801 / 801 legal Chulane cards have verified readiness",
        evidence_layer="DERIVED_MECHANICAL",
        has_exact_numerator_denominator=True,
        game_context={
            "format": "Commander",
            "rules_engine": "XMage",
            "provider": "XMAGE",
        },
        double_counting_risk="None; card names map deterministically to engine implementations.",
        license_terms="GPLv3 / Open Source (XMage Engine Source)",
        allowed_retrieval_method="Local file import / repository asset.",
        reproducibility="DETERMINISTIC_OFFLINE_SNAPSHOT",
        bias_risks=(
            "Engine implementation coverage differs from full Oracle card universe",
            "Tactical card mechanics without external decision control fail closed",
        ),
        status="VERIFIED",
        status_rationale=(
            "100% verified locally against pinned engine rules. "
            "All 801 legal Chulane pool cards are qualified with sim_status=OK."
        ),
    ),
    EvidenceSource(
        source_id="scryfall:tagger",
        priority=9,
        title="Scryfall Tagger Functional Roles & Community Tags",
        direct_url="https://tagger.scryfall.com/",
        reference_urls=(
            "https://scryfall.com/docs/tagger-tags",
            "src/commander_lab/studio/roles.py",
        ),
        publisher="Scryfall Community / Tagger Project",
        retrieved_at_utc=None,
        observation_period="Continuous community tag catalog (2024-2026)",
        snapshot_id=None,
        schema_format="Web / Community Tagging (CSV export when available)",
        card_identifier="oracle_id / card_name",
        coverage_scope="Community functional tags: ramp, draw, removal, bounce, tutor, combo-piece",
        evidence_layer="EXTERNAL_OPINION",
        has_exact_numerator_denominator=False,
        game_context={
            "format": "Commander",
            "tagging_scope": "functional_card_roles",
        },
        double_counting_risk=(
            "Multiple overlapping tags for the same functional role "
            "(e.g. bounce-creature and bounce-permanent)."
        ),
        license_terms="Public Community Fan Content Policy; non-commercial citation only.",
        allowed_retrieval_method="MANUAL_INSPECTION_ONLY (or authorized Scryfall bulk tags export).",
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Community tags are subjective, non-authoritative annotations, not official MTG Oracle mechanics",
            "Inconsistent granularity across card types",
        ),
        status="REVIEW",
        status_rationale=(
            "Valuable semantic role mappings imported into card_role, "
            "but requires external audit due to community subjectivity."
        ),
    ),
)


def get_source(source_id: str) -> EvidenceSource:
    """Retrieve one qualified evidence source by its unique ID."""
    for source in QUALIFIED_SOURCES:
        if source.source_id == source_id:
            return source
    raise KeyError(f"Unknown evidence source: {source_id!r}")


def list_sources(*, status: SourceStatus | None = None) -> list[EvidenceSource]:
    """List qualified evidence sources, optionally filtered by qualification status."""
    if status is None:
        return list(QUALIFIED_SOURCES)
    return [s for s in QUALIFIED_SOURCES if s.status == status]


class SourceInventoryPayload(TypedDict):
    """Deliverable 1 machine-readable sources inventory structure."""

    schema_version: str
    description: str
    total_sources: int
    status_counts: dict[str, int]
    sources: list[dict[str, object]]


def source_inventory_payload(*, status: SourceStatus | None = None) -> SourceInventoryPayload:
    """Generate the Deliverable 1 machine-readable inventory payload, optionally filtered by status."""
    matched = list_sources(status=status)
    sources_data = [s.to_dict() for s in matched]
    verified_count = sum(1 for s in QUALIFIED_SOURCES if s.status == "VERIFIED")
    review_count = sum(1 for s in QUALIFIED_SOURCES if s.status == "REVIEW")
    unavailable_count = sum(1 for s in QUALIFIED_SOURCES if s.status == "UNAVAILABLE")

    return {
        "schema_version": "evidence-source-inventory-1.0.0",
        "description": "Systematic inventory of qualified evidence sources for Commander Studio (P0 Deliverable 1).",
        "total_sources": len(matched),
        "status_counts": {
            "VERIFIED": verified_count,
            "REVIEW": review_count,
            "UNAVAILABLE": unavailable_count,
        },
        "sources": sources_data,
    }


def write_source_inventory_json(path: str | Path, *, status: SourceStatus | None = None) -> Path:
    """Write the machine-readable sources register to disk."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = source_inventory_payload(status=status)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def load_spellbook_combo_cards(combos_path: str | Path | None = None) -> set[str]:
    """Load the set of card names participating in verified combos for Chulane."""
    target_path = Path(combos_path) if combos_path else Path("data/meta/spellbook_combos.json")
    if not target_path.is_file():
        return set()
    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    cards: set[str] = set()
    combos = data.get("combos")
    if not isinstance(combos, list):
        return set()
    for combo in combos:
        if isinstance(combo, dict) and "Chulane" in str(combo.get("commander", "")):
            combo_cards = combo.get("cards")
            if isinstance(combo_cards, list):
                for c in combo_cards:
                    if isinstance(c, str):
                        cards.add(c)
            any_groups = combo.get("any_of")
            if isinstance(any_groups, list):
                for any_group in any_groups:
                    if isinstance(any_group, list):
                        for c in any_group:
                            if isinstance(c, str):
                                cards.add(c)
    return cards


def calculate_card_coverage_record(
    card: dict[str, object],
    spellbook_combo_cards: set[str],
    corpus_denominator: int = 975,
) -> CardCoverageRecord:
    """Calculate the systematic coverage and long-tail metrics for one pool card."""
    name = str(card.get("name", ""))
    oracle_id = str(card.get("oracle_id") or card.get("card_id", ""))
    mana_value = float(card.get("mana_value") or 0.0)  # type: ignore[arg-type]
    color_identity = str(card.get("colors") or "")
    type_line = str(card.get("type_line") or "")
    group = str(card.get("group") or "")

    # Evidence indicators
    has_scryfall_facts = bool(card.get("has_image") or card.get("fact_source") == "scryfall")
    sim_status = str(card.get("sim_status") or "")
    has_xmage_rules = sim_status in {"OK", "READY"}

    decks = card.get("decks")
    corpus_hits = 0
    if isinstance(decks, dict):
        corpus_hits = int(decks.get(ALL_DECKS, 0))

    edhrec = card.get("edhrec")
    edhrec_hits: int | None = None
    edhrec_denominator: int | None = None
    edhrec_lift: float | None = None
    if isinstance(edhrec, dict):
        if edhrec.get("numerator") is not None:
            edhrec_hits = int(edhrec["numerator"])
        if edhrec.get("denominator") is not None:
            edhrec_denominator = int(edhrec["denominator"])
        if edhrec.get("pct") is not None:
            edhrec_lift = float(edhrec["pct"])

    has_spellbook_combos = name in spellbook_combo_cards
    playgroup_observed_games: int | None = None  # Documented blockade / no public export
    tournament_hits: int | None = None  # Documented blockade / no licensed cEDH bulk export

    # Coverage grade determination
    coverage_grade: CoverageGrade
    if corpus_hits == 0:
        coverage_grade = "UNOBSERVED_IN_CORPUS"
    elif corpus_hits <= 4:
        coverage_grade = "SPARSE"
    elif has_scryfall_facts and has_xmage_rules and corpus_hits >= 5 and edhrec_hits is not None:
        coverage_grade = "COMPLETE"
    else:
        coverage_grade = "PARTIAL"

    # Research priority score calculation: (1 - coverage) * relevance
    # 1. Coverage score [0.0, 1.0]
    coverage = 0.0
    if has_scryfall_facts:
        coverage += 0.20
    if has_xmage_rules:
        coverage += 0.20
    if corpus_hits >= 5:
        coverage += 0.30
    else:
        coverage += (corpus_hits / 5.0) * 0.30
    if edhrec_hits is not None:
        coverage += 0.20
    if has_spellbook_combos:
        coverage += 0.10
    coverage = min(1.0, coverage)

    # 2. Deck relevance score [0.0, 1.0]
    relevance = 0.15  # base relevance for format-legal card in store
    if group == "Creature":
        if mana_value <= 3.0:
            relevance += 0.35  # optimal Chulane cast trigger
        else:
            relevance += 0.15
    raw_roles = card.get("roles")
    roles = [str(r) for r in raw_roles] if isinstance(raw_roles, list) else []
    primary_synergies = {"bounce", "recast", "ramp", "draw", "mana-dork", "landfall"}
    if any(r in primary_synergies for r in roles):
        relevance += 0.30
    elif roles:
        relevance += 0.15
    if has_spellbook_combos:
        relevance += 0.20
    relevance = min(1.0, relevance)

    research_priority_score = round((1.0 - coverage) * relevance, 4)

    # Long-tail candidate detection
    is_long_tail_candidate = (corpus_hits <= 4) and (
        (group == "Creature" and mana_value <= 3.0) or bool(roles) or has_spellbook_combos
    )

    notes: str
    if is_long_tail_candidate:
        notes = (
            f"Long-tail candidate: {corpus_hits}/975 corpus hits with engine relevance "
            f"(group={group}, MV={mana_value:g}, roles={roles or 'none'})."
        )
    elif corpus_hits == 0:
        notes = "Unobserved in curated 975-deck corpus (0 hits != weak; missing observation)."
    else:
        notes = f"Corpus observed ({corpus_hits}/{corpus_denominator} hits)."

    return CardCoverageRecord(
        oracle_id=oracle_id,
        card_name=name,
        mana_value=mana_value,
        color_identity=color_identity,
        type_line=type_line,
        has_scryfall_facts=has_scryfall_facts,
        has_xmage_rules=has_xmage_rules,
        corpus_hits=corpus_hits,
        corpus_denominator=corpus_denominator,
        edhrec_hits=edhrec_hits,
        edhrec_denominator=edhrec_denominator,
        edhrec_lift=edhrec_lift,
        has_spellbook_combos=has_spellbook_combos,
        playgroup_observed_games=playgroup_observed_games,
        tournament_hits=tournament_hits,
        coverage_grade=coverage_grade,
        research_priority_score=research_priority_score,
        is_long_tail_candidate=is_long_tail_candidate,
        notes=notes,
    )


class PoolGapMatrixPayload(TypedDict):
    """Deliverable 2 machine-readable pool gap matrix structure."""

    schema_version: str
    description: str
    commander: str
    generated_at_utc: str
    total_cards: int
    corpus_denominator: int
    summary_counts: dict[str, object]
    cards: list[dict[str, object]]


def calculate_pool_gap_matrix(
    store: StudioStore,
    commander_names: Sequence[str] = ("Chulane, Teller of Tales",),
    combos_path: str | Path | None = None,
) -> PoolGapMatrixPayload:
    """Calculate the 801-card data gap matrix and research priority scores (P0 Deliverable 2)."""
    pool = pool_cards(store, commander_names)
    raw_cards = pool.get("cards", [])
    if not isinstance(raw_cards, list):
        raw_cards = []

    spellbook_cards = load_spellbook_combo_cards(combos_path)
    corpus_sizes = pool.get("cohorts", {})
    denominator = 975
    if isinstance(corpus_sizes, dict) and ALL_DECKS in corpus_sizes:
        denominator = int(corpus_sizes[ALL_DECKS])

    records: list[CardCoverageRecord] = []
    grade_counts: dict[str, int] = {
        "COMPLETE": 0,
        "PARTIAL": 0,
        "SPARSE": 0,
        "UNOBSERVED_IN_CORPUS": 0,
    }
    long_tail_count = 0
    unobserved_count = 0
    observed_count = 0
    has_edhrec_count = 0
    spellbook_combo_count = 0
    xmage_ready_count = 0

    for c in raw_cards:
        if isinstance(c, dict):
            rec = calculate_card_coverage_record(c, spellbook_cards, corpus_denominator=denominator)
            records.append(rec)
            grade_counts[rec.coverage_grade] = grade_counts.get(rec.coverage_grade, 0) + 1
            if rec.is_long_tail_candidate:
                long_tail_count += 1
            if rec.corpus_hits == 0:
                unobserved_count += 1
            else:
                observed_count += 1
            if rec.edhrec_hits is not None:
                has_edhrec_count += 1
            if rec.has_spellbook_combos:
                spellbook_combo_count += 1
            if rec.has_xmage_rules:
                xmage_ready_count += 1

    # Sort cards by research priority score descending, then by name
    records.sort(key=lambda r: (-r.research_priority_score, r.card_name))

    return {
        "schema_version": "pool-gap-matrix-1.0.0",
        "description": "Evidence gap and research priority matrix for format-legal pool cards (P0 Deliverable 2).",
        "commander": ", ".join(commander_names),
        "generated_at_utc": now_utc(),
        "total_cards": len(records),
        "corpus_denominator": denominator,
        "summary_counts": {
            "coverage_grades": grade_counts,
            "long_tail_candidates_count": long_tail_count,
            "unobserved_in_corpus_count": unobserved_count,
            "observed_in_corpus_count": observed_count,
            "has_edhrec_count": has_edhrec_count,
            "has_spellbook_combos_count": spellbook_combo_count,
            "xmage_ready_count": xmage_ready_count,
        },
        "cards": [r.to_dict() for r in records],
    }


class GapExampleReportPayload(TypedDict):
    """Deliverable 3 concrete example report structure."""

    schema_version: str
    description: str
    commander: str
    total_pool_cards: int
    corpus_denominator: int
    summary_counts: dict[str, object]
    examples_by_grade: dict[str, list[dict[str, object]]]


def generate_gap_example_report(
    matrix: PoolGapMatrixPayload,
    *,
    sample_size_per_grade: int = 2,
) -> GapExampleReportPayload:
    """Generate a concrete example report illustrating observed, sparse, partial and unobserved pool cards (P0 Deliverable 3)."""
    cards = matrix.get("cards", [])
    by_grade: dict[str, list[dict[str, object]]] = {
        "COMPLETE": [],
        "SPARSE": [],
        "PARTIAL": [],
        "UNOBSERVED_IN_CORPUS": [],
    }
    for c in cards:
        if isinstance(c, dict):
            grade = str(c.get("coverage_grade", ""))
            if grade in by_grade:
                by_grade[grade].append(c)

    examples: dict[str, list[dict[str, object]]] = {}
    for grade, grade_cards in by_grade.items():
        examples[grade] = grade_cards[:sample_size_per_grade]

    return {
        "schema_version": "gap-example-report-1.0.0",
        "description": "Representative examples of observed, sparse, partial and unobserved pool cards (P0 Deliverable 3).",
        "commander": str(matrix.get("commander", "")),
        "total_pool_cards": int(matrix.get("total_cards", 0)),
        "corpus_denominator": int(matrix.get("corpus_denominator", 975)),
        "summary_counts": matrix.get("summary_counts", {}),
        "examples_by_grade": examples,
    }


def write_gap_matrix_json(
    store: StudioStore,
    path: str | Path,
    commander_names: Sequence[str] = ("Chulane, Teller of Tales",),
    combos_path: str | Path | None = None,
    *,
    payload: PoolGapMatrixPayload | None = None,
) -> Path:
    """Calculate and write the 801-card gap matrix JSON to disk."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = calculate_pool_gap_matrix(store, commander_names, combos_path=combos_path)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path
