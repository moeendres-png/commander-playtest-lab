"""Tests for the Commander Studio evidence source registry (P0 Deliverable 1 & 2).

Verifies the systematic qualification of the 9 prioritized sources, schema integrity,
explicit null-timestamp preservation, JSON inventory generation, card coverage record calculation,
long-tail candidate identification, and full 927-card pool gap matrix calculation.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import re
from pathlib import Path

import pytest

from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.sources import (
    ACCESS_STATUSES,
    QUALIFIED_SOURCES,
    PoolGapMatrixPayload,
    calculate_card_coverage_record,
    calculate_pool_gap_matrix,
    generate_gap_example_report,
    get_source,
    list_sources,
    load_spellbook_combo_cards,
    source_inventory_payload,
    write_gap_matrix_json,
    write_source_inventory_json,
)
from commander_lab.studio.store import StudioStore

EXPECTED_PRIORITIES = (
    (1, "scryfall:bulk-oracle", "VERIFIED"),
    (2, "playgroup:card-atlas", "REVIEW"),
    (3, "playgroup:chulane", "REVIEW"),
    (4, "edhrec:chulane", "VERIFIED"),
    (5, "spellbook:variants-api", "VERIFIED"),
    (6, "repo:chulane-corpus", "VERIFIED"),
    (7, "tournament:cedh-meta", "REVIEW"),
    (8, "xmage:card-facts", "VERIFIED"),
    (9, "scryfall:tagger", "REVIEW"),
    (10, "archidekt:decks", "UNAVAILABLE"),
    (11, "moxfield:decks", "UNAVAILABLE"),
    (12, "cardmarket:price-guide", "REVIEW"),
)


def test_qualified_sources_covers_all_twelve_priorities_in_exact_order() -> None:
    assert len(QUALIFIED_SOURCES) == 12
    priorities = [s.priority for s in QUALIFIED_SOURCES]
    assert priorities == list(range(1, 13))

    assert len(EXPECTED_PRIORITIES) == 12
    for (expected_prio, expected_id, expected_status), source in zip(
        EXPECTED_PRIORITIES, QUALIFIED_SOURCES, strict=True
    ):
        assert source.priority == expected_prio
        assert source.source_id == expected_id
        assert source.status == expected_status


def _assert_check_date(checked: object, evidence_url: str) -> None:
    """Terms are read on a date; a purely local source has no terms, so it carries None."""
    if checked is None:
        assert evidence_url.startswith("local:"), "only local sources may omit the check date"
        return
    assert isinstance(checked, str)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked) is not None


def test_every_source_has_all_seventeen_dimensions_populated() -> None:
    allowed_statuses = {"VERIFIED", "REVIEW", "UNAVAILABLE"}
    allowed_access_statuses = set(ACCESS_STATUSES)
    allowed_layers = {
        "FACT",
        "DERIVED_MECHANICAL",
        "OBSERVED_DECK",
        "OBSERVED_GAME",
        "COMBO_VERIFIED",
        "SIMULATED_RESULT",
        "MODELED",
        "EXTERNAL_OPINION",
    }

    assert len(QUALIFIED_SOURCES) == 12
    for source in QUALIFIED_SOURCES:
        # Core identification & URL
        assert source.source_id.strip() != ""
        assert source.title.strip() != ""
        assert source.direct_url.startswith("https://") or source.direct_url.startswith("local:")
        assert source.publisher.strip() != ""
        assert isinstance(source.reference_urls, tuple)
        assert len(source.reference_urls) > 0

        # Technical format & identification
        assert source.schema_format.strip() != ""
        assert source.card_identifier.strip() != ""
        assert source.coverage_scope.strip() != ""
        assert source.evidence_layer in allowed_layers
        assert isinstance(source.has_exact_numerator_denominator, bool)
        assert isinstance(source.game_context, dict)
        assert len(source.game_context) > 0

        # Governance, licensing, access & reproducibility
        assert source.double_counting_risk.strip() != ""
        assert source.license_terms.strip() != ""
        assert source.allowed_retrieval_method.strip() != ""
        assert source.reproducibility in {
            "DETERMINISTIC_OFFLINE_SNAPSHOT",
            "REPRODUCIBLE_API",
            "DYNAMIC_EPHEMERAL_WEB",
            "MANUAL_ARCHIVE",
            "UNKNOWN_NO_SNAPSHOT_RECORDED",
        }
        assert isinstance(source.bias_risks, tuple)
        assert len(source.bias_risks) > 0
        assert source.status in allowed_statuses
        assert source.status_rationale.strip() != ""
        assert source.access_status in allowed_access_statuses
        assert source.access_evidence_url.startswith(("https://", "local:"))
        _assert_check_date(source.access_checked_at_utc, source.access_evidence_url)


def test_missing_timestamps_remain_none_never_fabricated() -> None:
    # Sources without an exact verified HTTP capture must have retrieved_at_utc=None
    playgroup_atlas = get_source("playgroup:card-atlas")
    assert playgroup_atlas.retrieved_at_utc is None
    assert playgroup_atlas.snapshot_id is None

    playgroup_chulane = get_source("playgroup:chulane")
    assert playgroup_chulane.retrieved_at_utc is None
    assert playgroup_chulane.snapshot_id is None

    tournament = get_source("tournament:cedh-meta")
    assert tournament.retrieved_at_utc is None
    assert tournament.snapshot_id is None

    tagger = get_source("scryfall:tagger")
    assert tagger.retrieved_at_utc is None
    assert tagger.snapshot_id is None

    # Verified sources have explicit UTC timestamps and snapshot IDs
    scryfall = get_source("scryfall:bulk-oracle")
    assert scryfall.retrieved_at_utc == "2026-11-10T00:00:00Z"
    assert scryfall.snapshot_id == "scryfall-oracle-cards-20261110"

    xmage = get_source("xmage:card-facts")
    assert xmage.retrieved_at_utc == "2026-11-12T13:04:32Z"  # exported_at of the facts file
    assert xmage.snapshot_id == "xmage-card-facts-1.0.0-database-78c12c7d"

    # The corpus has no recorded retrieval time or snapshot: unbekannt, never invented
    with pytest.raises(KeyError):
        get_source("active_drive:chulane-corpus-975")  # misleading id (title and counts changed)
    corpus = get_source("repo:chulane-corpus")
    assert corpus.retrieved_at_utc is None
    assert corpus.snapshot_id is None


def test_get_source_and_list_sources() -> None:
    source = get_source("spellbook:variants-api")
    assert source.priority == 5
    assert source.evidence_layer == "COMBO_VERIFIED"
    assert "commanderspellbook.com" in source.direct_url

    with pytest.raises(KeyError, match="Unknown evidence source"):
        get_source("non-existent-source")

    verified = list_sources(status="VERIFIED")
    assert len(verified) == 5
    assert {s.source_id for s in verified} == {
        "scryfall:bulk-oracle",
        "edhrec:chulane",
        "spellbook:variants-api",
        "repo:chulane-corpus",
        "xmage:card-facts",
    }

    review = list_sources(status="REVIEW")
    assert len(review) == 5
    assert {s.source_id for s in review} == {
        "playgroup:card-atlas",
        "playgroup:chulane",
        "tournament:cedh-meta",
        "scryfall:tagger",
        "cardmarket:price-guide",
    }

    unavailable = list_sources(status="UNAVAILABLE")
    assert len(unavailable) == 2
    assert {s.source_id for s in unavailable} == {
        "archidekt:decks",
        "moxfield:decks",
    }


def test_source_inventory_payload_matches_schema() -> None:
    payload = source_inventory_payload()
    assert payload["schema_version"] == "evidence-source-inventory-1.0.0"
    assert payload["total_sources"] == 12
    assert payload["status_counts"]["VERIFIED"] == 5
    assert payload["status_counts"]["REVIEW"] == 5
    assert payload["status_counts"]["UNAVAILABLE"] == 2
    assert payload["access_status_counts"] == {
        "ok": 1,
        "ok_with_conditions": 5,
        "unclear": 2,
        "prohibited": 4,
    }
    assert len(payload["sources"]) == 12


def test_write_source_inventory_json_roundtrip(tmp_path: Path) -> None:
    target_file = tmp_path / "provenance" / "test_sources.json"
    written_path = write_source_inventory_json(target_file)
    assert written_path.is_file()

    loaded = json.loads(written_path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "evidence-source-inventory-1.0.0"
    assert loaded["total_sources"] == 12
    assert len(loaded["sources"]) == 12
    first = loaded["sources"][0]
    assert first["source_id"] == "scryfall:bulk-oracle"
    assert first["priority"] == 1


def test_load_spellbook_combo_cards(tmp_path: Path) -> None:
    # 1. Non-existent path returns empty set
    empty_set = load_spellbook_combo_cards(tmp_path / "does_not_exist.json")
    assert empty_set == set()

    # 2. Corrupted JSON returns empty set
    corrupted_file = tmp_path / "corrupted.json"
    corrupted_file.write_text("{not valid json", encoding="utf-8")
    assert load_spellbook_combo_cards(corrupted_file) == set()

    # 3. Valid JSON with Chulane combo and non-Chulane combo
    valid_file = tmp_path / "combos.json"
    payload = {
        "combos": [
            {
                "commander": "Chulane, Teller of Tales",
                "cards": ["Shrieking Drake", "Lotus Cobra"],
                "any_of": [["Mana Breach", "Overburden"]],
            },
            {
                "commander": "Korvold, Fae-Cursed King",
                "cards": ["Dockside Extortionist", "Mayhem Devil"],
            },
        ]
    }
    valid_file.write_text(json.dumps(payload), encoding="utf-8")
    extracted = load_spellbook_combo_cards(valid_file)
    assert extracted == {"Shrieking Drake", "Lotus Cobra", "Mana Breach", "Overburden"}

    # 4. Canonical repository file check (if present)
    canonical = Path("data/meta/spellbook_combos.json")
    if canonical.is_file():
        cards = load_spellbook_combo_cards()
        assert "Chulane, Teller of Tales" in cards
        assert "Shrieking Drake" in cards
        assert "Whitemane Lion" in cards


def test_calculate_card_coverage_record_grades_and_scores() -> None:
    spellbook_cards = {"Shrieking Drake", "Whitemane Lion"}

    # 1. Unobserved card in corpus (0 hits)
    unobserved_card: dict[str, object] = {
        "name": "Esperzoa",
        "oracle_id": "test-esperzoa-id",
        "mana_value": 3.0,
        "colors": "U",
        "type_line": "Artifact Creature — Jellyfish",
        "group": "Creature",
        "has_image": True,
        "sim_status": "OK",
        "decks": {"all": 0},
        "roles": ["bounce"],
    }
    rec_unobs = calculate_card_coverage_record(unobserved_card, spellbook_cards)
    assert rec_unobs.coverage_grade == "UNOBSERVED_IN_CORPUS"
    assert rec_unobs.corpus_hits == 0
    assert rec_unobs.has_scryfall_facts is True
    assert rec_unobs.has_xmage_rules is True
    assert rec_unobs.has_spellbook_combos is False
    assert rec_unobs.is_long_tail_candidate is True
    assert "0/975 corpus hits with engine relevance" in rec_unobs.notes
    assert rec_unobs.research_priority_score == pytest.approx(0.48, abs=0.01)

    # Notes texts follow the caller-supplied corpus denominator (canonical 2823),
    # not a hardcoded value.
    rec_unobs_2823 = calculate_card_coverage_record(
        unobserved_card, spellbook_cards, corpus_denominator=2823
    )
    assert "0/2823 corpus hits with engine relevance" in rec_unobs_2823.notes

    unobserved_plain_card: dict[str, object] = {
        "name": "Test Sorcery",
        "oracle_id": "test-sorcery-id",
        "mana_value": 5.0,
        "colors": "G",
        "type_line": "Sorcery",
        "group": "Sorcery",
        "has_image": True,
        "sim_status": "OK",
        "decks": {"all": 0},
        "roles": [],
    }
    rec_unobs_plain = calculate_card_coverage_record(
        unobserved_plain_card, spellbook_cards, corpus_denominator=2823
    )
    assert rec_unobs_plain.is_long_tail_candidate is False
    assert "Unobserved in curated 2823-deck corpus" in rec_unobs_plain.notes

    # 2. Sparse card (1-4 hits)
    sparse_card: dict[str, object] = {
        "name": "Cloudstone Curio",
        "oracle_id": "test-curio-id",
        "mana_value": 3.0,
        "colors": "",
        "type_line": "Artifact",
        "group": "Artifact",
        "has_image": True,
        "sim_status": "OK",
        "decks": {"all": 4},
        "roles": ["bounce", "combo"],
    }
    rec_sparse = calculate_card_coverage_record(sparse_card, spellbook_cards)
    assert rec_sparse.coverage_grade == "SPARSE"
    assert rec_sparse.corpus_hits == 4
    assert rec_sparse.is_long_tail_candidate is True

    # 3. Complete card (>= 5 hits, scryfall, xmage, edhrec)
    complete_card: dict[str, object] = {
        "name": "Shrieking Drake",
        "oracle_id": "test-drake-id",
        "mana_value": 1.0,
        "colors": "U",
        "type_line": "Creature — Drake",
        "group": "Creature",
        "has_image": True,
        "sim_status": "OK",
        "decks": {"all": 500},
        "edhrec": {"numerator": 8000, "denominator": 10000, "pct": 80.0},
        "roles": ["bounce"],
    }
    rec_complete = calculate_card_coverage_record(complete_card, spellbook_cards)
    assert rec_complete.coverage_grade == "COMPLETE"
    assert rec_complete.has_spellbook_combos is True
    assert rec_complete.is_long_tail_candidate is False
    assert rec_complete.research_priority_score == 0.0

    # 4. Partial card (>= 5 hits, but missing edhrec)
    partial_card: dict[str, object] = {
        "name": "Fleetfoot Panther",
        "oracle_id": "test-panther-id",
        "mana_value": 3.0,
        "colors": "WG",
        "type_line": "Creature — Cat",
        "group": "Creature",
        "has_image": True,
        "sim_status": "OK",
        "decks": {"all": 16},
        "roles": ["bounce"],
    }
    rec_partial = calculate_card_coverage_record(partial_card, spellbook_cards)
    assert rec_partial.coverage_grade == "PARTIAL"
    assert rec_partial.corpus_hits == 16
    assert rec_partial.is_long_tail_candidate is False


def _public_card(
    name: str,
    colors: list[str],
    type_line: str,
    *,
    mana_cost: str,
    cmc: float,
) -> dict[str, object]:
    slug = name.casefold().replace(" ", "-").replace("/", "")
    return {
        "id": f"print-{slug}",
        "oracle_id": f"oracle-{slug}",
        "name": name,
        "layout": "normal",
        "mana_cost": mana_cost,
        "cmc": cmc,
        "type_line": type_line,
        "oracle_text": "",
        "color_identity": colors,
        "legalities": {"commander": "legal"},
        "keywords": [],
        "image_uris": {"normal": f"https://cards.scryfall.io/normal/front/a/b/{slug}.jpg"},
    }


def _build_gap_matrix_store(tmp_path: Path, *, with_corpus: bool = True) -> tuple[Path, Path]:
    """Build a self-contained synthetic Chulane StudioStore covering all four coverage grades."""
    from commander_lab.studio import catalog, importers
    from tests.unit.test_studio_store import (
        _card,
        _card_row,
        _register_row,
        _workbook,
        _write_csv,
    )

    commander = "Chulane, Teller of Tales"
    store_dir = tmp_path / "studio"
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    cards = [
        _card(
            1,
            commander,
            "GWU",
            "Legendary Creature — Human Druid",
            mana_cost="{2}{G}{W}{U}",
            mana_value=5,
        ),
        _card(
            2,
            "Shrieking Drake",
            "U",
            "Creature — Drake",
            mana_cost="{U}",
            mana_value=1,
        ),
        _card(
            3,
            "Fleetfoot Panther",
            "GW",
            "Creature — Cat",
            mana_cost="{1}{G}{W}",
            mana_value=3,
        ),
        _card(
            4,
            "Cloudstone Curio",
            "",
            "Artifact",
            mana_cost="{3}",
            mana_value=3,
        ),
        _card(
            5,
            "Esperzoa",
            "U",
            "Artifact Creature — Jellyfish",
            mana_cost="{2}{U}",
            mana_value=3,
        ),
    ]
    public_cards = [
        _public_card(
            commander,
            ["G", "U", "W"],
            "Legendary Creature — Human Druid",
            mana_cost="{2}{G}{W}{U}",
            cmc=5.0,
        ),
        _public_card("Shrieking Drake", ["U"], "Creature — Drake", mana_cost="{U}", cmc=1.0),
        _public_card(
            "Fleetfoot Panther", ["G", "W"], "Creature — Cat", mana_cost="{1}{G}{W}", cmc=3.0
        ),
        _public_card("Cloudstone Curio", [], "Artifact", mana_cost="{3}", cmc=3.0),
        _public_card(
            "Esperzoa", ["U"], "Artifact Creature — Jellyfish", mana_cost="{2}{U}", cmc=3.0
        ),
    ]
    oracle_path = inputs_dir / "oracle.jsonl.gz"
    with gzip.open(oracle_path, "wt", encoding="utf-8") as handle:
        handle.write("[\n" + ",\n".join(json.dumps(c) for c in public_cards) + "\n]\n")

    combos_path = inputs_dir / "spellbook_combos.json"
    combos_path.write_text(
        json.dumps(
            {
                "combos": [
                    {
                        "commander": commander,
                        "cards": [commander, "Shrieking Drake"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    store = StudioStore.open(store_dir)
    try:
        importers.import_inventory_workbook(store, _workbook(inputs_dir / "cards.xlsx", cards))
        catalog.import_scryfall_oracle(store, oracle_path)
        db = store.connection
        source_id = str(db.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
        if with_corpus:
            register_rows = [_register_row(f"d{i}", "community") for i in range(1, 7)]
            card_rows: list[dict[str, object]] = []
            # 6 decks: Chulane + Shrieking Drake (6 hits) + Fleetfoot Panther (5 hits) + Cloudstone Curio (2 hits); Esperzoa has 0 hits.
            for idx in range(1, 7):
                deck_id = f"d{idx}"
                card_rows.append(
                    {
                        **_card_row(deck_id, commander),
                        "oracle_id": "oracle-chulane,-teller-of-tales",
                    }
                )
                card_rows.append(
                    {**_card_row(deck_id, "Shrieking Drake"), "oracle_id": "oracle-shrieking-drake"}
                )
                if idx <= 5:
                    card_rows.append(
                        {
                            **_card_row(deck_id, "Fleetfoot Panther"),
                            "oracle_id": "oracle-fleetfoot-panther",
                        }
                    )
                if idx <= 2:
                    card_rows.append(
                        {
                            **_card_row(deck_id, "Cloudstone Curio"),
                            "oracle_id": "oracle-cloudstone-curio",
                        }
                    )
            importers.import_corpus_register(
                store, _write_csv(inputs_dir / "register.csv", register_rows)
            )
            importers.import_corpus_cards(
                store, _write_csv(inputs_dir / "corpus_cards.csv", card_rows)
            )
            store.bind_unbound(commander)

        # EDHREC inclusion signal for Shrieking Drake -> COMPLETE; Fleetfoot Panther has no EDHREC -> PARTIAL.
        from commander_lab.studio import strength

        db.execute(
            "INSERT INTO card_signal(commander_name, signal, card_name, value, numerator,"
            " denominator, source_id) VALUES (?, ?, ?, 0.8, 800, 1000, ?)",
            (
                commander,
                strength.signal_for(strength.COMMANDER_INCLUSION, strength.BRACKET_NONE),
                "Shrieking Drake",
                source_id,
            ),
        )
        # Roles for relevance/long-tail verification.
        for oracle_id, role in (
            ("oracle-shrieking-drake", "bounce"),
            ("oracle-cloudstone-curio", "bounce"),
            ("oracle-esperzoa", "bounce"),
        ):
            db.execute(
                "INSERT OR IGNORE INTO card_role(oracle_id, role, source_id) VALUES (?, ?, ?)",
                (oracle_id, role, source_id),
            )
        db.commit()
    finally:
        store.close()
    return store_dir, combos_path


def test_calculate_pool_gap_matrix_integration_and_write(tmp_path: Path) -> None:
    store_dir, combos_path = _build_gap_matrix_store(tmp_path, with_corpus=True)
    store = StudioStore.open(store_dir)
    try:
        matrix = calculate_pool_gap_matrix(store, combos_path=combos_path)

        assert matrix["schema_version"] == "pool-gap-matrix-1.1.0"
        assert matrix["total_cards"] == 5
        assert matrix["corpus_denominator"] == 6
        assert matrix["commander"] == "Chulane, Teller of Tales"

        summary = matrix["summary_counts"]
        grades = summary["coverage_grades"]
        assert isinstance(grades, dict)
        assert grades == {
            "COMPLETE": 1,  # Shrieking Drake (>=5 hits, scryfall, xmage, edhrec)
            "PARTIAL": 2,  # Chulane + Fleetfoot Panther (>=5 hits, no edhrec)
            "SPARSE": 1,  # Cloudstone Curio (2 hits)
            "UNOBSERVED_IN_CORPUS": 1,  # Esperzoa (0 hits)
        }
        assert summary["long_tail_candidates_count"] == 2  # Cloudstone Curio + Esperzoa
        assert summary["observed_in_corpus_count"] == 4
        assert summary["unobserved_in_corpus_count"] == 1
        assert summary["has_edhrec_count"] == 1
        assert summary["has_spellbook_combos_count"] == 2  # Chulane + Shrieking Drake
        assert summary["xmage_ready_count"] == 5

        cards = matrix["cards"]
        assert len(cards) == 5

        # Verify descending sort by research_priority_score
        scores = [float(c["research_priority_score"]) for c in cards]  # type: ignore[arg-type]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]
        by_name = {str(c["card_name"]): c for c in cards}
        assert by_name["Shrieking Drake"]["coverage_grade"] == "COMPLETE"
        assert by_name["Shrieking Drake"]["research_priority_score"] == 0.0
        assert by_name["Esperzoa"]["coverage_grade"] == "UNOBSERVED_IN_CORPUS"
        assert "0/6 corpus hits" in str(by_name["Esperzoa"]["notes"])

        # Verify file roundtrip
        out_file = tmp_path / "research" / "test_gap_matrix.json"
        written_path = write_gap_matrix_json(store, out_file, combos_path=combos_path)
        assert written_path.is_file()

        loaded = json.loads(written_path.read_text(encoding="utf-8"))
        assert loaded["total_cards"] == 5
        assert loaded["corpus_denominator"] == 6
        assert loaded["schema_version"] == "pool-gap-matrix-1.1.0"
        assert len(loaded["cards"]) == 5
    finally:
        store.close()


def test_calculate_pool_gap_matrix_empty_corpus_uses_zero_denominator_not_975(
    tmp_path: Path,
) -> None:
    """An empty corpus must report denominator 0, never the stale hardcoded 975."""
    store_dir, combos_path = _build_gap_matrix_store(tmp_path, with_corpus=False)
    store = StudioStore.open(store_dir)
    try:
        matrix = calculate_pool_gap_matrix(store, combos_path=combos_path)
        assert matrix["total_cards"] == 5
        assert matrix["corpus_denominator"] == 0
        assert all(int(c["corpus_denominator"]) == 0 for c in matrix["cards"])  # type: ignore[arg-type]
    finally:
        store.close()
    empty_report = generate_gap_example_report(
        {
            "schema_version": "pool-gap-matrix-1.1.0",
            "description": "empty",
            "commander": "Chulane, Teller of Tales",
            "generated_at_utc": "2026-11-24T00:00:00Z",
            "total_cards": 0,
            "summary_counts": {},
            "cards": [],
        }  # type: ignore[typeddict-item]
    )
    assert empty_report["corpus_denominator"] == 0


def test_source_inventory_payload_filtered_by_status() -> None:
    verified_payload = source_inventory_payload(status="VERIFIED")
    assert verified_payload["schema_version"] == "evidence-source-inventory-1.0.0"
    assert verified_payload["total_sources"] == 5
    assert len(verified_payload["sources"]) == 5
    for s in verified_payload["sources"]:
        assert s["status"] == "VERIFIED"

    review_payload = source_inventory_payload(status="REVIEW")
    assert review_payload["total_sources"] == 5
    assert len(review_payload["sources"]) == 5
    for s in review_payload["sources"]:
        assert s["status"] == "REVIEW"


def test_generate_gap_example_report() -> None:
    # Build a minimal matrix with 1 card of each grade
    matrix: PoolGapMatrixPayload = {
        "schema_version": "pool-gap-matrix-1.1.0",
        "description": "test",
        "commander": "Chulane, Teller of Tales",
        "generated_at_utc": "2026-11-11T12:00:00Z",
        "total_cards": 4,
        "corpus_denominator": 975,
        "summary_counts": {"COMPLETE": 1, "SPARSE": 1, "PARTIAL": 1, "UNOBSERVED_IN_CORPUS": 1},
        "cards": [
            {
                "oracle_id": "c1",
                "card_name": "Card Complete",
                "mana_value": 2.0,
                "color_identity": "U",
                "type_line": "Creature",
                "has_scryfall_facts": True,
                "has_xmage_rules": True,
                "corpus_hits": 10,
                "corpus_denominator": 975,
                "edhrec_hits": 50,
                "edhrec_denominator": 100,
                "edhrec_inclusion_pct": 50.0,
                "has_spellbook_combos": False,
                "playgroup_observed_games": None,
                "tournament_hits": None,
                "coverage_grade": "COMPLETE",
                "research_priority_score": 0.05,
                "is_long_tail_candidate": False,
                "notes": "ok",
            },
            {
                "oracle_id": "c2",
                "card_name": "Card Sparse",
                "mana_value": 3.0,
                "color_identity": "G",
                "type_line": "Creature",
                "has_scryfall_facts": True,
                "has_xmage_rules": True,
                "corpus_hits": 2,
                "corpus_denominator": 975,
                "edhrec_hits": None,
                "edhrec_denominator": None,
                "edhrec_inclusion_pct": None,
                "has_spellbook_combos": False,
                "playgroup_observed_games": None,
                "tournament_hits": None,
                "coverage_grade": "SPARSE",
                "research_priority_score": 0.35,
                "is_long_tail_candidate": True,
                "notes": "sparse",
            },
            {
                "oracle_id": "c3",
                "card_name": "Card Partial",
                "mana_value": 4.0,
                "color_identity": "W",
                "type_line": "Enchantment",
                "has_scryfall_facts": True,
                "has_xmage_rules": True,
                "corpus_hits": 8,
                "corpus_denominator": 975,
                "edhrec_hits": None,
                "edhrec_denominator": None,
                "edhrec_inclusion_pct": None,
                "has_spellbook_combos": False,
                "playgroup_observed_games": None,
                "tournament_hits": None,
                "coverage_grade": "PARTIAL",
                "research_priority_score": 0.20,
                "is_long_tail_candidate": False,
                "notes": "partial",
            },
            {
                "oracle_id": "c4",
                "card_name": "Card Unobserved",
                "mana_value": 1.0,
                "color_identity": "U",
                "type_line": "Creature",
                "has_scryfall_facts": True,
                "has_xmage_rules": True,
                "corpus_hits": 0,
                "corpus_denominator": 975,
                "edhrec_hits": None,
                "edhrec_denominator": None,
                "edhrec_inclusion_pct": None,
                "has_spellbook_combos": False,
                "playgroup_observed_games": None,
                "tournament_hits": None,
                "coverage_grade": "UNOBSERVED_IN_CORPUS",
                "research_priority_score": 0.48,
                "is_long_tail_candidate": True,
                "notes": "unobserved",
            },
        ],
    }

    report = generate_gap_example_report(matrix, sample_size_per_grade=1)
    assert report["schema_version"] == "gap-example-report-1.0.0"
    assert report["total_pool_cards"] == 4
    assert report["commander"] == "Chulane, Teller of Tales"

    examples = report["examples_by_grade"]
    assert isinstance(examples, dict)
    assert len(examples) == 4
    assert len(examples["COMPLETE"]) == 1
    assert examples["COMPLETE"][0]["card_name"] == "Card Complete"
    assert len(examples["SPARSE"]) == 1
    assert examples["SPARSE"][0]["card_name"] == "Card Sparse"
    assert len(examples["PARTIAL"]) == 1
    assert examples["PARTIAL"][0]["card_name"] == "Card Partial"
    assert len(examples["UNOBSERVED_IN_CORPUS"]) == 1
    assert examples["UNOBSERVED_IN_CORPUS"][0]["card_name"] == "Card Unobserved"


def test_cli_sources_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. Default sources list
    rc = studio_main(["sources"])
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "evidence-source-inventory-1.0.0"
    assert payload["total_sources"] == 12

    # 2. Verified-only flag
    rc_v = studio_main(["sources", "--verified-only"])
    assert rc_v == 0
    captured_v = capsys.readouterr()
    payload_v = json.loads(captured_v.out)
    assert payload_v["total_sources"] == 5
    assert len(payload_v["sources"]) == 5

    # 3. Out flag writes to file
    out_file = tmp_path / "sources_test.json"
    rc_out = studio_main(["sources", "--out", str(out_file), "--verified-only"])
    assert rc_out == 0
    captured_out = capsys.readouterr()
    assert str(out_file) in captured_out.out
    assert out_file.is_file()
    loaded_out = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded_out["total_sources"] == 5

    # 4. Gap report CLI (against an isolated synthetic store, never Path.home() or repo CWD files)
    store_dir, _combos_path = _build_gap_matrix_store(tmp_path, with_corpus=True)
    monkeypatch.chdir(tmp_path)
    gap_out_file = tmp_path / "gap_test.json"
    rc_gap = studio_main(
        ["--data", str(store_dir), "sources", "--gap-report", "--gap-out", str(gap_out_file)]
    )
    assert rc_gap == 0
    captured_gap = capsys.readouterr()
    summary = json.loads(captured_gap.out)
    assert summary["total_cards"] == 5
    assert summary["corpus_denominator"] == 6
    assert gap_out_file.is_file()

    # 5. Example report CLI
    rc_ex = studio_main(["--data", str(store_dir), "sources", "--example-report"])
    assert rc_ex == 0
    captured_ex = capsys.readouterr()
    ex_report = json.loads(captured_ex.out)
    assert ex_report["schema_version"] == "gap-example-report-1.0.0"
    assert ex_report["total_pool_cards"] == 5
    assert ex_report["corpus_denominator"] == 6
    assert "UNOBSERVED_IN_CORPUS" in ex_report["examples_by_grade"]
    assert len(ex_report["examples_by_grade"]["UNOBSERVED_IN_CORPUS"]) == 1


def _extract_local_paths(entries: list[dict[str, object]]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for entry in entries:
        source_id = str(entry.get("source_id", ""))
        for field in ("direct_url", "access_evidence_url"):
            val = entry.get(field)
            if isinstance(val, str) and val.startswith("local:"):
                found.append((source_id, val.removeprefix("local:")))
        refs = entry.get("reference_urls")
        if isinstance(refs, (list, tuple)):
            for ref in refs:
                if isinstance(ref, str) and ref.startswith("local:"):
                    found.append((source_id, ref.removeprefix("local:")))
    return found


def test_every_local_path_in_registry_exists() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    py_entries = [s.to_dict() for s in QUALIFIED_SOURCES]
    py_locals = _extract_local_paths(py_entries)
    assert len(py_locals) > 0
    missing_py = [f"{sid}: local:{rel}" for sid, rel in py_locals if not (repo_root / rel).exists()]
    assert not missing_py, f"Missing local: paths in sources.py: {missing_py}"

    inventory_file = repo_root / "data" / "provenance" / "source_inventory.json"
    assert inventory_file.is_file()
    inv_data = json.loads(inventory_file.read_text(encoding="utf-8"))
    json_entries = inv_data.get("sources", [])
    assert isinstance(json_entries, list)
    json_locals = _extract_local_paths(json_entries)
    assert len(json_locals) > 0
    missing_json = [
        f"{sid}: local:{rel}" for sid, rel in json_locals if not (repo_root / rel).exists()
    ]
    assert not missing_json, f"Missing local: paths in source_inventory.json: {missing_json}"


def test_every_source_has_valid_access_status_and_json_matches_code() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    inventory_file = repo_root / "data" / "provenance" / "source_inventory.json"
    inv_data = json.loads(inventory_file.read_text(encoding="utf-8"))

    # Committed JSON must stay in sync with source_inventory_payload()
    expected_payload = json.loads(json.dumps(source_inventory_payload()))
    assert inv_data == expected_payload

    allowed = set(ACCESS_STATUSES)
    for entry in inv_data["sources"]:
        assert entry["access_status"] in allowed
        assert isinstance(entry["access_evidence_url"], str)
        assert entry["access_evidence_url"].startswith(("https://", "local:"))
        _assert_check_date(entry["access_checked_at_utc"], entry["access_evidence_url"])

    # Key access classifications and separation from data quality status (Issue #1546)
    by_id = {entry["source_id"]: entry for entry in inv_data["sources"]}
    assert by_id["scryfall:bulk-oracle"]["access_status"] == "ok_with_conditions"
    assert by_id["scryfall:tagger"]["access_status"] == "ok_with_conditions"
    assert by_id["spellbook:variants-api"]["access_status"] == "ok_with_conditions"
    assert by_id["playgroup:card-atlas"]["access_status"] == "ok_with_conditions"
    assert by_id["playgroup:chulane"]["access_status"] == "ok_with_conditions"
    assert by_id["edhrec:chulane"]["access_status"] == "prohibited"
    assert by_id["edhrec:chulane"]["status"] == "VERIFIED"
    assert by_id["archidekt:decks"]["access_status"] == "prohibited"
    assert by_id["moxfield:decks"]["access_status"] == "prohibited"
    assert by_id["tournament:cedh-meta"]["access_status"] == "unclear"
    # The corpus stems from prohibited origin sources (EDHREC, Archidekt): stock only (#1557)
    assert by_id["repo:chulane-corpus"]["access_status"] == "prohibited"
    assert by_id["repo:chulane-corpus"]["status"] == "VERIFIED"
    assert by_id["xmage:card-facts"]["access_status"] == "ok"
    assert by_id["xmage:card-facts"]["access_checked_at_utc"] is None


def _load_script_module(rel_path: str, name: str) -> object:
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / rel_path
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_spellbook_combos_fetch_bulk_parsing_and_generic_user_agent(tmp_path: Path) -> None:
    mod = _load_script_module("scripts/spellbook_combos_fetch.py", "spellbook_combos_fetch_1546")

    # Bulk URL points to official variants.json.gz, not paginated REST API
    assert mod.DEFAULT_BULK_URL == "https://json.commanderspellbook.com/variants.json.gz"  # type: ignore[attr-defined]
    mod.check_bulk_url(mod.DEFAULT_BULK_URL)  # type: ignore[attr-defined]

    # Generic default User-Agent across updated fetch scripts (no project/repo/person tokens)
    forbidden = (
        "commander",
        "playtest",
        "lab",
        "github",
        "moeendres",
        "http",
        "mozilla",
        "chrome",
        "safari",
        "@",
    )
    for rel_path, mod_name in (
        ("scripts/spellbook_combos_fetch.py", "ua_check_spellbook_fetch"),
        ("scripts/build_spellbook_shells.py", "ua_check_spellbook_shells"),
        ("scripts/build_pilot_card_knowledge.py", "ua_check_pilot_knowledge"),
        ("scripts/import_oracle_cards.py", "ua_check_import_oracle"),
        ("scripts/import_scryfall_oracle_tags.py", "ua_check_oracle_tags"),
        ("scripts/process_scryfall_rulings.py", "ua_check_rulings"),
        ("scripts/studio_edhrec_provenance/capture_public_chulane.py", "ua_check_edhrec_capture"),
        ("scripts/collect_topdeck_decks.py", "ua_check_topdeck"),
    ):
        script_mod = _load_script_module(rel_path, mod_name)
        ua = str(script_mod.DEFAULT_USER_AGENT)  # type: ignore[attr-defined]
        assert ua.strip() != "", f"Blank DEFAULT_USER_AGENT in {rel_path}"
        ua_low = ua.lower()
        for token in forbidden:
            assert token not in ua_low, f"Forbidden token {token!r} in {rel_path} UA: {ua!r}"

    # The Scryfall roles fetch inside the package uses the same generic identity (#1557 point 4)
    from commander_lab.studio import roles

    roles_agent = roles._USER_AGENT.lower()
    for token in forbidden:
        assert token not in roles_agent, f"Forbidden token {token!r} in roles UA"

    # Offline bulk parsing test with synthetic .json and .json.gz fixtures
    synthetic_bulk = {
        "variants": [
            {
                "id": "sb-001",
                "identity": "WUG",
                "status": "OK",
                "spoiler": False,
                "legalities": {"commander": True},
                "popularity": 120,
                "uses": [
                    {"card": {"name": "Chulane, Teller of Tales"}, "mustBeCommander": True},
                    {"card": {"name": "Shrieking Drake"}, "mustBeCommander": False},
                ],
                "produces": [{"feature": {"name": "Infinite draw triggers"}}],
            },
            {
                "id": "sb-002",
                "identity": "UBR",
                "status": "OK",
                "spoiler": False,
                "legalities": {"commander": True},
                "uses": [
                    {"card": {"name": "Thassa's Oracle"}, "mustBeCommander": False},
                    {"card": {"name": "Demonic Consultation"}, "mustBeCommander": False},
                ],
                "produces": [{"feature": {"name": "Win the game"}}],
            },
        ]
    }
    raw_bytes = json.dumps(synthetic_bulk).encode("utf-8")

    plain_path = tmp_path / "variants.json"
    plain_path.write_bytes(raw_bytes)
    gz_path = tmp_path / "variants.json.gz"
    gz_path.write_bytes(gzip.compress(raw_bytes))

    for fixture_path in (plain_path, gz_path):
        facts = mod._load_bulk_variants(  # type: ignore[attr-defined]
            fixture_path, commander="Chulane, Teller of Tales"
        )
        assert len(facts) == 2
        assert facts[0].variant_id == "sb-001"
        assert facts[0].names == ("Chulane, Teller of Tales", "Shrieking Drake")
        assert facts[0].foreign_commander is False
        assert facts[0].produces == ("Infinite draw triggers",)
        assert facts[0].edhrec_decks == 120

        generated, counts = mod._select_variants(  # type: ignore[attr-defined]
            facts,
            corpus_keys={"chulane, teller of tales", "shrieking drake"},
            preserved_sets=set(),
            commander="Chulane, Teller of Tales",
            note="synthetic bulk test",
        )
        assert counts["fetched"] == 2
        assert counts["identity_outside_wug"] == 1
        assert counts["kept"] == 1
        assert [entry["combo_id"] for entry in generated] == ["chulane-sb-sb-001"]


def test_a_snapshot_claiming_source_records_a_snapshot() -> None:
    # reproducibility DETERMINISTIC_OFFLINE_SNAPSHOT needs a retrieval time and a snapshot id;
    # without them the register says UNKNOWN_NO_SNAPSHOT_RECORDED, never a fabricated claim.
    for source in QUALIFIED_SOURCES:
        if source.reproducibility == "DETERMINISTIC_OFFLINE_SNAPSHOT":
            assert source.retrieved_at_utc is not None, source.source_id
            assert source.snapshot_id is not None, source.source_id
        if source.retrieved_at_utc is None and source.snapshot_id is None:
            assert source.reproducibility != "DETERMINISTIC_OFFLINE_SNAPSHOT", source.source_id
    assert get_source("scryfall:tagger").reproducibility == "UNKNOWN_NO_SNAPSHOT_RECORDED"
    assert get_source("repo:chulane-corpus").reproducibility == "UNKNOWN_NO_SNAPSHOT_RECORDED"


def test_stock_from_prohibited_sources_carries_the_owner_decision_note() -> None:
    corpus = get_source("repo:chulane-corpus")
    assert corpus.access_status == "prohibited"
    rationale = corpus.status_rationale
    assert "Owner-Entscheid #1557" in rationale
    assert "keine Nachernte" in rationale
    assert "Herkunft verbotene Quellen" in rationale
    for origin in ("EDHREC", "Archidekt"):
        assert origin in corpus.license_terms
    assert "#1557" in get_source("edhrec:chulane").status_rationale
    assert "#1557" in get_source("archidekt:decks").status_rationale
    tournament = get_source("tournament:cedh-meta")
    assert "#1557 point 3" in tournament.allowed_retrieval_method
    assert "no API key" in tournament.allowed_retrieval_method.lower() or (
        "no topdeck api key" in tournament.allowed_retrieval_method.lower()
    )


def test_register_has_no_unsourced_pool_size_and_no_personal_names() -> None:
    text = json.dumps([s.to_dict() for s in QUALIFIED_SOURCES], ensure_ascii=False)
    assert "801" not in text  # pool size: 927 in the gap matrix of 2026-11-12, dated where used
    assert "7,231" not in text
    for token in ("moeendres", "/home/", "C:\\", "Moritz"):
        assert token not in text
    # Playgroup's licence claim is stated as unresolved, not as fact
    for source_id in ("playgroup:card-atlas", "playgroup:chulane"):
        license_text = get_source(source_id).license_terms
        assert "ungeklärt" in license_text and "no legal review" in license_text
    chulane = get_source("playgroup:chulane")
    assert "449 / 1,111" in chulane.status_rationale  # other counting, kept apart
    assert "2026-11-08" in chulane.status_rationale
    assert "2026-11-08" in chulane.observation_period
