"""Unit tests for Scryfall Tagger bulk import and 24-taxonomy mapping.

Tests fixture parsing, error paths (missing file, corrupt JSON line, unknown label),
negative vocabulary verification (stax, token, card-selection), alias mapping,
DFC frontname resolution, and lossless transactional merge into StudioStore.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.import_scryfall_oracle_tags import (
    KNOWN_ALIASES,
    NEGATIVE_VOCABULARY_TARGETS,
    ORIGIN_TAGGER_BULK,
    ROLE_TAXONOMY_24,
    audit_vocabulary,
    import_tagger_bulk_claims,
    load_bulk_graph,
    parse_tag_line,
    resolve_front_name,
)

from commander_lab.studio.roles import ORIGIN_TAGGER
from commander_lab.studio.store import DataClass, StudioStore

OID_SOL_RING = "sol-ring-oracle-uuid-0001"
OID_SWEEPER_CARD = "wrath-of-god-oracle-uuid-0002"
OID_DFC_CARD = "wear-tear-oracle-uuid-0003"
OID_GRAVEYARD_CARD = "rest-in-peace-oracle-uuid-0004"
OID_ANTHEM_CARD = "glorious-anthem-oracle-uuid-0005"


def _sample_bulk_jsonl() -> str:
    """Return a minimal valid bulk JSONL string covering hierarchy, aliases, and direct tags."""
    records: list[dict[str, object]] = [
        # 1. Direct tag: ramp
        {
            "object": "tag",
            "id": "tag-ramp-001",
            "label": "ramp",
            "slug": "ramp",
            "aliases": ["mana-ramp"],
            "parent_ids": [],
            "child_ids": ["tag-rock-002"],
            "taggings": [{"oracle_id": OID_SOL_RING, "weight": "high"}],
        },
        # 2. Child tag: mana-rock (child of ramp)
        {
            "object": "tag",
            "id": "tag-rock-002",
            "label": "mana rock",
            "slug": "mana-rock",
            "aliases": ["manarock"],
            "parent_ids": ["tag-ramp-001"],
            "child_ids": [],
            "taggings": [{"oracle_id": OID_SOL_RING, "weight": "high"}],
        },
        # 3. Aliased tag: sweeper (maps to board_wipe)
        {
            "object": "tag",
            "id": "tag-sweeper-003",
            "label": "sweeper",
            "slug": "sweeper",
            "aliases": ["board-wipe"],
            "parent_ids": [],
            "child_ids": [],
            "taggings": [{"oracle_id": OID_SWEEPER_CARD, "weight": "high"}],
        },
        # 4. Aliased tag: hate-graveyard (maps to graveyard_hate)
        {
            "object": "tag",
            "id": "tag-grave-004",
            "label": "hate graveyard",
            "slug": "hate-graveyard",
            "aliases": ["graveyard-hate"],
            "parent_ids": [],
            "child_ids": [],
            "taggings": [{"oracle_id": OID_GRAVEYARD_CARD, "weight": "high"}],
        },
        # 5. Extension tag: anthem
        {
            "object": "tag",
            "id": "tag-anthem-005",
            "label": "anthem",
            "slug": "anthem",
            "aliases": [],
            "parent_ids": [],
            "child_ids": [],
            "taggings": [{"oracle_id": OID_ANTHEM_CARD, "weight": "median"}],
        },
        # 6. Unrelated tag (should be ignored by taxonomy)
        {
            "object": "tag",
            "id": "tag-unrelated-006",
            "label": "hats in art",
            "slug": "hats-in-art",
            "aliases": [],
            "parent_ids": [],
            "child_ids": [],
            "taggings": [{"oracle_id": OID_SOL_RING, "weight": "low"}],
        },
    ]
    return "\n".join(json.dumps(r) for r in records) + "\n"


def _create_mock_store(tmp_path: Path) -> StudioStore:
    """Create a StudioStore populated with test cards."""
    store = StudioStore.open(tmp_path / "studio")
    with store.connection as db:
        source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title="test_cards.xlsx",
            sha256="testsha000000000000000000000000000000000000000000000000000000000",
        )
        test_cards: list[tuple[str, str, str, str, str, float, str, str, int, str]] = [
            (
                "card:test:01",
                OID_SOL_RING,
                "Sol Ring",
                "",
                "{1}",
                1.0,
                "Artifact",
                "{T}: Add {C}{C}.",
                0,
                source_id,
            ),
            (
                "card:test:02",
                OID_SWEEPER_CARD,
                "Wrath of God",
                "W",
                "{2}{W}{W}",
                4.0,
                "Sorcery",
                "Destroy all creatures.",
                0,
                source_id,
            ),
            (
                "card:test:03",
                OID_DFC_CARD,
                "Wear // Tear",
                "RW",
                "{1}{R} // {W}",
                3.0,
                "Instant // Instant",
                "Destroy target artifact. // Destroy target enchantment.",
                0,
                source_id,
            ),
            (
                "card:test:04",
                OID_GRAVEYARD_CARD,
                "Rest in Peace",
                "W",
                "{1}{W}",
                2.0,
                "Enchantment",
                "Exile all graveyards.",
                0,
                source_id,
            ),
            (
                "card:test:05",
                OID_ANTHEM_CARD,
                "Glorious Anthem",
                "W",
                "{1}{W}{W}",
                3.0,
                "Enchantment",
                "Creatures you control get +1/+1.",
                0,
                source_id,
            ),
        ]
        db.executemany(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, mana_cost, "
            "mana_value, type_line, oracle_text, is_basic_land, source_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            test_cards,
        )
        db.executemany(
            "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, available_lower_bound, quantity_exact, source_id) "
            "VALUES (?, 1, 1, 0, 1, 1, ?)",
            [(c[0], source_id) for c in test_cards],
        )
    return store


def test_missing_bulk_file_raises_error(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.jsonl"
    with pytest.raises(FileNotFoundError, match="Bulk file not found"):
        load_bulk_graph(non_existent)


def test_corrupt_jsonl_line_raises_error() -> None:
    bad_line = "{not valid json"
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_tag_line(bad_line, 1)


def test_missing_id_in_tag_line_raises_error() -> None:
    missing_id = json.dumps({"label": "test", "slug": "test"})
    with pytest.raises(ValueError, match="missing or invalid 'id'"):
        parse_tag_line(missing_id, 1)


def test_dfc_front_name_resolution() -> None:
    assert resolve_front_name("Wear // Tear") == "Wear"
    assert resolve_front_name("Delver of Secrets // Insectile Aberration") == "Delver of Secrets"
    assert resolve_front_name("Sol Ring") == "Sol Ring"


def test_negative_vocabulary_proof(tmp_path: Path) -> None:
    bulk_file = tmp_path / "mock_bulk.jsonl"
    bulk_file.write_text(_sample_bulk_jsonl(), encoding="utf-8")

    graph = load_bulk_graph(bulk_file)
    audit = audit_vocabulary(graph)

    assert audit.negative_audit_passed is True
    for target in NEGATIVE_VOCABULARY_TARGETS:
        assert audit.negative_hits[target] == 0


def test_alias_mapping_and_hierarchy(tmp_path: Path) -> None:
    bulk_file = tmp_path / "mock_bulk.jsonl"
    bulk_file.write_text(_sample_bulk_jsonl(), encoding="utf-8")

    graph = load_bulk_graph(bulk_file)

    # Alias sweeper -> board_wipe
    sweeper_ids, rule_sweeper = graph.get_descendant_oracle_ids("sweeper")
    assert OID_SWEEPER_CARD in sweeper_ids
    assert "sweeper" in rule_sweeper

    # Alias hate-graveyard -> graveyard_hate
    grave_ids, rule_grave = graph.get_descendant_oracle_ids("hate-graveyard")
    assert OID_GRAVEYARD_CARD in grave_ids
    assert "hate-graveyard" in rule_grave

    # Known alias mapping lookup
    assert KNOWN_ALIASES["board-wipe"] == "sweeper"
    assert KNOWN_ALIASES["graveyard-hate"] == "hate-graveyard"

    # Hierarchy: ramp has rock as child; querying ramp includes child's cards
    ramp_ids, rule_ramp = graph.get_descendant_oracle_ids("ramp")
    assert OID_SOL_RING in ramp_ids
    assert "hierarchy" in rule_ramp


def test_lossless_claim_preservation_and_priority(tmp_path: Path) -> None:
    store = _create_mock_store(tmp_path)
    bulk_file = tmp_path / "mock_bulk.jsonl"
    bulk_file.write_text(_sample_bulk_jsonl(), encoding="utf-8")

    try:
        # Pre-seed an existing claim from SCRYFALL_TAGGER_ORIGINAL
        with store.connection as db:
            src_id = store.register_source(
                data_class=DataClass.ORIGINAL_SOURCE,
                title="search_api_snapshot.json",
                sha256="preseed000000000000000000000000000000000000000000000000000000000",
            )
            db.execute(
                "INSERT INTO card_role_claim(oracle_id, role, role_origin, scope_key, source_id, "
                "original_tag, mapping_rule) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    OID_SOL_RING,
                    "ramp",
                    ORIGIN_TAGGER,
                    "WUG",
                    src_id,
                    "ramp",
                    "search_api",
                ),
            )
            db.execute(
                "INSERT INTO card_role(oracle_id, role, source_id) VALUES (?, ?, ?)",
                (OID_SOL_RING, "ramp", src_id),
            )

        # Import bulk claims
        stats = import_tagger_bulk_claims(store, bulk_file, dry_run=False)

        assert stats.claims_written >= 4
        assert stats.matched_collection_cards >= 3

        # Assert card_role_claim contains BOTH claims for Sol Ring ramp
        with store.connection as db:
            claims = db.execute(
                "SELECT role_origin, mapping_rule FROM card_role_claim WHERE oracle_id = ? AND role = 'ramp' "
                "ORDER BY role_origin",
                (OID_SOL_RING,),
            ).fetchall()
            origins = [str(r[0]) for r in claims]
            assert ORIGIN_TAGGER in origins
            assert ORIGIN_TAGGER_BULK in origins

            # In card_role, SCRYFALL_TAGGER_ORIGINAL wins over SCRYFALL_TAGGER_BULK
            role_row = db.execute(
                "SELECT c.role_origin, cr.source_id FROM card_role cr "
                "JOIN card_role_claim c ON cr.oracle_id = c.oracle_id AND cr.role = c.role AND cr.source_id = c.source_id "
                "WHERE cr.oracle_id = ? AND cr.role = 'ramp'",
                (OID_SOL_RING,),
            ).fetchone()
            assert role_row is not None
            assert str(role_row[0]) == ORIGIN_TAGGER
            assert str(role_row[1]) == src_id

            # New card (Wrath of God) receives SCRYFALL_TAGGER_BULK role in card_role
            sweeper_row = db.execute(
                "SELECT c.role_origin FROM card_role cr "
                "JOIN card_role_claim c ON cr.oracle_id = c.oracle_id AND cr.role = c.role AND cr.source_id = c.source_id "
                "WHERE cr.oracle_id = ? AND cr.role = 'board_wipe'",
                (OID_SWEEPER_CARD,),
            ).fetchone()
            assert sweeper_row is not None
            assert str(sweeper_row[0]) == ORIGIN_TAGGER_BULK
    finally:
        store.close()


def test_dry_run_leaves_database_unmutated(tmp_path: Path) -> None:
    store = _create_mock_store(tmp_path)
    bulk_file = tmp_path / "mock_bulk.jsonl"
    bulk_file.write_text(_sample_bulk_jsonl(), encoding="utf-8")

    try:
        stats = import_tagger_bulk_claims(store, bulk_file, dry_run=True)
        assert stats.claims_written >= 4

        with store.connection as db:
            claim_count = db.execute("SELECT COUNT(*) FROM card_role_claim").fetchone()
            assert claim_count is not None
            assert int(claim_count[0]) == 0
    finally:
        store.close()


def test_unknown_labels_ignored_safely(tmp_path: Path) -> None:
    bulk_file = tmp_path / "mock_bulk.jsonl"
    bulk_file.write_text(_sample_bulk_jsonl(), encoding="utf-8")

    graph = load_bulk_graph(bulk_file)
    unrelated_id = graph.find_tag_id("hats-in-art")
    assert unrelated_id is not None

    # Unrelated tag does not leak into 24 taxonomy roles
    for _role, slug in ROLE_TAXONOMY_24.items():
        assert slug != "hats-in-art"
