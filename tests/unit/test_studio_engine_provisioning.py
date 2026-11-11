"""Unit tests for Studio engine provisioning, prerequisites checks, and card capability pre-flight (Issue #1172).

Tests:
1. engine_state detection (missing jar, installed jar, pin verification, sha256 checksum).
2. cards_unsupported_by_engine & cards_unknown_to_pilots fail-closed detection.
3. collection_cards_unknown_to_pilots and collection_cards_unsupported_by_engine.
4. start_game pre-flight checks fail-closed.
5. scripts/provision_engine_bridge.py staging and verification logic.
6. /api/engine/missing-cards web endpoint.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from scripts.provision_engine_bridge import provision_bridge, verify_installed_engine
from starlette.testclient import TestClient

from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)
from commander_lab.studio import launch
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.launch import (
    ENGINE_JAR,
    cards_unknown_to_pilots,
    cards_unsupported_by_engine,
    collection_cards_unknown_to_pilots,
    collection_cards_unsupported_by_engine,
    engine_state,
)
from commander_lab.studio.store import DataClass, StudioStore
from commander_lab.studio.web import create_app


def test_engine_state_missing_and_present(tmp_path: Path) -> None:
    # Initially no engine JAR in tmp_path
    state = engine_state(tmp_path)
    assert not state["ready"]
    assert "Die Engine-Datei fehlt" in str(state["reason"])
    assert state["jar_path"] is None
    assert state["jar_sha256"] is None
    pin = canonical_xmage_engine_pin()
    assert state["pin"] == pin

    # Create dummy engine JAR
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir(parents=True)
    jar_file = tmp_path / ENGINE_JAR
    jar_file.write_bytes(b"dummy-engine-jar-bytes-12345")

    # With JAR present but no java mock or real java
    state_with_jar = engine_state(tmp_path)
    assert state_with_jar["jar_path"] == str(jar_file)
    assert state_with_jar["jar_sha256"] is not None
    assert len(str(state_with_jar["jar_sha256"])) == 64

    # Add ENGINE_PIN.txt with correct pin
    pin_file = engine_dir / "ENGINE_PIN.txt"
    pin_file.write_text(pin + "\n", encoding="utf-8")
    state_pinned = engine_state(tmp_path)
    assert state_pinned["recorded_pin"] == pin
    assert state_pinned["pin_matches"] is True
    assert state_pinned["warning"] is None

    # Mismatched pin file
    pin_file.write_text("0000000000111111111122222222223333333333\n", encoding="utf-8")
    state_mismatch = engine_state(tmp_path)
    assert state_mismatch["pin_matches"] is False
    assert state_mismatch["warning"] is not None
    assert "erwartet wird jedoch" in str(state_mismatch["warning"])


def test_cards_unsupported_by_engine_and_pilots() -> None:
    # Deck with known card (Sol Ring) and completely synthetic card
    snapshot: dict[str, object] = {
        "deck_id": "test-deck",
        "cards": [
            {"oracle_name": "Sol Ring", "name": "Sol Ring", "quantity": 1},
            {
                "oracle_name": "Completely Nonexistent Card 999",
                "name": "Completely Nonexistent Card 999",
                "quantity": 1,
            },
        ],
    }

    unknown_pilots = cards_unknown_to_pilots(snapshot)
    assert "Completely Nonexistent Card 999" in unknown_pilots
    assert "Sol Ring" not in unknown_pilots

    unsupported_engine = cards_unsupported_by_engine(snapshot)
    assert "Completely Nonexistent Card 999" in unsupported_engine
    assert "Sol Ring" not in unsupported_engine


def test_collection_gaps_reporting(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path)
    try:
        # Register a source
        src_id = store.register_source(
            data_class=DataClass.ORIGINAL_SOURCE,
            title="test",
            sha256="0" * 64,
        )
        # Insert known and unknown cards
        store.connection.execute(
            "INSERT INTO card (card_id, oracle_name, color_identity, source_id) "
            "VALUES (?, ?, ?, ?)",
            ("card:1", "Sol Ring", "C", src_id),
        )
        store.connection.execute(
            "INSERT INTO card (card_id, oracle_name, color_identity, source_id) "
            "VALUES (?, ?, ?, ?)",
            ("card:2", "Fabricated Studio Card 42", "W", src_id),
        )

        missing_pilot = collection_cards_unknown_to_pilots(store)
        assert "Fabricated Studio Card 42" in missing_pilot
        assert "Sol Ring" not in missing_pilot

        missing_engine = collection_cards_unsupported_by_engine(store)
        assert "Fabricated Studio Card 42" in missing_engine
        assert "Sol Ring" not in missing_engine
    finally:
        store.close()


def test_start_game_fails_closed_on_unsupported_cards(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path)
    try:
        src_id = store.register_source(
            data_class=DataClass.ORIGINAL_SOURCE,
            title="test",
            sha256="0" * 64,
        )
        store.connection.execute(
            "INSERT INTO card (card_id, oracle_name, color_identity, source_id) "
            "VALUES (?, ?, ?, ?)",
            ("c:1", "Fabricated Card Alpha", "G", src_id),
        )
        cards = [RevisionCard("c:1", 1, "commander")]
        rev_id = create_revision(store, deck_id="deck-alpha", name="Alpha", cards=cards)

        with (
            patch.object(launch, "engine_command", return_value=("java", "-jar", "mock.jar")),
            pytest.raises(
                ValueError, match="Regeln-Engine XMage unterstützt diese Karten noch nicht"
            ),
        ):
            launch.start_game(
                store,
                tmp_path,
                revision_id=rev_id,
                opponent_ids=["kaervek/current"],
                seed=42,
            )
    finally:
        store.close()


def test_provision_bridge_script(tmp_path: Path) -> None:
    source_jar = tmp_path / "mock-source-bridge.jar"
    source_jar.write_bytes(b"PK\x03\x04test-engine-bridge-binary-contents")

    target_studio = tmp_path / "studio_data"
    result = provision_bridge(source_jar, target_studio)

    assert result["status"] == "provisioned"
    assert (target_studio / ENGINE_JAR).is_file()
    assert (target_studio / "engine" / "ENGINE_PIN.txt").is_file()
    assert (target_studio / "engine" / "xmage-engine-bridge.jar.sha256").is_file()

    verify_report = verify_installed_engine(target_studio)
    assert verify_report["data_dir"] == str(target_studio.resolve())
    assert isinstance(verify_report["engine_state"], dict)


def test_api_missing_cards_endpoint(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path)
    try:
        src_id = store.register_source(
            data_class=DataClass.ORIGINAL_SOURCE,
            title="test",
            sha256="0" * 64,
        )
        store.connection.execute(
            "INSERT INTO card (card_id, oracle_name, color_identity, source_id) "
            "VALUES (?, ?, ?, ?)",
            ("card:sol", "Sol Ring", "C", src_id),
        )
    finally:
        store.close()

    app = create_app(tmp_path)
    client = TestClient(app)

    res = client.get("/api/engine/missing-cards")
    assert res.status_code == 200
    data = res.json()
    assert "collection_unknown_to_pilots" in data
    assert "collection_unsupported_by_engine" in data
    assert "Sol Ring" not in data["collection_unknown_to_pilots"]
