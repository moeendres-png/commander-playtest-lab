"""Unit tests for Scryfall Tagger bulk import and studio-roles-2 integration.

Tests:
- Streaming JSONL bulk parser and error paths
- Alias separation: aliases never overwrite slugs or labels
- Hierarchy resolution with valid child counting
- True negative vocabulary verification (stax, token, card-selection)
- Generation of valid studio-roles-2 role snapshot file
- Integration with standard roles.import_roles into StudioStore
- Cross-source Oracle ID resolution (collection + corpus + scryfall)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.import_scryfall_oracle_tags import (
    NEGATIVE_VOCABULARY_TARGETS,
    audit_vocabulary,
    export_studio_roles_file,
    import_tagger_bulk,
    load_bulk_graph,
    parse_tag_line,
    resolve_all_store_oracle_ids,
)

from commander_lab.studio.roles import (
    ORIGIN_TAGGER,
    ROLES,
    read_role_file,
)
from commander_lab.studio.store import DataClass, StudioStore

OID_SOL_RING = "sol-ring-oracle-uuid-0001"
OID_SWEEPER_CARD = "wrath-of-god-oracle-uuid-0002"
OID_CORPUS_CARD = "cultivate-oracle-uuid-0003"
OID_SCRYFALL_CARD = "counterspell-oracle-uuid-0004"


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
            "taggings": [{"oracle_id": OID_SOL_RING}],
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
            "taggings": [{"oracle_id": OID_SOL_RING}],
        },
        # 3. Aliased tag: sweeper (canonical for board-wipe / board_wipe)
        {
            "object": "tag",
            "id": "tag-sweeper-003",
            "label": "sweeper",
            "slug": "sweeper",
            "aliases": ["board-wipe"],
            "parent_ids": [],
            "child_ids": [],
            "taggings": [{"oracle_id": OID_SWEEPER_CARD}],
        },
        # 4. Direct tag: land-ramp (maps to land_ramp, matches OID_CORPUS_CARD)
        {
            "object": "tag",
            "id": "tag-land-ramp-004",
            "label": "land ramp",
            "slug": "land-ramp",
            "aliases": [],
            "parent_ids": [],
            "child_ids": [],
            "taggings": [{"oracle_id": OID_CORPUS_CARD}],
        },
        # 5. Direct tag: counterspell (matches OID_SCRYFALL_CARD)
        {
            "object": "tag",
            "id": "tag-counter-005",
            "label": "counterspell",
            "slug": "counterspell",
            "aliases": [],
            "parent_ids": [],
            "child_ids": [],
            "taggings": [{"oracle_id": OID_SCRYFALL_CARD}],
        },
        # 6. Unrelated tag (should be ignored by canonical roles)
        {
            "object": "tag",
            "id": "tag-unrelated-006",
            "label": "hats in art",
            "slug": "hats-in-art",
            "aliases": ["ramp"],  # Test alias conflict: must NOT overwrite canonical ramp!
            "parent_ids": [],
            "child_ids": [],
            "taggings": [{"oracle_id": "unrelated-card-uuid"}],
        },
    ]
    return "\n".join(json.dumps(r) for r in records) + "\n"


def _create_mock_store(tmp_path: Path) -> StudioStore:
    """Create a StudioStore populated with collection, corpus, and scryfall cards."""
    store = StudioStore.open(tmp_path / "studio")
    with store.connection as db:
        source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title="test_sources.xlsx",
            sha256="testsha000000000000000000000000000000000000000000000000000000000",
        )
        # 1. Collection cards
        db.execute(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, mana_cost, "
            "mana_value, type_line, oracle_text, is_basic_land, source_id) "
            "VALUES ('card:01', ?, 'Sol Ring', '', '{1}', 1.0, 'Artifact', '', 0, ?)",
            (OID_SOL_RING, source_id),
        )
        db.execute(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, mana_cost, "
            "mana_value, type_line, oracle_text, is_basic_land, source_id) "
            "VALUES ('card:02', ?, 'Wrath of God', 'W', '{2}{W}{W}', 4.0, 'Sorcery', '', 0, ?)",
            (OID_SWEEPER_CARD, source_id),
        )
        # 2. Corpus-only card (not in card table!)
        db.execute(
            "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, tags, fingerprint, legality_audit, source_id) "
            "VALUES ('d1', 'chulane', 'http://deck', 'edhrec', 'casual', '[]', 'fp', 'PASS', ?)",
            (source_id,),
        )
        db.execute(
            "INSERT INTO corpus_deck_card VALUES ('d1', 'Cultivate', ?, 1, 'mainboard', 'OK')",
            (OID_CORPUS_CARD,),
        )
        # 3. Scryfall-only card
        db.execute(
            "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout, "
            "color_identity, commander_legality, keywords, produced_mana, source_id) "
            "VALUES (?, 'scry-01', 'Counterspell', 'Counterspell', 'normal', 'U', 'legal', '[]', '[]', ?)",
            (OID_SCRYFALL_CARD, source_id),
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


def test_alias_does_not_overwrite_slug(tmp_path: Path) -> None:
    """Verify an alias 'ramp' on a later tag does not hijack the primary 'ramp' tag."""
    bulk_file = tmp_path / "mock_bulk.jsonl"
    bulk_file.write_text(_sample_bulk_jsonl(), encoding="utf-8")

    graph = load_bulk_graph(bulk_file)
    ramp_id = graph.find_tag_id("ramp")
    assert ramp_id == "tag-ramp-001"
    assert graph.nodes_by_id[ramp_id].slug == "ramp"


def test_negative_vocabulary_proof(tmp_path: Path) -> None:
    """Genuinely audit that 'stax', 'token', and 'card-selection' are absent."""
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

    # Alias: board-wipe maps to canonical tag 'sweeper'
    sweeper_ids, rule_sweeper = graph.get_descendant_oracle_ids("board-wipe")
    assert OID_SWEEPER_CARD in sweeper_ids
    assert "sweeper" in rule_sweeper

    # Hierarchy: ramp includes child tag mana-rock
    ramp_ids, rule_ramp = graph.get_descendant_oracle_ids("ramp")
    assert OID_SOL_RING in ramp_ids
    assert "hierarchy (1 children)" in rule_ramp


def test_cross_source_oracle_id_resolution(tmp_path: Path) -> None:
    """Verify target oracle_id gathering covers collection, corpus, and scryfall."""
    store = _create_mock_store(tmp_path)
    try:
        targets = resolve_all_store_oracle_ids(store)
        assert OID_SOL_RING in targets
        assert OID_SWEEPER_CARD in targets
        assert OID_CORPUS_CARD in targets
        assert OID_SCRYFALL_CARD in targets
    finally:
        store.close()


def test_export_and_validate_studio_roles_file(tmp_path: Path) -> None:
    """Verify exported JSON satisfies the canonical studio-roles-2 schema."""
    bulk_file = tmp_path / "mock_bulk.jsonl"
    bulk_file.write_text(_sample_bulk_jsonl(), encoding="utf-8")

    graph = load_bulk_graph(bulk_file)
    out_file = tmp_path / "roles_snapshot.json"

    export_studio_roles_file(graph, out_file, scope_key="TEST_SCOPE")
    assert out_file.is_file()

    role_file = read_role_file(out_file)
    assert role_file.origin == ORIGIN_TAGGER
    assert role_file.scope_key == "TEST_SCOPE"
    assert set(role_file.roles.keys()) == set(ROLES.keys())
    assert OID_SOL_RING in role_file.roles["ramp"]
    assert OID_SWEEPER_CARD in role_file.roles["board_wipe"]


def test_import_tagger_bulk_into_store(tmp_path: Path) -> None:
    """Verify end-to-end import via roles.import_roles updates card_role and claims."""
    store = _create_mock_store(tmp_path)
    bulk_file = tmp_path / "mock_bulk.jsonl"
    bulk_file.write_text(_sample_bulk_jsonl(), encoding="utf-8")

    try:
        out_roles = tmp_path / "roles_snapshot.json"
        res = import_tagger_bulk(
            store,
            bulk_file,
            out_roles_path=out_roles,
            allow_scope_replace=True,
            scope_key="TEST_ALL",
        )

        assert res["vocabulary_audit"]["negative_audit_passed"] is True
        assert res["target_oracle_ids_count"] >= 4

        with store.connection as db:
            # Check claims exist for collection card
            claims_sol = db.execute(
                "SELECT role_origin, original_tag FROM card_role_claim "
                "WHERE oracle_id = ? AND role = 'ramp'",
                (OID_SOL_RING,),
            ).fetchall()
            assert len(claims_sol) >= 1
            assert claims_sol[0][0] == ORIGIN_TAGGER

            # Check claims exist for corpus-only card
            claims_corpus = db.execute(
                "SELECT role_origin FROM card_role_claim "
                "WHERE oracle_id = ? AND role = 'land_ramp'",
                (OID_CORPUS_CARD,),
            ).fetchall()
            assert len(claims_corpus) >= 1
            assert claims_corpus[0][0] == ORIGIN_TAGGER

            # Check claims exist for scryfall-only card
            claims_scry = db.execute(
                "SELECT role_origin FROM card_role_claim "
                "WHERE oracle_id = ? AND role = 'counterspell'",
                (OID_SCRYFALL_CARD,),
            ).fetchall()
            assert len(claims_scry) >= 1

            # Check card_role table was rebuilt
            roles_sol = db.execute(
                "SELECT role FROM card_role WHERE oracle_id = ?",
                (OID_SOL_RING,),
            ).fetchall()
            assigned_roles = [r[0] for r in roles_sol]
            assert "ramp" in assigned_roles
            assert "mana_rock" in assigned_roles

            # Re-importing with allow_scope_replace=True replaces cleanly
            res2 = import_tagger_bulk(
                store,
                bulk_file,
                out_roles_path=out_roles,
                allow_scope_replace=True,
                scope_key="TEST_ALL",
            )
            assert res2["target_oracle_ids_count"] >= 4
    finally:
        store.close()
