"""Evidence source registry and research coverage specification for Commander Studio.

See docs/research/SOURCE_INVENTORY_AND_GAP_MATRIX.md and Issue #1185 (P0 Deliverable 1).
Defines the machine-readable inventory of external evidence sources, their strict
evidence layers, licensing terms, rate limits, bias characteristics, and coverage status.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, TypedDict

from .builder import ALL_DECKS, pool_cards
from .store import StudioStore, now_utc

SourceStatus = Literal["VERIFIED", "REVIEW", "UNAVAILABLE"]

AccessStatus = Literal["ok", "ok_with_conditions", "unclear", "prohibited"]

ACCESS_STATUSES: tuple[AccessStatus, ...] = (
    "ok",
    "ok_with_conditions",
    "unclear",
    "prohibited",
)

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

    Captures governance, legal, technical, access, and bias dimensions:
    source_id, priority, title, direct_url, reference_urls, publisher,
    retrieved_at_utc, observation_period, snapshot_id, schema_format, card_identifier,
    coverage_scope, evidence_layer, has_exact_numerator_denominator, game_context,
    double_counting_risk, license_terms, allowed_retrieval_method, reproducibility,
    bias_risks, status (data quality), status_rationale, access_status (automated
    retrieval permission), access_evidence_url, and access_checked_at_utc (the date the
    terms were read; None for purely local sources, which have no terms to check).
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
    access_status: AccessStatus
    access_evidence_url: str
    access_checked_at_utc: str | None

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
    edhrec_inclusion_pct: float | None
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
# Qualified Sources (Data quality status separated from automated access status)
# ---------------------------------------------------------------------------

QUALIFIED_SOURCES: tuple[EvidenceSource, ...] = (
    EvidenceSource(
        source_id="scryfall:bulk-oracle",
        priority=1,
        title="Scryfall Bulk Manifest & Oracle Cards",
        direct_url="https://api.scryfall.com/bulk-data",
        reference_urls=(
            "https://scryfall.com/docs/api",
            "https://scryfall.com/docs/api/rate-limits",
            "https://scryfall.com/docs/api/bulk-data",
            "https://data.scryfall.io/robots.txt",
        ),
        publisher="Scryfall, LLC",
        retrieved_at_utc="2026-11-10T00:00:00Z",
        observation_period="All released MTG sets through November 2026",
        snapshot_id="scryfall-oracle-cards-20261110",
        schema_format="JSON (Scryfall Bulk oracle_cards)",
        card_identifier="oracle_id",
        coverage_scope=(
            "100% of all MTG cards; has_scryfall_facts 927 / 927 pool cards "
            "(gap matrix data/research/chulane_legal_pool_gap_matrix.json, generated 2026-11-12)"
        ),
        evidence_layer="FACT",
        has_exact_numerator_denominator=True,
        game_context={"format": "Commander", "pod_size": None, "commander": None},
        double_counting_risk="None; cards fold strictly 1:1 to canonical oracle_id across printings.",
        license_terms="Scryfall API Terms: free personal / non-commercial use with fan content attribution; no AI training.",
        allowed_retrieval_method=(
            "Bulk GET (daily manifest, conditional ETag requests; generic User-Agent and Accept "
            "headers required; strip price fields on write into scryfall_card; only for the TAM "
            "purchase view (#1637) the fields prices.eur, prices.eur_foil and cardmarket_id of a "
            "local bulk file go into the local store table tam_price_eur and its companion "
            "table, never committed; no single-card polling loop)."
        ),
        reproducibility="DETERMINISTIC_OFFLINE_SNAPSHOT",
        bias_risks=(
            "Facts and mechanics, no evaluation of gameplay strength or deck fit",
            "Scryfall Tagger roles are subjective community classifications and not authoritative Oracle facts",
        ),
        status="VERIFIED",
        status_rationale=(
            "Fully verified daily bulk dataset imported into studio.sqlite3 (scryfall_card, 35,353 cards); "
            "covers 927 / 927 pool cards of the gap matrix generated 2026-11-12 (pool size at "
            "other dates: unbekannt)."
        ),
        access_status="ok_with_conditions",
        access_evidence_url="https://scryfall.com/docs/api/rate-limits",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="playgroup:card-atlas",
        priority=2,
        title="Playgroup.gg Card Atlas & Gameplay Research",
        direct_url="https://playgroup.gg/cards",
        reference_urls=(
            "https://playgroup.gg/about",
            "https://playgroup.gg/research",
            "https://playgroup.gg/api/public/v1/openapi.yaml",
            "https://playgroup.gg/legal",
            "https://playgroup.gg/robots.txt",
        ),
        publisher="Playgroup.gg",
        retrieved_at_utc=None,
        observation_period="Ongoing (Playgroup Live Sessions 2024-2026)",
        snapshot_id=None,
        schema_format="Public REST API (commander stats) / HTML (/cards/...)",
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
            "Licence status ungeklärt, no legal review (docs/research/data_wave1_20261118/"
            "README.md section 4): the public OpenAPI description states CC BY 4.0 for aggregated "
            "statistics with attribution and link and permits bulk access; authenticated "
            "raw-games endpoint excluded."
        ),
        allowed_retrieval_method=(
            "Public API / HTML GET with recognizable generic User-Agent (400 req/min with UA, "
            "10 req/min without; max 20 requests/10 min per commander path; respect 429 Retry-After; "
            "attribution with link requested; the CC BY 4.0 licence claim is ungeklärt, no legal review)."
        ),
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Observed correlations are NOT causal proof of card efficacy",
            "Survivorship bias: drawn-to-played measures only cards drawn in surviving game states",
            "Pilot- and pod-clustering bias",
            "Missing long-tail coverage: cards with few live appearances remain completely unobserved",
        ),
        status="REVIEW",
        status_rationale=(
            "The public OpenAPI description permits bulk access with a generic User-Agent "
            "(licence CC BY 4.0 stated there, ungeklärt, no legal review); "
            "Card Atlas itself is HTML (/cards/...) with survivorship and pod-clustering biases, "
            "so data quality remains REVIEW."
        ),
        access_status="ok_with_conditions",
        access_evidence_url="https://playgroup.gg/api/public/v1/openapi.yaml",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="playgroup:chulane",
        priority=3,
        title="Playgroup.gg Chulane Commander Performance",
        direct_url="https://playgroup.gg/commanders/2143-chulane-teller-of-tales",
        reference_urls=(
            "https://playgroup.gg/about",
            "https://playgroup.gg/research",
            "https://playgroup.gg/api/public/v1/openapi.yaml",
            "https://playgroup.gg/legal",
        ),
        publisher="Playgroup.gg",
        retrieved_at_utc=None,
        observation_period=(
            "Aggregated live games, manual page inspection with state per the Phase-7 spec dated "
            "2026-11-08 (2,094 recorded games, provider figure, not recounted)"
        ),
        snapshot_id=None,
        schema_format="Public REST API / HTML Web Page",
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
        license_terms=(
            "Licence status ungeklärt, no legal review (docs/research/data_wave1_20261118/"
            "README.md section 4): the public OpenAPI description states CC BY 4.0 for aggregated "
            "commander statistics with attribution and link and permits bulk access."
        ),
        allowed_retrieval_method=(
            "Public API GET with recognizable generic User-Agent (400 req/min with UA, "
            "10 req/min without; max 20 requests/10 min per commander path; respect 429 Retry-After; "
            "attribution with link requested; the CC BY 4.0 licence claim is ungeklärt, no legal review)."
        ),
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Seat position skew (state 2026-11-08, provider figures): seat 1 45.3% in 674 games, "
            "seat 5 16.3% in 43 games (seats 5 and 6 were locked for Studio play until the Owner released them on 2026-11-22, register E16)",
            "Archetype skew: Playgroup Chulane population is heavily Landfall-focused",
            "Small sample sizes for non-staple cards (n < 30)",
        ),
        status="REVIEW",
        status_rationale=(
            "The public OpenAPI description permits bulk access with a generic User-Agent "
            "(licence CC BY 4.0 stated there, ungeklärt, no legal review). Provider-published "
            "Chulane win rate 36% (770 wins, 1,304 losses, 2,094 recorded games; the figures do not "
            "reconcile to one denominator, state per the Phase-7 spec dated 2026-11-08). Other "
            "counting methods, never mixed with it: data wave 1 commander list 449 / 1,111 rated "
            "seats (40.4%, retrieved 2026-11-18) and per-commander CSV 782 / 2,110 games (37%, "
            "retrieved 2026-11-11/12). Winrate and card lifts remain REVIEW due to heavy pilot, "
            "seat-position, and archetype confounding."
        ),
        access_status="ok_with_conditions",
        access_evidence_url="https://playgroup.gg/api/public/v1/openapi.yaml",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="edhrec:chulane",
        priority=4,
        title="EDHREC Chulane Recommendations & Relative Lift",
        direct_url="https://edhrec.com/commanders/chulane-teller-of-tales",
        reference_urls=(
            "https://edhrec.com/terms",
            "https://edhrec.com/robots.txt",
            "https://edhrec.com/articles/changelog-replacing-synergy-with-lift-on-edhrecs-card-pages",
            "https://edhrec.com/guides/how-to-use-edhrec",
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
        license_terms=(
            "EDHREC Terms of Service (effective 2024-08-06): personal non-commercial viewing only; "
            "automated queries, scripts, and downloading are prohibited; robots.txt disallows /deckpreview/."
        ),
        allowed_retrieval_method=(
            "PROHIBITED_AUTOMATED_RETRIEVAL (ToS effective 2024-08-06 prohibit automated queries/scripts; "
            "robots.txt disallows /deckpreview/; json.edhrec.com/robots.txt returns HTTP 403; "
            "historical snapshots only, no new automated fetches)."
        ),
        reproducibility="REPRODUCIBLE_API",
        bias_risks=(
            "Popularity bias: deckbuilding presence != gameplay strength or winrate",
            "Lift is relative deck co-occurrence, NOT winrate lift!",
            "Echo-chamber bias: popular precons and internet lists dominate builder selections",
        ),
        status="VERIFIED",
        status_rationale=(
            "Data quality VERIFIED for 20 SHA-256-verified historical snapshots from 2026-11-11 "
            "(Run #43024442970, Refs #1186; 1,304 legacy rows remain retrieved_at_utc=NULL). "
            "Automated retrieval is separately classified access_status=prohibited per ToS (2024-08-06). "
            "Stock usable unchanged per Owner decision #1557 point 1; no new automated retrievals "
            "without the operator's written permission."
        ),
        access_status="prohibited",
        access_evidence_url="https://edhrec.com/terms",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="spellbook:variants-api",
        priority=5,
        title="Commander Spellbook Combo Variants (Bulk Export)",
        direct_url="https://json.commanderspellbook.com/variants.json.gz",
        reference_urls=(
            "https://commanderspellbook.com/",
            "https://spacecowmedia.github.io/commander-spellbook-backend/api.html",
            "https://backend.commanderspellbook.com/robots.txt",
            "https://commanderspellbook.com/about/",
        ),
        publisher="Commander Spellbook (Space Cow Media / Community)",
        retrieved_at_utc="2026-11-11T14:00:00Z",
        observation_period="Current verified combo catalog (continuous)",
        snapshot_id="spellbook-backend-v1",
        schema_format="JSON Bulk (variants.json.gz) / JSON REST API (sparse only)",
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
        license_terms=(
            "MIT License (backend source code); combo dataset license unconfirmed on operator pages "
            "(attribution with link requested)."
        ),
        allowed_retrieval_method=(
            "Bulk GET via https://json.commanderspellbook.com/variants.json.gz (no full export via "
            "REST API; REST only for sparse unauthenticated requests at ~80 req/min respecting HTTP 429; "
            "backend.commanderspellbook.com/robots.txt disallows crawlers; strip price/salt fields)."
        ),
        reproducibility="REPRODUCIBLE_API",
        bias_risks=(
            "Existence of a combo is NOT proof of consistency, speed, resilience or in-game winrate",
            "Complex 4+ piece combos are rarely executed in real games",
        ),
        status="VERIFIED",
        status_rationale=(
            "Operator-recommended bulk export (variants.json.gz) for full combo data; REST API is "
            "sparse-only. Processed deterministically via scripts/spellbook_combos_fetch.py (bulk mode) "
            "and scripts/build_spellbook_shells.py."
        ),
        access_status="ok_with_conditions",
        access_evidence_url="https://spacecowmedia.github.io/commander-spellbook-backend/api.html",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="repo:chulane-corpus",
        priority=6,
        title="Curated Chulane 99-Card Deck Corpus (Repository Archive)",
        direct_url="local:data/research/chulane_corpus",
        reference_urls=(
            "local:data/research/chulane_corpus/README.md",
            "https://archidekt.com/terms",
            "docs/STUDIO_DECKBUILDER.md",
        ),
        publisher="Commander Studio repository archive (harvested from EDHREC and Archidekt)",
        retrieved_at_utc=None,
        observation_period=(
            "Public Chulane decklists harvested from EDHREC (2,300 classified + 7,528 unclassified) "
            "and Archidekt (723); first capture date unbekannt, last refresh 2026-11-15 "
            "(corpus README, issue #1388); EDHREC retrievals 2026-11-11 to 2026-11-15 (#1557). "
            "Decks that left EDHREC's rolling two-year window stay in the corpus."
        ),
        snapshot_id=None,
        schema_format="Per-deck normalized JSON (data/research/chulane_corpus/)",
        card_identifier="oracle_id",
        coverage_scope="Canonical Chulane decklist corpus in repository (10,551 raw / 10,150 deduplicated decks; initial 975-deck ACTIVE archive superseded)",
        evidence_layer="OBSERVED_DECK",
        has_exact_numerator_denominator=True,
        game_context={
            "commander": "Chulane, Teller of Tales",
            "deck_size": 99,
            "format": "Commander",
        },
        double_counting_risk="Content duplicates resolved via canonical oracle_id fingerprint at import time.",
        license_terms=(
            "Origin sources EDHREC (Terms of Service 2024-08-06) and Archidekt (Terms of Service "
            "2018-09-07) both prohibit automated retrieval (register status prohibited); stock "
            "usable per Owner decision #1557 (point 1: keep using the EDHREC stock, no new "
            "automated retrievals without written permission; point 2: no Archidekt scraping). "
            "Purchase/price signals excluded for Chulane (AGENTS.md §12)."
        ),
        allowed_retrieval_method=(
            "NO_NEW_HARVEST (origin sources prohibit automated retrieval, #1557). Stock is read "
            "from the repository by local import only (scripts/import_chulane_corpus.py)."
        ),
        reproducibility="UNKNOWN_NO_SNAPSHOT_RECORDED",
        bias_risks=(
            "Corpus reflects historical collection choices and specific community deck sources",
            "Null-case trap: unobserved pool cards (0 hits) mean unobserved, never weak",
        ),
        status="VERIFIED",
        status_rationale=(
            "Canonical Chulane decklist corpus stored in-repo under data/research/chulane_corpus/ "
            "(replaces historical non-existent local:data/hub/ reference) and imported into "
            "studio.sqlite3. Bestand nutzbar nach Owner-Entscheid #1557 (Punkt 1: EDHREC-Bestand "
            "weiter nutzen, keine neuen automatisierten Abrufe ohne schriftliche Erlaubnis; "
            "Punkt 2: Archidekt kein Scraping), Herkunft verbotene Quellen, keine Nachernte. "
            "No retrieval timestamp or snapshot id is recorded for the corpus as a whole, so "
            "both stay None (unbekannt)."
        ),
        access_status="prohibited",
        access_evidence_url="https://edhrec.com/terms",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="tournament:cedh-meta",
        priority=7,
        title="cEDH Tournament Placement & Competitive Meta",
        direct_url="https://edhtop16.com/commander/Chulane,%20Teller%20of%20Tales",
        reference_urls=(
            "https://edhtop16.com/terms",
            "https://topdeck.gg/developer-terms",
            "https://topdeck.gg/docs/tournaments-v2",
            "https://mtgtop8.com/",
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
        license_terms=(
            "EDHTop16 terms: API as-is, no excessive automated requests, no redistribution without "
            "permission, no documented rate limit; TopDeck.gg API v2 requires Owner API key, "
            "attribution with link, no scraping outside API, no storing player names."
        ),
        allowed_retrieval_method=(
            "EDHTop16: unclear (no documented rate limit, no automated retrieval built); TopDeck.gg: "
            "API v2 only with an Owner key (5/50/100 req/min by tier, attribution required, omit "
            "player names). Owner decision #1557 point 3: no TopDeck API key is created while no "
            "cEDH reference is wanted, so no TopDeck retrieval (scripts/collect_topdeck_decks.py "
            "stays closed without a key)."
        ),
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Extreme selection bias: cEDH optimizes for turn 2-3 wins and fast mana incompatible with casual play",
            "Very low sample size for Chulane in current competitive tier lists",
        ),
        status="REVIEW",
        status_rationale=(
            "Valuable supplementary perspective, but requires manual audit due to cEDH "
            "selection divergence and undocumented EDHTop16 rate limits. No TopDeck data is "
            "collected (Owner decision #1557 point 3: no API key)."
        ),
        access_status="unclear",
        access_evidence_url="https://edhtop16.com/terms",
        access_checked_at_utc="2026-11-18",
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
        retrieved_at_utc="2026-11-12T13:04:32Z",
        observation_period=(
            "XMage card repository export of 2026-11-12 (exported_at in data/cards/xmage_card_facts.json)"
        ),
        snapshot_id="xmage-card-facts-1.0.0-database-78c12c7d",
        schema_format="JSON (xmage_card_facts.json)",
        card_identifier="engine_name / oracle_name",
        coverage_scope=(
            "32,615 cards in the XMage card repository export (card_count in "
            "data/cards/xmage_card_facts.json); has_xmage_rules 807 / 927 pool cards "
            "(gap matrix generated 2026-11-12)"
        ),
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
            "Local engine card facts export (32,615 cards, exported 2026-11-12). Pool coverage: "
            "has_xmage_rules 807 / 927 pool cards per the gap matrix of 2026-11-12; the other 120 "
            "are not covered. A per-card sim_status is not recorded in this register (unbekannt)."
        ),
        access_status="ok",
        access_evidence_url="local:data/cards/xmage_card_facts.json",
        access_checked_at_utc=None,
    ),
    EvidenceSource(
        source_id="scryfall:tagger",
        priority=9,
        title="Scryfall Tagger Functional Roles & Oracle Tags Bulk",
        direct_url="https://tagger.scryfall.com/",
        reference_urls=(
            "https://scryfall.com/docs/api/bulk-data",
            "https://scryfall.com/docs/tagger-tags",
            "src/commander_lab/studio/roles.py",
        ),
        publisher="Scryfall, LLC / Scryfall Tagger Community",
        retrieved_at_utc=None,
        observation_period="Continuous community tag catalog (official Oracle Tags bulk)",
        snapshot_id=None,
        schema_format="JSONL Bulk (Scryfall Bulk oracle_tags, official bulk export)",
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
        license_terms="Scryfall API Terms: free non-commercial / research use with fan content attribution; official Oracle Tags bulk.",
        allowed_retrieval_method=(
            "Bulk GET via Scryfall Bulk Data API (type: oracle_tags) with generic User-Agent "
            "and Accept headers; no AI training."
        ),
        reproducibility="UNKNOWN_NO_SNAPSHOT_RECORDED",
        bias_risks=(
            "Community tags are subjective, non-authoritative annotations, not official MTG Oracle mechanics",
            "Inconsistent granularity across card types",
        ),
        status="REVIEW",
        status_rationale=(
            "Official Scryfall 'Oracle Tags' bulk export is accessible (access_status=ok_with_conditions, "
            "no longer blocked on license); data quality remains REVIEW due to community tag subjectivity."
        ),
        access_status="ok_with_conditions",
        access_evidence_url="https://scryfall.com/docs/api/bulk-data",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="archidekt:decks",
        priority=10,
        title="Archidekt Public Decklists",
        direct_url="https://archidekt.com/",
        reference_urls=(
            "https://archidekt.com/terms",
            "https://archidekt.com/robots.txt",
        ),
        publisher="Archidekt (Space Cow Media)",
        retrieved_at_utc=None,
        observation_period="Historical Chulane bracket decklists in local corpus (723 decks)",
        snapshot_id=None,
        schema_format="Web / Unofficial JSON",
        card_identifier="card_name / oracle_id",
        coverage_scope="Public Commander decklists with optional bracket metadata",
        evidence_layer="OBSERVED_DECK",
        has_exact_numerator_denominator=False,
        game_context={
            "format": "Commander",
            "commander": "Chulane, Teller of Tales",
        },
        double_counting_risk=(
            "Decks indexed by Archidekt overlap with EDHREC decklists; "
            "deduplicate by canonical oracle_id fingerprint."
        ),
        license_terms=(
            "Archidekt Terms of Service (effective 2018-09-07): same wording as EDHREC; "
            "personal use only, automated queries and scripts prohibited; no public API documentation."
        ),
        allowed_retrieval_method=(
            "PROHIBITED_AUTOMATED_RETRIEVAL (Terms of Service prohibit automated queries/scripts; "
            "no public API documentation)."
        ),
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Deckbuilding popularity != gameplay strength",
            "Self-reported bracket tags may be inconsistent across authors",
        ),
        status="UNAVAILABLE",
        status_rationale=(
            "No authorized automated retrieval path; Terms of Service (2018-09-07) prohibit "
            "automated queries with the same wording as EDHREC. Owner decision #1557 point 2: "
            "no scraping; the operator is asked, the rule-derived Game Changer band is the substitute."
        ),
        access_status="prohibited",
        access_evidence_url="https://archidekt.com/terms",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="moxfield:decks",
        priority=11,
        title="Moxfield Public Decklists",
        direct_url="https://www.moxfield.com/",
        reference_urls=(
            "https://api2.moxfield.com/robots.txt",
            "https://www.moxfield.com/terms",
        ),
        publisher="Moxfield",
        retrieved_at_utc=None,
        observation_period="Not directly harvested (blocked by robots.txt)",
        snapshot_id=None,
        schema_format="Web / Private API",
        card_identifier="card_name / scryfall_id",
        coverage_scope="Not collected directly; API host disallowed",
        evidence_layer="OBSERVED_DECK",
        has_exact_numerator_denominator=False,
        game_context={
            "format": "Commander",
            "commander": "Chulane, Teller of Tales",
        },
        double_counting_risk="Decks hosted on Moxfield overlap with EDHREC aggregations.",
        license_terms=(
            "api2.moxfield.com/robots.txt disallows all paths (User-agent: * / Disallow: /); "
            "moxfield.com/terms returns HTTP 403 to automated clients."
        ),
        allowed_retrieval_method=(
            "PROHIBITED_AUTOMATED_RETRIEVAL (api2.moxfield.com/robots.txt disallows all paths)."
        ),
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "Deckbuilding popularity != gameplay strength",
            "Direct automated access blocked",
        ),
        status="UNAVAILABLE",
        status_rationale=(
            "Automated access blocked: api2.moxfield.com/robots.txt disallows all paths "
            "for all user agents."
        ),
        access_status="prohibited",
        access_evidence_url="https://api2.moxfield.com/robots.txt",
        access_checked_at_utc="2026-11-18",
    ),
    EvidenceSource(
        source_id="cardmarket:price-guide",
        priority=12,
        title="Cardmarket Price Guide and Singles Product List (published downloads)",
        direct_url="https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json",
        reference_urls=(
            "https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_1.json",
            "https://www.cardmarket.com/robots.txt",
        ),
        publisher="Cardmarket",
        retrieved_at_utc=None,
        observation_period="Daily file; only a local copy on the Owner's computer, never committed",
        snapshot_id=None,
        schema_format="JSON (priceGuides: idProduct, avg, low, trend and -foil fields)",
        card_identifier="idProduct = cardmarket_id of the Scryfall printing",
        coverage_scope=(
            "Only the TAM purchase list (#1637, register entry 'Preise für TAM'): lowest low and "
            "trend per card over its playable printings; never evidence, rating, tier list, "
            "ranking, suggestion or simulation input"
        ),
        evidence_layer="EXTERNAL_OPINION",
        has_exact_numerator_denominator=False,
        game_context={
            "format": "Commander",
            "commander": "Tam, the Possibility (purchase list only; Chulane never)",
        },
        double_counting_risk="One price row per Cardmarket product; cards fold to oracle_id by minimum.",
        license_terms=(
            "Terms for automated retrieval not read (UNBELEGT); the files are published for "
            "download by Cardmarket; robots.txt carries a reservation of rights (EU 2019/790). "
            "Owner exception 2026-11-22: the risk (e.g. a block) lies with the Owner."
        ),
        allowed_retrieval_method=(
            "Owner command only (import-cardmarket-priceguide): one GET per file, a local copy "
            "younger than 24 hours is reused, honest User-Agent, no cookies, account, key, proxy "
            "or redirect; any status other than 200 stops. No page of www.cardmarket.com is read "
            "(no scraping); values only in the local Studio store, never committed."
        ),
        reproducibility="DYNAMIC_EPHEMERAL_WEB",
        bias_risks=(
            "low and trend are not filtered by seller country or condition (no DE/EX)",
            "low reflects one offer of any language or condition and swings on thin markets",
        ),
        status="REVIEW",
        status_rationale=(
            "Owner exception 2026-11-22 (register entry 'Preise für TAM'): allowed for the TAM "
            "purchase list only, as a labelled approximation; access status stays unclear until "
            "the terms are read."
        ),
        access_status="unclear",
        access_evidence_url="https://www.cardmarket.com/robots.txt",
        access_checked_at_utc="2026-11-22",
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
    access_status_counts: dict[str, int]
    sources: list[dict[str, object]]


def source_inventory_payload(*, status: SourceStatus | None = None) -> SourceInventoryPayload:
    """Generate the Deliverable 1 machine-readable inventory payload, optionally filtered by status."""
    matched = list_sources(status=status)
    sources_data = [s.to_dict() for s in matched]
    verified_count = sum(1 for s in QUALIFIED_SOURCES if s.status == "VERIFIED")
    review_count = sum(1 for s in QUALIFIED_SOURCES if s.status == "REVIEW")
    unavailable_count = sum(1 for s in QUALIFIED_SOURCES if s.status == "UNAVAILABLE")
    access_counts: dict[str, int] = {
        str(key): sum(1 for s in QUALIFIED_SOURCES if s.access_status == key)
        for key in ACCESS_STATUSES
    }

    return {
        "schema_version": "evidence-source-inventory-1.0.0",
        "description": "Systematic inventory of qualified evidence sources for Commander Studio (P0 Deliverable 1).",
        "total_sources": len(matched),
        "status_counts": {
            "VERIFIED": verified_count,
            "REVIEW": review_count,
            "UNAVAILABLE": unavailable_count,
        },
        "access_status_counts": access_counts,
        "sources": sources_data,
    }


def write_source_inventory_json(path: str | Path, *, status: SourceStatus | None = None) -> Path:
    """Write the machine-readable sources register to disk."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = source_inventory_payload(status=status)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


