-- Studio store fixture at schema 21 (#1703 / #1856, Owner decision 2026-11-28, Schema 22a).
-- The DDL below is the verbatim _SCHEMA text of src/commander_lab/studio/store.py as of
-- origin/main d021ebb4 (SCHEMA_VERSION = 21), followed by the additive simulation_run columns
-- that a 21 store gets on open (revision_id ... pilot_fingerprint), the meta row and three
-- simulation_run rows. It has NO games_drawn / games_decided columns: used by
-- tests/unit/test_studio_schema22a.py to prove the 21 -> 22 migration. Do not edit the DDL.
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source (
    source_id TEXT PRIMARY KEY,
    data_class TEXT NOT NULL,
    title TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    snapshot_date TEXT,
    url TEXT,
    imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card (
    card_id TEXT PRIMARY KEY,
    oracle_id TEXT,
    oracle_name TEXT NOT NULL,
    color_identity TEXT NOT NULL,
    mana_cost TEXT,
    mana_value REAL,
    type_line TEXT,
    oracle_text TEXT,
    is_basic_land INTEGER NOT NULL DEFAULT 0,
    commander_legal INTEGER,
    legality_verified_at TEXT,
    identity_evidence TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE INDEX IF NOT EXISTS card_name ON card(oracle_name);
CREATE TABLE IF NOT EXISTS inventory (
    card_id TEXT PRIMARY KEY REFERENCES card(card_id),
    observed INTEGER NOT NULL,
    owned_lower_bound INTEGER NOT NULL,
    reserved INTEGER NOT NULL,
    available_lower_bound INTEGER NOT NULL,
    quantity_exact INTEGER NOT NULL,
    lots INTEGER,
    last_verified_at TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
-- Where the copies of a card lie, as the inventory workbook's lot sheet states it (#1419):
-- summed lower-bound lot quantities per card and location (``exact`` 0 when any lot is only a
-- lower bound, ``unknown_lots`` lots without any quantity), the name from the location sheet.
-- Empty when the workbook carries no lot sheet; never guessed.
CREATE TABLE IF NOT EXISTS card_location (
    card_id TEXT NOT NULL REFERENCES card(card_id),
    location_id TEXT NOT NULL,
    location_name TEXT NOT NULL,
    location_type TEXT,
    quantity INTEGER NOT NULL,
    exact INTEGER NOT NULL,
    unknown_lots INTEGER NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (card_id, location_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS deck (
    deck_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deck_revision (
    revision_id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL REFERENCES deck(deck_id),
    parent_revision_id TEXT REFERENCES deck_revision(revision_id),
    deck_hash TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    source_id TEXT REFERENCES source(source_id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deck_revision_card (
    revision_id TEXT NOT NULL REFERENCES deck_revision(revision_id),
    card_id TEXT NOT NULL REFERENCES card(card_id),
    zone TEXT NOT NULL CHECK (zone IN ('commander', 'main')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (revision_id, card_id, zone)
);
CREATE TABLE IF NOT EXISTS deck_branch (
    deck_id TEXT NOT NULL REFERENCES deck(deck_id),
    branch TEXT NOT NULL,
    revision_id TEXT NOT NULL REFERENCES deck_revision(revision_id),
    PRIMARY KEY (deck_id, branch)
);
CREATE TABLE IF NOT EXISTS corpus_deck (
    deck_id TEXT PRIMARY KEY,
    cohort TEXT NOT NULL,
    url TEXT NOT NULL,
    platform TEXT NOT NULL,
    play_group TEXT NOT NULL,
    deck_date TEXT,
    tags TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    duplicate_of TEXT,
    legality_audit TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS corpus_deck_card (
    deck_id TEXT NOT NULL REFERENCES corpus_deck(deck_id),
    card_name TEXT NOT NULL,
    oracle_id TEXT,
    quantity INTEGER NOT NULL,
    section TEXT NOT NULL,
    normalization_status TEXT NOT NULL,
    PRIMARY KEY (deck_id, section, card_name)
) WITHOUT ROWID;
-- Covering index for per-card counts; per-deck counts use the WITHOUT ROWID primary key.
CREATE INDEX IF NOT EXISTS corpus_card_cover
    ON corpus_deck_card(card_name, section, quantity, deck_id);
CREATE TABLE IF NOT EXISTS observation (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT REFERENCES card(card_id),
    card_name TEXT NOT NULL,
    metric TEXT NOT NULL,
    cohort TEXT NOT NULL,
    value REAL,
    numerator INTEGER,
    denominator INTEGER,
    data_class TEXT NOT NULL,
    url TEXT,
    snapshot TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE INDEX IF NOT EXISTS observation_card ON observation(card_name, metric);
-- Importers replace the rows of one source (DELETE by source_id) before they write them again.
CREATE INDEX IF NOT EXISTS observation_source ON observation(source_id);
CREATE TABLE IF NOT EXISTS scryfall_card (
    oracle_id TEXT PRIMARY KEY,
    scryfall_id TEXT NOT NULL,
    name TEXT NOT NULL,
    front_name TEXT NOT NULL,
    layout TEXT NOT NULL,
    mana_cost TEXT,
    mana_value REAL,
    type_line TEXT,
    oracle_text TEXT,
    color_identity TEXT NOT NULL,
    commander_legality TEXT NOT NULL,
    edhrec_rank INTEGER,
    keywords TEXT NOT NULL,
    produced_mana TEXT NOT NULL,
    power TEXT,
    toughness TEXT,
    game_changer INTEGER,
    released_at TEXT,
    image_front TEXT,
    image_back TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    printing_set TEXT,
    printing_number TEXT,
    printing_basis TEXT
);
CREATE INDEX IF NOT EXISTS scryfall_name ON scryfall_card(name);
CREATE INDEX IF NOT EXISTS scryfall_front_name ON scryfall_card(front_name);
CREATE TABLE IF NOT EXISTS card_printing (
    card_id TEXT PRIMARY KEY REFERENCES card(card_id),
    set_code TEXT,
    collector_number TEXT,
    lang TEXT,
    finish TEXT,
    copies INTEGER NOT NULL DEFAULT 0,
    distinct_printings INTEGER NOT NULL DEFAULT 0,
    ref_status TEXT NOT NULL DEFAULT 'UNRESOLVED',
    scryfall_id TEXT,
    image_front TEXT,
    image_back TEXT,
    basis TEXT
);
CREATE TABLE IF NOT EXISTS card_mark (
    card_id TEXT PRIMARY KEY REFERENCES card(card_id),
    favorite INTEGER NOT NULL DEFAULT 0,
    excluded INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deck_draft (
    deck_id TEXT NOT NULL REFERENCES deck(deck_id),
    branch TEXT NOT NULL,
    cards TEXT NOT NULL,
    base_revision_id TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (deck_id, branch)
);
CREATE TABLE IF NOT EXISTS deck_module (
    module_id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL REFERENCES deck(deck_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('core', 'package')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS deck_module_deck ON deck_module(deck_id, sort_order, module_id);
CREATE TABLE IF NOT EXISTS deck_module_card (
    module_id TEXT NOT NULL REFERENCES deck_module(module_id) ON DELETE CASCADE,
    card_id TEXT NOT NULL REFERENCES card(card_id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    is_commander INTEGER NOT NULL DEFAULT 0 CHECK (is_commander IN (0, 1)),
    PRIMARY KEY (module_id, card_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS deck_primer (
    deck_id TEXT PRIMARY KEY REFERENCES deck(deck_id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scryfall_token (
    scryfall_id TEXT PRIMARY KEY,
    oracle_id TEXT,
    name TEXT NOT NULL,
    type_line TEXT NOT NULL DEFAULT '',
    power TEXT,
    toughness TEXT,
    colors TEXT NOT NULL DEFAULT '',
    oracle_text TEXT NOT NULL DEFAULT '',
    image_front TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE INDEX IF NOT EXISTS scryfall_token_name ON scryfall_token(name);
CREATE TABLE IF NOT EXISTS scryfall_card_token (
    oracle_id TEXT NOT NULL,
    token_scryfall_id TEXT NOT NULL,
    token_name TEXT NOT NULL,
    token_type_line TEXT NOT NULL DEFAULT '',
    token_uri TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (oracle_id, token_scryfall_id, token_name)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS scryfall_card_token_oracle ON scryfall_card_token(oracle_id);
CREATE TABLE IF NOT EXISTS corpus_cohort (
    cohort TEXT NOT NULL,
    deck_id TEXT NOT NULL REFERENCES corpus_deck(deck_id),
    PRIMARY KEY (cohort, deck_id)
) WITHOUT ROWID;
-- The primary key leads with cohort; the per-deck delete of an import needs deck_id alone.
CREATE INDEX IF NOT EXISTS corpus_cohort_deck ON corpus_cohort(deck_id);
CREATE TABLE IF NOT EXISTS universe_profile (
    profile_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    spec TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS corpus_deck_part (
    deck_id TEXT PRIMARY KEY REFERENCES corpus_deck(deck_id) DEFERRABLE INITIALLY DEFERRED,
    part_name TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS commander_binding (
    kind TEXT NOT NULL CHECK (kind IN
        ('corpus_deck', 'observation_cohort', 'simulation_run', 'neutral_source')),
    key TEXT NOT NULL,
    commander_name TEXT NOT NULL,
    basis TEXT NOT NULL,
    PRIMARY KEY (kind, key, commander_name)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS commander_binding_name ON commander_binding(commander_name, kind);
CREATE TABLE IF NOT EXISTS corpus_deck_stat (
    deck_id TEXT PRIMARY KEY REFERENCES corpus_deck(deck_id),
    cards INTEGER NOT NULL,
    resolved INTEGER NOT NULL,
    lands INTEGER NOT NULL,
    creatures INTEGER NOT NULL,
    nonland_mana_value REAL NOT NULL,
    nonland_cards INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS card_role (
    oracle_id TEXT NOT NULL,
    role TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (oracle_id, role)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS card_role_claim (
    oracle_id TEXT NOT NULL,
    role TEXT NOT NULL,
    role_origin TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    original_tag TEXT,
    mapping_rule TEXT,
    PRIMARY KEY (oracle_id, role, role_origin, scope_key, source_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS card_role_claim_scope ON card_role_claim(role_origin, scope_key, role);
CREATE TABLE IF NOT EXISTS corpus_deck_role (
    deck_id TEXT NOT NULL REFERENCES corpus_deck(deck_id),
    role TEXT NOT NULL,
    cards INTEGER NOT NULL,
    PRIMARY KEY (deck_id, role)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS neutral_board_row (
    source_key TEXT NOT NULL,
    batch TEXT NOT NULL,
    section TEXT NOT NULL,
    card_name TEXT NOT NULL,
    oracle_id TEXT,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (source_key, section, card_name)
);
CREATE INDEX IF NOT EXISTS neutral_board_oracle ON neutral_board_row(oracle_id);
CREATE INDEX IF NOT EXISTS neutral_board_name ON neutral_board_row(card_name);
CREATE TABLE IF NOT EXISTS simulation_run (
    run_id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL,
    pod TEXT NOT NULL,
    engine_pin TEXT NOT NULL,
    bridge_jar_sha256 TEXT,
    bridge_qualification_state TEXT,
    pilot_policy TEXT NOT NULL,
    seeds TEXT NOT NULL,
    games_planned INTEGER NOT NULL,
    games_completed INTEGER NOT NULL,
    games_failed INTEGER NOT NULL,
    wins_fractional REAL NOT NULL,
    win_rate REAL,
    mean_rounds REAL,
    hand_dwell_status TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS simulation_card (
    run_id TEXT NOT NULL REFERENCES simulation_run(run_id),
    card_id TEXT REFERENCES card(card_id),
    card_name TEXT NOT NULL,
    games_completed INTEGER NOT NULL,
    games_offered INTEGER NOT NULL,
    games_cast_after_offer INTEGER NOT NULL,
    games_rotted INTEGER NOT NULL,
    offered_castable INTEGER NOT NULL,
    cast_count INTEGER NOT NULL,
    mean_first_cast_round REAL,
    PRIMARY KEY (run_id, card_name)
);
CREATE INDEX IF NOT EXISTS simulation_card_id ON simulation_card(card_id);
-- B2 (#1658): additive experiment index, no schema bump (22 is reserved for K-2, E15 Q9).
-- Plan, result and decision files stay the source; ``experiments.rebuild_index`` rebuilds
-- both tables from them. A decision is kept in the row and in its file.
CREATE TABLE IF NOT EXISTS experiment (
    experiment_id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL,
    question TEXT NOT NULL,
    question_kind TEXT,
    purpose TEXT NOT NULL,
    base_revision_id TEXT NOT NULL,
    plan_sha TEXT,
    table_hash TEXT,
    first_seed INTEGER,
    last_seed INTEGER,
    series_id TEXT,
    engine_pin TEXT,
    bridge_jar_sha256 TEXT,
    bridge_state TEXT,
    pilot_fingerprint TEXT,
    decision TEXT NOT NULL DEFAULT 'open' CHECK (decision IN ('open', 'adopted', 'rejected')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'withdrawn')),
    decision_at TEXT,
    decision_note TEXT,
    decision_tested INTEGER,
    decision_previous_revision_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS experiment_deck ON experiment(deck_id);
CREATE TABLE IF NOT EXISTS experiment_arm (
    experiment_id TEXT NOT NULL REFERENCES experiment(experiment_id),
    role TEXT NOT NULL CHECK (role IN ('base', 'variant')),
    revision_id TEXT NOT NULL,
    deck_hash TEXT,
    PRIMARY KEY (experiment_id, role, revision_id)
);
CREATE INDEX IF NOT EXISTS experiment_arm_revision ON experiment_arm(revision_id);
CREATE TABLE IF NOT EXISTS source_capture_event (
    event_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    request_start_utc TEXT NOT NULL,
    response_complete_utc TEXT NOT NULL,
    raw_response_sha256 TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    provenance_class TEXT NOT NULL,
    raw_size_bytes INTEGER NOT NULL,
    cardlists_count INTEGER NOT NULL,
    automatic_import INTEGER NOT NULL DEFAULT 0,
    source_id TEXT REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS playgroup_card_atlas (
    oracle_id TEXT NOT NULL,
    format_mode TEXT NOT NULL DEFAULT 'multiplayer',
    card_id TEXT REFERENCES card(card_id),
    card_name TEXT NOT NULL,
    slug TEXT NOT NULL,
    card_type TEXT,
    set_name TEXT,
    live_inclusion_pct REAL,
    deck_inclusion_pct REAL,
    times_brought INTEGER,
    decks_running INTEGER,
    unique_players INTEGER,
    median_cast_turn REAL,
    drawn_to_played_pct REAL,
    first_cast_n INTEGER,
    turn_1_pct REAL,
    turn_2_pct REAL,
    turn_3_pct REAL,
    turn_4_pct REAL,
    turn_5_pct REAL,
    turn_6_to_9_pct REAL,
    turn_10_plus_pct REAL,
    p25_cast_turn REAL,
    p75_cast_turn REAL,
    max_cast_turn REAL,
    on_curve_pct REAL,
    on_curve_count INTEGER,
    on_curve_denominator INTEGER,
    on_curve_turn TEXT,
    cast_same_turn_as_drawn_pct REAL,
    turns_in_hand REAL,
    funnel_brought_n INTEGER,
    funnel_players_n INTEGER,
    ever_drawn_n INTEGER,
    reached_battlefield_n INTEGER,
    still_on_board_at_end_n INTEGER,
    battlefield_survival_pct REAL,
    winrate_when_cast_pct REAL,
    winrate_when_cast_n INTEGER,
    winrate_when_in_library_pct REAL,
    winrate_when_in_library_n INTEGER,
    winrate_when_in_hand_pct REAL,
    winrate_when_in_hand_n INTEGER,
    observed_winrate_gap_pp REAL,
    ci_95_lower_pp REAL,
    ci_95_upper_pp REAL,
    conservative_ranking_indicator TEXT,
    final_zones_instances_n INTEGER,
    fetch_status TEXT NOT NULL DEFAULT 'OK',
    quality_warnings_json TEXT NOT NULL DEFAULT '[]',
    insufficient_sample INTEGER NOT NULL DEFAULT 0,
    retrieved_at_utc TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (oracle_id, format_mode)
);
CREATE INDEX IF NOT EXISTS idx_playgroup_card_atlas_card_id ON playgroup_card_atlas(card_id);
CREATE INDEX IF NOT EXISTS idx_playgroup_card_atlas_slug ON playgroup_card_atlas(slug);
CREATE INDEX IF NOT EXISTS idx_playgroup_card_atlas_status ON playgroup_card_atlas(fetch_status);
CREATE INDEX IF NOT EXISTS idx_playgroup_card_atlas_name ON playgroup_card_atlas(card_name);
CREATE TABLE IF NOT EXISTS playgroup_top_commander (
    oracle_id TEXT NOT NULL,
    format_mode TEXT NOT NULL DEFAULT 'multiplayer',
    rank INTEGER NOT NULL,
    commander_name TEXT NOT NULL,
    commander_slug TEXT NOT NULL,
    color_identity TEXT NOT NULL,
    decks_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (oracle_id, format_mode, rank)
);
CREATE TABLE IF NOT EXISTS playgroup_final_zone (
    oracle_id TEXT NOT NULL,
    format_mode TEXT NOT NULL DEFAULT 'multiplayer',
    zone_name TEXT NOT NULL,
    pct REAL NOT NULL,
    instances_n INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (oracle_id, format_mode, zone_name)
);
CREATE TABLE IF NOT EXISTS card_signal (
    commander_name TEXT NOT NULL,
    signal TEXT NOT NULL,
    card_name TEXT NOT NULL,
    value REAL,
    numerator INTEGER,
    denominator INTEGER,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (commander_name, signal, card_name)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS strength_profile (
    name TEXT PRIMARY KEY,
    spec TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tier_snapshot (
    commander_name TEXT NOT NULL,
    spec_hash TEXT NOT NULL,
    profile_name TEXT NOT NULL,
    spec_version TEXT NOT NULL,
    data_epoch TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tier_counts_json TEXT NOT NULL,
    component_denominators_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (commander_name, spec_hash)
);
CREATE TABLE IF NOT EXISTS card_label (
    card_id TEXT NOT NULL REFERENCES card(card_id),
    label TEXT NOT NULL COLLATE NOCASE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (card_id, label)
);
CREATE INDEX IF NOT EXISTS card_label_label ON card_label(label);
CREATE TABLE IF NOT EXISTS deck_label (
    deck_id TEXT NOT NULL REFERENCES deck(deck_id),
    label TEXT NOT NULL COLLATE NOCASE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (deck_id, label)
);
CREATE TABLE IF NOT EXISTS commander_combo (
    commander_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    cards TEXT NOT NULL,
    num_decks INTEGER NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (commander_name, ordinal)
);
CREATE TABLE IF NOT EXISTS card_ruling (
    oracle_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    published_at TEXT NOT NULL,
    ruling_source TEXT NOT NULL,
    comment TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (oracle_id, ordinal)
);
CREATE UNIQUE INDEX IF NOT EXISTS card_ruling_unique
    ON card_ruling(oracle_id, published_at, comment);
CREATE TABLE IF NOT EXISTS card_ruling_source (
    oracle_id TEXT NOT NULL,
    published_at TEXT NOT NULL,
    comment TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (oracle_id, published_at, comment, source_id)
);
-- TAM purchase guide values (#1637, register entry "Preise für TAM"): the field prices.eur of a
-- local Scryfall bulk file, one value per oracle_id, only in this local store (never committed,
-- never in scryfall_card). Read only by purchase_guide_values (TAM guide-value module).
-- Created on every open without a schema bump (schema 22 is reserved for the file split,
-- E15 Q9); a card without a usable value has no row ("unbekannt", never 0).
CREATE TABLE IF NOT EXISTS tam_price_snapshot (
    snapshot_id INTEGER PRIMARY KEY CHECK (snapshot_id = 1),
    file_name TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    bulk_date TEXT NOT NULL,
    date_basis TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    cards_with_value INTEGER NOT NULL,
    cards_without_value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tam_price_eur (
    oracle_id TEXT PRIMARY KEY,
    eur_cents INTEGER NOT NULL CHECK (eur_cents > 0),
    scryfall_id TEXT,
    finish TEXT,
    set_code TEXT,
    collector_number TEXT
) WITHOUT ROWID;
-- TAM Cardmarket prices (#1637, WP-10b, register entry "Preise für TAM" and its Owner
-- exception of 2026-11-22), all only in this local store (never committed) and read only by the
-- TAM guide-value module; no row means "unbekannt", never 0.
-- tam_cardmarket_price: a price the Owner read on Cardmarket and entered (or a CSV of such
-- prices); filter_code names the Cardmarket filters it was read under.
CREATE TABLE IF NOT EXISTS tam_cardmarket_price (
    oracle_id TEXT PRIMARY KEY,
    eur_cents INTEGER NOT NULL CHECK (eur_cents > 0),
    price_date TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    filter_code TEXT NOT NULL,
    source_url TEXT
) WITHOUT ROWID;
-- tam_price_print: the Cardmarket product id (cardmarket_id) of each playable paper printing of
-- the local Scryfall bulk file, the key to the price guide.
CREATE TABLE IF NOT EXISTS tam_price_print (
    cardmarket_id INTEGER PRIMARY KEY,
    oracle_id TEXT NOT NULL,
    set_code TEXT,
    collector_number TEXT
);
-- tam_cardmarket_guide: per card the lowest 'low' / 'low-foil' and the lowest 'trend' /
-- 'trend-foil' of Cardmarket's published price guide over its playable printings (no filter on
-- seller country or condition), with finish and printing of the lowest 'low'.
CREATE TABLE IF NOT EXISTS tam_cardmarket_guide (
    oracle_id TEXT PRIMARY KEY,
    low_cents INTEGER CHECK (low_cents > 0),
    low_finish TEXT CHECK (low_finish IN ('nonfoil', 'foil')),
    low_set_code TEXT,
    low_collector_number TEXT,
    trend_cents INTEGER CHECK (trend_cents > 0),
    CHECK (low_cents IS NOT NULL OR trend_cents IS NOT NULL)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS tam_cardmarket_guide_snapshot (
    snapshot_id INTEGER PRIMARY KEY CHECK (snapshot_id = 1),
    guide_date TEXT NOT NULL,
    date_basis TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    products_in_guide INTEGER NOT NULL,
    printings_known INTEGER NOT NULL,
    printings_matched INTEGER NOT NULL,
    name_mismatches INTEGER NOT NULL,
    name_check INTEGER NOT NULL CHECK (name_check IN (0, 1)),
    cards_with_value INTEGER NOT NULL
);
-- PLAY v1 postgame session summary and deck/card play notes (#1662 part 4): additive tables
-- without bumping SCHEMA_VERSION (22 is reserved for #1703 K-2).
CREATE TABLE IF NOT EXISTS play_session (
    game_id TEXT PRIMARY KEY,
    deck_id TEXT,
    revision_id TEXT,
    deck_hash TEXT,
    table_json TEXT,
    seed INTEGER,
    human_seat INTEGER,
    outcome TEXT,
    duration_seconds REAL,
    human_clicks INTEGER,
    bridge_jar_sha256 TEXT,
    bridge_qualification_state TEXT,
    data_class TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS play_note (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    deck_id TEXT,
    revision_id TEXT,
    card_name TEXT,
    note_text TEXT NOT NULL,
    action_hint TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS play_note_game ON play_note(game_id);
CREATE INDEX IF NOT EXISTS play_note_deck ON play_note(deck_id, revision_id);
CREATE VIEW IF NOT EXISTS card_fact AS
SELECT c.card_id,
       c.oracle_name,
       COALESCE(s.oracle_id, c.oracle_id) AS oracle_id,
       CASE WHEN s.oracle_id IS NULL THEN c.oracle_name
            WHEN s.layout = 'split' THEN s.name ELSE s.front_name END AS engine_name,
       COALESCE(s.color_identity, REPLACE(c.color_identity, 'C', '')) AS color_identity,
       COALESCE(s.mana_cost, c.mana_cost) AS mana_cost,
       COALESCE(s.mana_value, c.mana_value) AS mana_value,
       COALESCE(s.type_line, c.type_line) AS type_line,
       COALESCE(s.oracle_text, c.oracle_text) AS oracle_text,
       CASE WHEN COALESCE(s.type_line, c.type_line) LIKE 'Basic %Land%' THEN 1
            ELSE c.is_basic_land END AS is_basic_land,
       CASE WHEN s.oracle_id IS NULL THEN c.commander_legal
            WHEN s.commander_legality = 'legal' THEN 1 ELSE 0 END AS commander_legal,
       CASE WHEN s.oracle_id IS NULL THEN 'workbook' ELSE 'scryfall' END AS fact_source,
       s.layout, s.edhrec_rank, s.keywords, s.produced_mana, s.power, s.toughness,
       s.game_changer, s.image_front, s.image_back
FROM card c LEFT JOIN scryfall_card s ON s.oracle_id = c.oracle_id;

ALTER TABLE simulation_run ADD COLUMN revision_id TEXT;
ALTER TABLE simulation_run ADD COLUMN deck_hash TEXT;
ALTER TABLE simulation_run ADD COLUMN opponent_ids TEXT;
ALTER TABLE simulation_run ADD COLUMN opponent_set_hash TEXT;
ALTER TABLE simulation_run ADD COLUMN table_size INTEGER;
ALTER TABLE simulation_run ADD COLUMN pilot_fingerprint TEXT;
INSERT INTO meta(key, value) VALUES ('schema_version', '21');
INSERT INTO source(source_id, data_class, title, sha256, imported_at)
VALUES ('src-1', 'SIMULATED_RESULT', 'fixture source', 'aa', '2026-11-01T00:00:00Z');
INSERT INTO simulation_run(run_id, deck_id, pod, engine_pin, pilot_policy, seeds, games_planned,
    games_completed, games_failed, wins_fractional, win_rate, mean_rounds, hand_dwell_status,
    source_id)
VALUES ('run-a', 'deck/a', 'pod-a', 'pin', 'policy', '[1,2,3,4]', 4, 4, 0, 2.0, 0.6667, 7.5,
    'NOT_MEASURED', 'src-1');
INSERT INTO simulation_run(run_id, deck_id, pod, engine_pin, pilot_policy, seeds, games_planned,
    games_completed, games_failed, wins_fractional, win_rate, mean_rounds, hand_dwell_status,
    source_id)
VALUES ('run-b', 'deck/a', 'pod-b', 'pin', 'policy', '[5,6]', 2, 2, 0, 1.0, 0.5, 6.0,
    'NOT_MEASURED', 'src-1');
INSERT INTO simulation_run(run_id, deck_id, pod, engine_pin, pilot_policy, seeds, games_planned,
    games_completed, games_failed, wins_fractional, win_rate, mean_rounds, hand_dwell_status,
    source_id)
VALUES ('run-c', 'deck/b', 'pod-a', 'pin', 'policy', '[7]', 1, 0, 1, 0.0, NULL, NULL,
    'NOT_MEASURED', 'src-1');
