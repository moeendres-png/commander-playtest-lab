"""Unit tests for Deck-Primer (#1449): CRUD, revision persistence, text export/re-import roundtrip, XSS-safe UI rendering, and tier/strength invariance."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    StudioStore,
    create_revision,
    deck_evidence,
    decks,
    strength,
    strength_view,
    tiers,
    universe,
)
from commander_lab.studio.decks import list_rows
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _deck, _fill

COMMANDER = "Test Commander"
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def test_primer_crud_and_persistence_across_revisions(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        rev1 = create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)

        # Default primer is empty
        initial = decks.get_deck_primer(store, "chulane")
        assert initial["deck_id"] == "chulane"
        assert initial["content"] == ""
        assert initial["updated_at"] is None

        # Set primer Markdown
        md = "# Spielplan\n\n- Früh: Mana-Elfen\n- Mitte: **Chulane** + `Shrieking Drake`\n"
        saved = decks.set_deck_primer(store, "chulane", md)
        assert saved["deck_id"] == "chulane"
        assert saved["content"] == md
        assert saved["updated_at"] is not None

        # Create a second revision with a card swap and verify primer remains intact on deck_id
        from commander_lab.studio.decks import RevisionCard

        cards_v2 = [*full_cards[:-2], RevisionCard("card:project:0007", 1, "main"), full_cards[-1]]
        rev2 = create_revision(
            store,
            deck_id="chulane",
            name="Chulane",
            cards=cards_v2,
            parent_revision_id=rev1,
            note="Zweite Revision",
        )
        assert rev2 != rev1
        after_rev2 = decks.get_deck_primer(store, "chulane")
        assert after_rev2["content"] == md
        assert after_rev2["updated_at"] == saved["updated_at"]

        # Overly long primer is rejected
        with pytest.raises(ValueError, match="zu lang"):
            decks.set_deck_primer(store, "chulane", "x" * (decks.MAX_PRIMER_CHARS + 1))

        # Unknown deck raises KeyError
        with pytest.raises(KeyError):
            decks.get_deck_primer(store, "nonexistent")
        with pytest.raises(KeyError):
            decks.set_deck_primer(store, "nonexistent", "text")
    finally:
        store.close()


def test_primer_export_and_reimport_roundtrip(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)
        rows = list_rows(store, full_cards)

        # Primer includes commas, brackets, parentheses, and multiple lines to test format detection resilience
        primer_md = (
            "# Chulane, Teller of Tales Primer\n"
            "Starthand: [Mana], (ELD) 326, Kombo-Linien, 2 Länder.\n\n"
            "- **Linie A**: Shrieking Drake + Chulane\n"
            "- **Mulligan**: Nie unter 2 Ländern halten"
        )
        without_primer = decks.export_text(rows, "moxfield")
        with_primer = decks.export_text(rows, "moxfield", primer=primer_md)

        assert not without_primer.startswith("//")
        assert with_primer.startswith("// Primer:\n// # Chulane, Teller of Tales Primer\n")
        assert without_primer in with_primer

        # Re-importing the exported text with primer comments yields the exact same card entries
        parsed_without = decks.parse_decklist_text(store, [COMMANDER], without_primer)
        parsed_with = decks.parse_decklist_text(store, [COMMANDER], with_primer)
        assert parsed_with["detected_format"] == parsed_without["detected_format"]
        assert parsed_with["cards"] == parsed_without["cards"]
        assert parsed_with["unrecognized_lines"] == []
    finally:
        store.close()


def test_primer_never_affects_tiers_strength_or_evidence(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)

        inc_before = universe.inclusion(store, commander_names=[COMMANDER])
        tiers_before = tiers.tiers_for_universe(
            inc_before, universe_snapshot="snap-1", params=tiers.TierParams()
        )
        strength_before = strength_view.compute(store, COMMANDER, strength.StrengthSettings())
        evidence_before = deck_evidence.deck_evidence(store, list_rows(store, full_cards))

        decks.set_deck_primer(
            store,
            "chulane",
            "# Turnier-Primer\n\nS-Tier Notizen, Matchup-Pläne und Mulligan-Regeln.",
        )

        inc_after = universe.inclusion(store, commander_names=[COMMANDER])
        tiers_after = tiers.tiers_for_universe(
            inc_after, universe_snapshot="snap-1", params=tiers.TierParams()
        )
        assert tiers_after == tiers_before
        assert (
            strength_view.compute(store, COMMANDER, strength.StrengthSettings()) == strength_before
        )
        assert deck_evidence.deck_evidence(store, list_rows(store, full_cards)) == evidence_before
    finally:
        store.close()


def test_primer_http_routes_and_static_ui_wiring(tmp_path: Path) -> None:
    studio_dir = tmp_path / "studio"
    store = StudioStore.open(studio_dir)
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        rev_id = create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)
    finally:
        store.close()

    client = TestClient(create_app(studio_dir))
    headers = {"X-Studio": "1"}

    get_resp = client.get("/api/decks/chulane/primer", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["content"] == ""

    md = (
        "## Matchup-Notizen\n\n- Gegen Stax: **Geduld**\n- Gegen Turbo: `Counterspell` offen halten"
    )
    put_resp = client.put(
        "/api/decks/chulane/primer",
        headers=headers,
        json={"content": md},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["content"] == md

    exp_plain = client.get(f"/api/revisions/{rev_id}/export?format=moxfield", headers=headers)
    assert exp_plain.status_code == 200
    assert not exp_plain.text.startswith("// Primer:")

    exp_with = client.get(
        f"/api/revisions/{rev_id}/export?format=moxfield&include_primer=true",
        headers=headers,
    )
    assert exp_with.status_code == 200
    assert exp_with.text.startswith("// Primer:\n// ## Matchup-Notizen\n")

    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert '["primer", "Primer"]' in app_js
    assert "renderPrimer" in app_js
    assert "renderMarkdownSafe" in app_js

    export_js = (STATIC_DIR / "exportformats.js").read_text(encoding="utf-8")
    assert "exportFormatPrimerLines" in export_js
    assert "export-include-primer" in export_js
