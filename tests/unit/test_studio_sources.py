"""Tests for the Commander Studio evidence source registry (P0 Deliverable 1 & 2).

Verifies the systematic qualification of the 9 prioritized sources, schema integrity,
explicit null-timestamp preservation, JSON inventory generation, card coverage record calculation,
long-tail candidate identification, and full 801-card pool gap matrix calculation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.sources import (
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
    (6, "active_drive:chulane-corpus-975", "VERIFIED"),
    (7, "tournament:cedh-meta", "REVIEW"),
    (8, "xmage:card-facts", "VERIFIED"),
    (9, "scryfall:tagger", "REVIEW"),
)


def test_qualified_sources_covers_all_nine_priorities_in_exact_order() -> None:
    assert len(QUALIFIED_SOURCES) == 9
    priorities = [s.priority for s in QUALIFIED_SOURCES]
    assert priorities == list(range(1, 10))

    assert len(EXPECTED_PRIORITIES) == 9
    for (expected_prio, expected_id, expected_status), source in zip(
        EXPECTED_PRIORITIES, QUALIFIED_SOURCES, strict=True
    ):
        assert source.priority == expected_prio
        assert source.source_id == expected_id
        assert source.status == expected_status


def test_every_source_has_all_seventeen_dimensions_populated() -> None:
    allowed_statuses = {"VERIFIED", "REVIEW", "UNAVAILABLE"}
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

    assert len(QUALIFIED_SOURCES) == 9
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

        # Governance, licensing & reproducibility
        assert source.double_counting_risk.strip() != ""
        assert source.license_terms.strip() != ""
        assert source.allowed_retrieval_method.strip() != ""
        assert source.reproducibility in {
            "DETERMINISTIC_OFFLINE_SNAPSHOT",
            "REPRODUCIBLE_API",
            "DYNAMIC_EPHEMERAL_WEB",
            "MANUAL_ARCHIVE",
        }
        assert isinstance(source.bias_risks, tuple)
        assert len(source.bias_risks) > 0
        assert source.status in allowed_statuses
        assert source.status_rationale.strip() != ""


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
    assert xmage.retrieved_at_utc == "2026-11-10T00:00:00Z"
    assert xmage.snapshot_id == "xmage-card-facts-v1"


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
        "active_drive:chulane-corpus-975",
        "xmage:card-facts",
    }

    review = list_sources(status="REVIEW")
    assert len(review) == 4
    assert {s.source_id for s in review} == {
        "playgroup:card-atlas",
        "playgroup:chulane",
        "tournament:cedh-meta",
        "scryfall:tagger",
    }

    unavailable = list_sources(status="UNAVAILABLE")
    assert len(unavailable) == 0


def test_source_inventory_payload_matches_schema() -> None:
    payload = source_inventory_payload()
    assert payload["schema_version"] == "evidence-source-inventory-1.0.0"
    assert payload["total_sources"] == 9
    assert payload["status_counts"]["VERIFIED"] == 5
    assert payload["status_counts"]["REVIEW"] == 4
    assert payload["status_counts"]["UNAVAILABLE"] == 0
    assert len(payload["sources"]) == 9


def test_write_source_inventory_json_roundtrip(tmp_path: Path) -> None:
    target_file = tmp_path / "provenance" / "test_sources.json"
    written_path = write_source_inventory_json(target_file)
    assert written_path.is_file()

    loaded = json.loads(written_path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "evidence-source-inventory-1.0.0"
    assert loaded["total_sources"] == 9
    assert len(loaded["sources"]) == 9
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


def test_calculate_pool_gap_matrix_integration_and_write(tmp_path: Path) -> None:
    store_dir = Path.home() / ".local" / "share" / "commander-studio"
    db_path = store_dir / "studio.sqlite3"
    if not db_path.is_file():
        pytest.skip(f"Studio sqlite DB not found at {db_path}")

    store = StudioStore.open(store_dir)
    matrix = calculate_pool_gap_matrix(store)

    assert matrix["schema_version"] == "pool-gap-matrix-1.0.0"
    assert matrix["total_cards"] == 801
    assert matrix["corpus_denominator"] == 975
    assert matrix["commander"] == "Chulane, Teller of Tales"

    summary = matrix["summary_counts"]
    grades = summary["coverage_grades"]
    assert isinstance(grades, dict)
    assert grades["COMPLETE"] == 219
    assert grades["SPARSE"] == 202
    assert grades["PARTIAL"] == 8
    assert grades["UNOBSERVED_IN_CORPUS"] == 372
    assert summary["long_tail_candidates_count"] == 413
    assert summary["observed_in_corpus_count"] == 429
    assert summary["unobserved_in_corpus_count"] == 372
    assert summary["xmage_ready_count"] == 801

    cards = matrix["cards"]
    assert len(cards) == 801

    # Verify descending sort by research_priority_score
    scores = [float(c["research_priority_score"]) for c in cards]  # type: ignore[arg-type]
    assert len(scores) == 801
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]

    # Verify file roundtrip
    out_file = tmp_path / "research" / "test_gap_matrix.json"
    written_path = write_gap_matrix_json(store, out_file)
    assert written_path.is_file()

    loaded = json.loads(written_path.read_text(encoding="utf-8"))
    assert loaded["total_cards"] == 801
    assert loaded["schema_version"] == "pool-gap-matrix-1.0.0"
    assert len(loaded["cards"]) == 801


def test_source_inventory_payload_filtered_by_status() -> None:
    verified_payload = source_inventory_payload(status="VERIFIED")
    assert verified_payload["schema_version"] == "evidence-source-inventory-1.0.0"
    assert verified_payload["total_sources"] == 5
    assert len(verified_payload["sources"]) == 5
    for s in verified_payload["sources"]:
        assert s["status"] == "VERIFIED"

    review_payload = source_inventory_payload(status="REVIEW")
    assert review_payload["total_sources"] == 4
    assert len(review_payload["sources"]) == 4
    for s in review_payload["sources"]:
        assert s["status"] == "REVIEW"


def test_generate_gap_example_report() -> None:
    # Build a minimal matrix with 1 card of each grade
    matrix: PoolGapMatrixPayload = {
        "schema_version": "pool-gap-matrix-1.0.0",
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
                "edhrec_lift": 50.0,
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
                "edhrec_lift": None,
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
                "edhrec_lift": None,
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
                "edhrec_lift": None,
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


def test_cli_sources_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # 1. Default sources list
    rc = studio_main(["sources"])
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "evidence-source-inventory-1.0.0"
    assert payload["total_sources"] == 9

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

    # 4. Gap report CLI (skip if DB not present)
    store_dir = Path.home() / ".local" / "share" / "commander-studio"
    if (store_dir / "studio.sqlite3").is_file():
        gap_out_file = tmp_path / "gap_test.json"
        rc_gap = studio_main(["sources", "--gap-report", "--gap-out", str(gap_out_file)])
        assert rc_gap == 0
        captured_gap = capsys.readouterr()
        summary = json.loads(captured_gap.out)
        assert summary["total_cards"] == 801
        assert gap_out_file.is_file()

        # 5. Example report CLI
        rc_ex = studio_main(["sources", "--example-report"])
        assert rc_ex == 0
        captured_ex = capsys.readouterr()
        ex_report = json.loads(captured_ex.out)
        assert ex_report["schema_version"] == "gap-example-report-1.0.0"
        assert ex_report["total_pool_cards"] == 801
        assert "UNOBSERVED_IN_CORPUS" in ex_report["examples_by_grade"]
