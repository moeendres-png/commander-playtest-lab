"""Documentation models of the six remembered read routes (#1615 point 5).

Since #1563/#1609 these routes return the remembered JSON bytes as a plain ``Response``
(``answer_cache.json_answer``), so FastAPI no longer derived a response schema for them. The
models below describe the JSON each route sends and are handed to FastAPI through
``responses={200: {"model": ...}}`` only: they never serialise or validate an answer, the
handler keeps returning the prebuilt bytes, so no response byte depends on them.

Each model follows the builder that fills the answer (``builder.pool_cards``,
``evidence.pool_evidence``, ``roles.role_origin_audit``, ``similar_decks.browse_decks``,
``corpus_audit.corpus_audit``, ``universe_choice.counted_universes``). Where the builder's
shape is dynamic (the keys of a cohort map, the rows of a layer that differ per kind) the field
is an object map, never an invented set of fields. ``extra="forbid"`` makes a test that
validates a real answer against its model fail on a key the model does not name.

Optional variant fields declared with ``| None = None`` are omitted from the JSON in inactive
variants and are never sent as ``null``; round-trip checks serialize with ``exclude_unset=True``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Shape(BaseModel):
    """Base shape for documented route answers.

    Variant fields (``| None = None``) are absent in inactive variants, never serialized as
    ``null`` (``exclude_unset=True``).
    """

    model_config = ConfigDict(extra="forbid")


class CorpusBinding(_Shape):
    commander: list[str]
    bound_decks: int
    other_commander_decks: int
    unbound_decks: int


class SimReadiness(_Shape):
    available: bool
    ready: int
    total: int
    by_status: dict[str, int]


class EdhrecEntry(_Shape):
    page: str
    pct: float | None
    numerator: int | None
    denominator: int | None
    origin: str


class PlaygroupEntry(_Shape):
    live_inclusion_pct: float | None
    median_cast_turn: float | None
    winrate_when_cast_pct: float | None
    observed_winrate_gap_pp: float | None
    ci_95_lower_pp: float | None
    ci_95_upper_pp: float | None
    conservative_ranking_indicator: str | None
    status: str
    times_brought: int | None
    winrate_when_cast_n: int | None
    insufficient_sample: bool


class SignalFigure(_Shape):
    value: float
    numerator: int | None
    denominator: int | None


class CountedFigure(_Shape):
    hits: int
    denominator: int
    share: float


class UniverseFigure(_Shape):
    matched: bool
    hits: int | None
    denominator: int | None
    share: float | None
    reason: str | None
    filter_card: bool


class PoolCard(_Shape):
    card_id: str
    oracle_id: str | None
    name: str
    names_de: list[str] | None
    mana_cost: str
    mana_value: float | None
    type_line: str
    group: str
    text: str
    keywords: list[str]
    colors: str
    power: str | None
    toughness: str | None
    basic: bool
    produced_mana: str
    edhrec_rank: int | None
    game_changer: bool
    has_back: bool
    has_image: bool
    image_url_front: str | None
    image_url_back: str | None
    fact_source: str
    sim_status: str
    owned: int
    available: int
    reserved: int
    favorite: bool
    excluded: bool
    note: str
    labels: list[str]
    roles: list[str]
    decks: dict[str, int]
    decks_known: bool
    edhrec: EdhrecEntry | None
    signals: dict[str, SignalFigure]
    playgroup: PlaygroupEntry | None
    # only with include_unowned (#1648)
    in_collection: bool | None = None
    wishlist_candidate: bool | None = None
    selected_by: list[str] | None = None
    # only with a counted universe or a universe profile / game-changer band
    counted: CountedFigure | None = None
    universe: UniverseFigure | None = None


class PoolAnswer(_Shape):
    """``GET /api/pool``: the pool of the asked commander(s) with everything the builder shows."""

    commander_ids: list[str]
    german_names_available: bool
    identity: str
    cohorts: dict[str, int]
    corpus_binding: CorpusBinding
    small_denominator: int
    roles: list[str]
    sim_readiness: SimReadiness
    cards: list[PoolCard]
    # only with include_unowned
    sim_readiness_unowned: SimReadiness | None = None
    include_unowned: bool | None = None
    unowned_selection: dict[str, object] | None = None
    # only when a counted universe was chosen, or with a profile / gc_band
    counted_universe: dict[str, object] | None = None
    universe: dict[str, object] | None = None


class TierPolicy(_Shape):
    version: str
    tiers: list[str]
    validated_model: str | None
    rule: str
    never_inputs: list[str]


class EvidenceRating(_Shape):
    status: str
    tier: str | None
    reason: str
    model_version: str | None


class RoleClaim(_Shape):
    role: str
    origin: str
    original_tag: str | None
    mapping_rule: str | None


class MechanicalFeature(_Shape):
    feature: str
    holds: bool
    rule: str


class FactLayer(_Shape):
    status: str
    data_class: str
    mana_value: float | None
    colors: str
    type_line: str
    fact_source: str
    rules_version: str
    features: list[MechanicalFeature]
    roles: list[RoleClaim]


class DeckLayer(_Shape):
    status: str
    # kinds differ (edhrec_rank_global, corpus), so each item is an object
    items: list[dict[str, object]]
    edhrec: dict[str, object] | None
    cohorts_overlap_never_add: bool


class GameLayer(_Shape):
    status: str
    rows: int
    atlas: PlaygroupEntry | None
    population: str
    data_class: str
    note: str


class ComboLayer(_Shape):
    status: str
    data_class: str
    note: str | None = None  # absent in the global view


class SimulatedLayer(_Shape):
    status: str
    data_class: str
    # the three below exist only in the commander view
    grouping: str | None = None
    group_count: int | None = None
    groups: list[dict[str, object]] | None = None


class EvidenceLayers(_Shape):
    fact: FactLayer
    observed_deck: DeckLayer
    observed_game: GameLayer
    combo_verified: ComboLayer
    simulated_result: SimulatedLayer


class ResearchPriority(_Shape):
    score: float | None
    data_class: str
    long_tail: bool


class EvidenceCoverage(_Shape):
    present: list[str]
    missing: list[str]
    needs: list[str]
    gap_grade: str | None
    research_priority: ResearchPriority | None


class EvidenceCard(_Shape):
    card_id: str
    name: str
    oracle_id: str | None
    mana_value: float | None
    type_line: str
    text: str
    keywords: list[str]
    group: str
    colors: str
    has_image: bool
    has_back: bool
    image_url_front: str | None
    image_url_back: str | None
    available: int
    rating: EvidenceRating
    layers: EvidenceLayers
    coverage: EvidenceCoverage


class EvidenceSummary(_Shape):
    cards: int
    unrated: int
    layer_status: dict[str, dict[str, int]]


class EvidenceAnswer(_Shape):
    """``GET /api/evidence``: evidence per pool card; every card is UNRATED."""

    schema_: str = Field(alias="schema")
    view: str
    commander: list[str]
    tier_policy: TierPolicy
    cohorts: dict[str, int]
    corpus_binding: CorpusBinding
    small_denominator: int
    summary: EvidenceSummary
    cards: list[EvidenceCard]


class RoleRow(_Shape):
    role: str
    tagger_total: int
    oracle_total: int
    both: int
    tagger_only: int
    oracle_only: int
    oracle_confirmed_share: float | None
    # only with a commander (the pool-scoped figures)
    pool_count: int | None = None
    pool_total: int | None = None
    pool_share: float | None = None
    pool_tagger_total: int | None = None
    pool_oracle_total: int | None = None
    pool_both: int | None = None
    pool_tagger_only: int | None = None
    pool_oracle_only: int | None = None


class RoleAuditAnswer(_Shape):
    """``GET /api/roles/audit``: tagger claims against Oracle-text claims, counts only."""

    claims_by_origin: dict[str, int]
    roles: list[RoleRow]
    # only with a commander
    commander: str | None = None
    pool_claims_by_origin: dict[str, int] | None = None
    pool_total: int | None = None
    pool_tagged: int | None = None
    pool_untagged: int | None = None
    pool_coverage_share: float | None = None
    per_role_pool_counts: dict[str, int] | None = None


class CountedUniverseItem(_Shape):
    """One element of ``GET /api/universe/counted`` (the answer is a list of these)."""

    signal: str
    value: str
    source: str
    bracket: str
    denominator: int
    snapshot_id: str
    rows: int
    label: str
    short_label: str
    unmatched_rows: int
    unmatched_examples: list[str]
    notice: str


class DeckBrowserFilters(_Shape):
    commander: str
    q: str
    origin: str
    cohort: str
    label: str
    must_contain: list[str]
    must_not_contain: list[str]
    include_unowned: bool


class DeckBrowserOrigins(_Shape):
    source: int
    saved: int


class BrowserDeck(_Shape):
    id: str
    deck_id: str
    branch: str | None
    revision_id: str | None
    origin: str
    name: str
    commander: str
    cohort: str
    bracket: str | None
    platform: str
    url: str
    deck_date: str | None
    labels: list[str]
    cards: int


class CooccurrenceCard(_Shape):
    card_id: str | None
    name: str
    decks: int
    of: int
    share: float
    owned: int
    available: int
    in_collection: bool


class DeckBrowserAnswer(_Shape):
    """``GET /api/deck-browser``: filtered decks and card co-occurrence (n/N)."""

    total_decks: int
    origin_counts: DeckBrowserOrigins
    small_sample: bool
    small_denominator: int
    filters: DeckBrowserFilters
    decks: list[BrowserDeck]
    cooccurrence: list[CooccurrenceCard]
    total_cooccurrence_cards: int


class CountOf(_Shape):
    count: int
    of: int


class AuditBinding(_Shape):
    commander: str
    bound_decks: int
    other_commander_decks: int
    unbound_decks: int
    of: int


class AuditStatus(_Shape):
    befund: int
    unbekannt: int
    ohne_befund: int
    of: int


class AuditReason(_Shape):
    count: int
    of: int
    not_measurable: int


class AuditBucket(_Shape):
    decks: int
    befund: int
    unbekannt: int
    ohne_befund: int


class CorpusAuditAnswer(_Shape):
    """``GET /api/corpus-audit``: counts only, bound to the commander of the audit."""

    schema_: str = Field(alias="schema")
    origin: str
    cohort: str
    decks_counted: CountOf
    binding: AuditBinding
    decks_with_card_rows: CountOf
    status: AuditStatus
    by_reason: dict[str, AuditReason]
    by_cohort_dimension: dict[str, dict[str, AuditBucket]]
    card_facts_snapshot_date: str
    card_facts_age_days: int | str  # a number of days, or "unbekannt"
    note: str
    notes: list[str]
