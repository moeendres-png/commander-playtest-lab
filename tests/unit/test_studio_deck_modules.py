"""Unit tests for user-defined Deck-Module (#1448): CRUD, 100-card compilation, collision checks, diff integration, and tier/strength invariance."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    StudioStore,
    create_revision,
    deck_diff,
    deck_evidence,
    deck_modules,
    strength,
    strength_view,
    tiers,
    universe,
)
from commander_lab.studio.decks import RevisionCard, list_rows
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _deck, _fill

COMMANDER = "Test Commander"
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def test_module_crud_and_seed_split(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)

        # Initially empty
        assert deck_modules.list_modules(store, "chulane") == []

        # Seed into Core (commanders + lands) and Package A (non-lands)
        seeded = deck_modules.seed_modules_from_cards(
            store,
            deck_id="chulane",
            cards=full_cards,
            core_name="Kern",
            package_name="Paket A",
        )
        assert len(seeded) == 2
        core_mod, pkg_mod = seeded[0], seeded[1]
        assert core_mod["role"] == "core"
        assert pkg_mod["role"] == "package"
        assert int(core_mod["commander_cards"]) == 1  # type: ignore[arg-type]
        assert int(core_mod["total_cards"]) + int(pkg_mod["total_cards"]) == 100  # type: ignore[arg-type]

        # Update module name
        updated = deck_modules.save_module(
            store,
            deck_id="chulane",
            module_id=str(pkg_mod["module_id"]),
            name="Paket A (Bounce)",
            role="package",
            cards=[
                RevisionCard(str(c["card_id"]), int(c["qty"]), str(c["zone"]))  # type: ignore[arg-type]
                for c in pkg_mod["cards"]  # type: ignore[union-attr]
            ],
            sort_order=2,
        )
        assert updated["name"] == "Paket A (Bounce)"
        assert updated["module_id"] == pkg_mod["module_id"]

        # Delete module
        assert deck_modules.delete_module(store, "chulane", str(pkg_mod["module_id"])) is True
        remaining = deck_modules.list_modules(store, "chulane")
        assert len(remaining) == 1
        assert remaining[0]["module_id"] == core_mod["module_id"]

        with pytest.raises(KeyError):
            deck_modules.delete_module(store, "chulane", "nonexistent")
    finally:
        store.close()


def test_compile_modules_to_100_cards_and_diff_variants(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)

        # Split: Commander + first 50 main cards in Core (51 cards), remaining 49 cards (20 fillers + 29 Forests) in Package A
        cmd_cards = [c for c in full_cards if c.zone == "commander"]
        main_cards = [c for c in full_cards if c.zone == "main"]
        core_cards = cmd_cards + main_cards[:50]
        pkg_a_cards = main_cards[50:]

        # Build Package B by replacing main_cards[50] (1 card) with Swarm Rat (card:project:0007, 1 card)
        pkg_b_cards = [RevisionCard("card:project:0007", 1, "main"), *pkg_a_cards[1:]]

        core = deck_modules.save_module(
            store, deck_id="chulane", name="Chulane Kern", role="core", cards=core_cards
        )
        pkg_a = deck_modules.save_module(
            store, deck_id="chulane", name="Combo Paket", role="package", cards=pkg_a_cards
        )
        pkg_b = deck_modules.save_module(
            store, deck_id="chulane", name="Ratten Paket", role="package", cards=pkg_b_cards
        )

        res_a = deck_modules.compile_modules(
            store,
            "chulane",
            [str(core["module_id"]), str(pkg_a["module_id"])],
            save=True,
        )
        assert res_a["valid"] is True
        assert res_a["saved"] is True
        assert res_a["total_cards"] == 100
        assert res_a["branch"] == "module:combo-paket"
        assert res_a["revision_id"] is not None
        assert res_a["issues"] == []
        export_dict = res_a["export"]
        assert isinstance(export_dict, dict)
        assert COMMANDER in str(export_dict["plain"])
        assert "Commander\n1 " + COMMANDER in str(export_dict["moxfield"])

        res_b = deck_modules.compile_modules(
            store,
            "chulane",
            [str(core["module_id"]), str(pkg_b["module_id"])],
            save=True,
        )
        assert res_b["valid"] is True
        assert res_b["saved"] is True
        assert res_b["branch"] == "module:ratten-paket"
        assert res_b["revision_id"] is not None
        assert res_b["revision_id"] != res_a["revision_id"]

        # Verify seamless integration with deck_diff
        cards_a = [
            RevisionCard(str(c["card_id"]), int(c["quantity"]), str(c["zone"]))  # type: ignore[arg-type]
            for c in res_a["cards"]  # type: ignore[union-attr]
        ]
        cards_b = [
            RevisionCard(str(c["card_id"]), int(c["quantity"]), str(c["zone"]))  # type: ignore[arg-type]
            for c in res_b["cards"]  # type: ignore[union-attr]
        ]
        diff = deck_diff.diff_impact(store, cards_a, cards_b)
        assert len(diff["added"]) == 1  # type: ignore[arg-type]
        assert len(diff["removed"]) == 1  # type: ignore[arg-type]
    finally:
        store.close()


def test_compile_detects_cross_module_collisions_and_validation_errors(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)

        cmd_cards = [c for c in full_cards if c.zone == "commander"]
        main_cards = [c for c in full_cards if c.zone == "main"]
        # Pick a non-basic card (`card:project:0108`) and put it in BOTH core and package
        dup_card = main_cards[8]
        assert dup_card.card_id == "card:project:0108"

        core_cards = cmd_cards + main_cards[:50]
        # Replace two 1-qty cards in package with dup_card + off-color Red Outsider (card:project:0003)
        pkg_cards = [dup_card, RevisionCard("card:project:0003", 1, "main"), *main_cards[52:]]
        assert sum(c.quantity for c in core_cards) + sum(c.quantity for c in pkg_cards) == 100

        core = deck_modules.save_module(
            store, deck_id="chulane", name="Kern", role="core", cards=core_cards
        )
        pkg = deck_modules.save_module(
            store, deck_id="chulane", name="Fehler-Paket", role="package", cards=pkg_cards
        )

        res = deck_modules.compile_modules(
            store,
            "chulane",
            [str(core["module_id"]), str(pkg["module_id"])],
            save=True,
        )
        assert res["valid"] is False
        assert res["saved"] is False
        assert res["revision_id"] is None
        codes = [str(i["code"]) for i in res["issues"]]  # type: ignore[index,union-attr]
        assert "duplicate_across_modules" in codes
        assert "color_identity" in codes

        dup_issue = next(
            i
            for i in res["issues"]
            if i["code"] == "duplicate_across_modules"  # type: ignore[index,union-attr]
        )
        assert "Kern" in str(dup_issue["message"])
        assert "Fehler-Paket" in str(dup_issue["message"])

        ci_issue = next(
            i
            for i in res["issues"]
            if i["code"] == "color_identity"  # type: ignore[index,union-attr]
        )
        assert "[Modul: Fehler-Paket]" in str(ci_issue["message"])

        # Missing package module error
        only_core = deck_modules.compile_modules(
            store, "chulane", [str(core["module_id"])], save=True
        )
        only_core_codes = [str(i["code"]) for i in only_core["issues"]]  # type: ignore[index,union-attr]
        assert "package_module_count" in only_core_codes
        assert only_core["saved"] is False
    finally:
        store.close()


def test_modules_never_affect_tiers_strength_or_evidence(tmp_path: Path) -> None:
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

        seeded = deck_modules.seed_modules_from_cards(
            store, deck_id="chulane", cards=full_cards, core_name="Kern", package_name="Paket A"
        )
        deck_modules.compile_modules(
            store,
            "chulane",
            [str(m["module_id"]) for m in seeded],
            save=True,
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


def test_module_http_routes_and_static_ui_wiring(tmp_path: Path) -> None:
    studio_dir = tmp_path / "studio"
    store = StudioStore.open(studio_dir)
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)
    finally:
        store.close()

    client = TestClient(create_app(studio_dir))
    headers = {"X-Studio": "1"}

    # Seed via API
    seed_resp = client.post(
        "/api/decks/chulane/modules/seed",
        headers=headers,
        json={
            "cards": [
                {"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone} for c in full_cards
            ],
            "core_name": "Kern",
            "package_name": "Paket A",
        },
    )
    assert seed_resp.status_code == 200
    mods = seed_resp.json()["modules"]
    assert len(mods) == 2

    # List via API
    list_resp = client.get("/api/decks/chulane/modules", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["schema"] == deck_modules.DECK_MODULES_SCHEMA
    assert len(list_resp.json()["modules"]) == 2

    # Compile & save via API
    comp_resp = client.post(
        "/api/decks/chulane/modules/compile",
        headers=headers,
        json={
            "module_ids": [m["module_id"] for m in mods],
            "owned_only": True,
            "save": True,
        },
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["valid"] is True
    assert comp_data["saved"] is True
    assert comp_data["total_cards"] == 100

    # UI wiring check
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert '["modules", "Module"]' in app_js
    assert "renderModules" in app_js