_COMBO_CARDS_MAX = 16
_combo_cards_lock = threading.Lock()
_combo_cards: dict[tuple[str, int, int, str], frozenset[str]] = {}


def load_spellbook_combo_cards(
    combos_path: str | Path | None = None, *, commander: str = "Chulane"
) -> set[str]:
    """Load the set of card names participating in verified combos listed for ``commander``
    (matched against the combo's ``commander`` field; another commander's combos never count).

    Read once per state of the file (path, size, modification time) and commander (#1563): the
    file is parsed again only when it changed. The caller gets its own set."""
    if not commander:
        return set()
    target_path = Path(combos_path) if combos_path else Path("data/meta/spellbook_combos.json")
    try:
        found = os.stat(target_path)
    except OSError:
        return set()
    if not stat.S_ISREG(found.st_mode):
        return set()
    key = (str(target_path.resolve()), found.st_size, found.st_mtime_ns, commander)
    with _combo_cards_lock:
        known = _combo_cards.get(key)
    if known is not None:
        return set(known)
    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()  # not remembered: a passing read error must not stick
    cards = frozenset(_combo_cards_of(data, commander))
    with _combo_cards_lock:
        if len(_combo_cards) >= _COMBO_CARDS_MAX:
            _combo_cards.clear()
        _combo_cards[key] = cards
    return set(cards)


def _combo_cards_of(data: dict[str, object], commander: str) -> set[str]:
    cards: set[str] = set()
    combos = data.get("combos")
    if not isinstance(combos, list):
        return cards
    for combo in combos:
        if isinstance(combo, dict) and commander in str(combo.get("commander", "")):
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


def load_spellbook_combo_partners(
    combos_path: str | Path | None = None, *, commander: str = "Chulane"
) -> dict[str, set[str]]:
    """Combo partners per card from the verified combos listed for ``commander``:
    ``{casefolded card name: {casefolded partner names}}``. The commander matching is
    the one of ``load_spellbook_combo_cards`` (the combo's ``commander`` field must
    name the commander), so another commander's combos never mark a pair."""
    partners: dict[str, set[str]] = {}
    if not commander:
        return partners
    target_path = Path(combos_path) if combos_path else Path("data/meta/spellbook_combos.json")
    if not target_path.is_file():
        return partners
    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return partners
    combos = data.get("combos")
    if not isinstance(combos, list):
        return partners
    for combo in combos:
        if not isinstance(combo, dict) or commander not in str(combo.get("commander", "")):
            continue
        names: set[str] = set()
        combo_cards = combo.get("cards")
        if isinstance(combo_cards, list):
            names.update(c for c in combo_cards if isinstance(c, str))
        any_groups = combo.get("any_of")
        if isinstance(any_groups, list):
            for any_group in any_groups:
                if isinstance(any_group, list):
                    names.update(c for c in any_group if isinstance(c, str))
        for name in names:
            partners.setdefault(name.casefold(), set()).update(
                other.casefold() for other in names if other != name
            )
    return partners


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
    edhrec_inclusion_pct: float | None = None
    if isinstance(edhrec, dict):
        if edhrec.get("numerator") is not None:
            edhrec_hits = int(edhrec["numerator"])
        if edhrec.get("denominator") is not None:
            edhrec_denominator = int(edhrec["denominator"])
        if edhrec.get("pct") is not None:
            edhrec_inclusion_pct = float(edhrec["pct"])

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
            f"Long-tail candidate: {corpus_hits}/{corpus_denominator} corpus hits with engine relevance "
            f"(group={group}, MV={mana_value:g}, roles={roles or 'none'})."
        )
    elif corpus_hits == 0:
        notes = (
            f"Unobserved in curated {corpus_denominator}-deck corpus "
            "(0 hits != weak; missing observation)."
        )
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
        edhrec_inclusion_pct=edhrec_inclusion_pct,
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
    """Calculate the 927-card data gap matrix and research priority scores (P0 Deliverable 2).

    Per-card evidence grades against the legacy corpus cohort (``ALL_DECKS``) as denominator, for
    research prioritisation. The deck-frequency class counts over the deduplicated local deck-list
    universe (counts only, own denominator per universe) are a different matrix:
    ``gap_matrix.build_gap_matrix``; see its module docstring for why the two are not merged."""
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
        "schema_version": "pool-gap-matrix-1.1.0",
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
    """Calculate and write the 927-card gap matrix JSON to disk."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = calculate_pool_gap_matrix(store, commander_names, combos_path=combos_path)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path
