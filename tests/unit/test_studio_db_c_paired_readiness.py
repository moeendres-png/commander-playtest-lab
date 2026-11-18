"""Self-contained unit tests for PR DB-C (#1404 op. 6 paired series & C-3 readiness audit)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from commander_lab.agents.card_knowledge import CardCatalogError
from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)
from commander_lab.studio import (
    StudioStore,
    builder,
    launch,
    paired_comparison,
    paired_series,
    strength_view,
)
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.paired_series import PairedSeriesManager
from commander_lab.studio.store import now_utc
from commander_lab.studio.strength import StrengthSettings
from commander_lab.studio.web import create_app

COMMANDER = "Chulane, Teller of Tales"
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def _ensure_source(store: StudioStore, source_id: str, data_class: str, title: str) -> None:
    store.connection.execute(
        "INSERT OR IGNORE INTO source (source_id, data_class, title, sha256, imported_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (source_id, data_class, title, "0" * 64, now_utc()),
    )


def _add_card(
    store: StudioStore,
    card_id: str,
    name: str,
    *,
    identity: str = "G,U,W",
    mana_cost: str = "{1}{G}",
    mana_value: float = 2.0,
    type_line: str = "Creature — Elf Druid",
    oracle_text: str = "Tap: Add {G}.",
    legal: int = 1,
    owned: int = 1,
    available: int = 1,
    roles: tuple[str, ...] = (),
    is_basic: int = 0,
    oracle_id: str | None = None,
) -> None:
    oid = oracle_id or f"oid-{card_id}"
    src_id = "src-card-fixture"
    with store.connection:
        _ensure_source(store, src_id, "ORIGINAL_SOURCE", "Test Card Fixture")
        store.connection.execute(
            "INSERT OR REPLACE INTO card "
            "(card_id, oracle_id, oracle_name, color_identity, mana_cost, mana_value, "
            "type_line, oracle_text, is_basic_land, commander_legal, source_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                card_id,
                oid,
                name,
                identity,
                mana_cost,
                mana_value,
                type_line,
                oracle_text,
                is_basic,
                legal,
                src_id,
            ),
        )
        store.connection.execute(
            "INSERT OR REPLACE INTO inventory "
            "(card_id, observed, owned_lower_bound, reserved, available_lower_bound, "
            "quantity_exact, source_id) "
            "VALUES (?, 1, ?, 0, ?, ?, ?)",
            (card_id, owned, available, owned, src_id),
        )
        for role in roles:
            store.connection.execute(
                "INSERT OR IGNORE INTO card_role (oracle_id, role, source_id) VALUES (?, ?, ?)",
                (oid, role, src_id),
            )
        store.connection.execute(
            "INSERT OR REPLACE INTO scryfall_card "
            "(oracle_id, scryfall_id, name, front_name, layout, mana_cost, mana_value, "
            "type_line, oracle_text, color_identity, commander_legality, keywords, "
            "produced_mana, source_id) "
            "VALUES (?, ?, ?, ?, 'normal', ?, ?, ?, ?, ?, ?, '[]', '[]', ?)",
            (
                oid,
                f"scry-{card_id}",
                name,
                name,
                mana_cost,
                mana_value,
                type_line,
                oracle_text,
                identity,
                "legal" if legal else "not_legal",
                src_id,
            ),
        )


def _seed_signal(
    store: StudioStore,
    card_name: str,
    *,
    edhrec_pct: float = 0.50,
    cohort_pct: float = 0.60,
) -> None:
    with store.connection:
        _ensure_source(store, "src-sig-edhrec", "PUBLIC_AGGREGATED", "EDHREC Fixture")
        _ensure_source(store, "src-sig-corpus", "PUBLIC_AGGREGATED", "Corpus Fixture")
        store.connection.execute(
            "INSERT OR REPLACE INTO card_signal "
            "(commander_name, card_name, signal, value, numerator, denominator, source_id) "
            "VALUES ('', ?, 'edhrec_global_inclusion', ?, ?, 100, 'src-sig-edhrec')",
            (card_name, edhrec_pct, round(edhrec_pct * 100)),
        )
        store.connection.execute(
            "INSERT OR REPLACE INTO card_signal "
            "(commander_name, card_name, signal, value, numerator, denominator, source_id) "
            "VALUES (?, ?, 'edhrec_commander_inclusion', ?, ?, 100, 'src-sig-corpus')",
            (COMMANDER, card_name, cohort_pct, round(cohort_pct * 100)),
        )


def _make_store(tmp_path: Path) -> tuple[StudioStore, Path]:
    folder = tmp_path / "studio_data"
    store = StudioStore.open(folder)
    _add_card(
        store,
        "cid-chulane",
        COMMANDER,
        identity="G,U,W",
        mana_cost="{2}{G}{W}{U}",
        mana_value=5.0,
        type_line="Legendary Creature — Human Druid",
        roles=("card_draw",),
    )
    _add_card(
        store,
        "cid-forest",
        "Forest",
        identity="G",
        mana_cost="",
        mana_value=0.0,
        type_line="Basic Land — Forest",
        is_basic=1,
        owned=120,
        available=120,
    )
    _add_card(
        store,
        "cid-sol-ring",
        "Sol Ring",
        identity="",
        mana_cost="{1}",
        mana_value=1.0,
        type_line="Artifact",
        roles=("ramp", "mana_rock"),
        owned=2,
        available=2,
    )
    _add_card(
        store,
        "cid-llanowar",
        "Llanowar Elves",
        identity="G",
        mana_cost="{G}",
        mana_value=1.0,
        type_line="Creature — Elf Druid",
        roles=("ramp", "mana_dork"),
        owned=2,
        available=2,
    )
    _add_card(
        store,
        "cid-signet",
        "Arcane Signet",
        identity="",
        mana_cost="{2}",
        mana_value=2.0,
        type_line="Artifact",
        roles=("ramp", "mana_rock"),
        owned=2,
        available=2,
    )
    return store, folder


def _wait_job(manager: PairedSeriesManager, folder: Path, series_id: str) -> dict[str, object]:
    for _ in range(100):
        data = manager.get_series(folder, series_id)
        if data is not None and data.get("status") in {"completed", "failed", "cancelled"}:
            return data
        time.sleep(0.02)
    raise AssertionError(f"paired job {series_id} did not finish in time")


def _mock_exposure(
    game_id: str,
    *,
    seed: int,
    seat: int,
    tested_deck_id: str,
    won: bool,
) -> dict[str, object]:
    seats = []
    for s in range(4):
        did = tested_deck_id if s == seat else f"opp-{s}"
        w_credit = (
            1.0 if (s == seat and won) or (s != seat and not won and s == (seat + 1) % 4) else 0.0
        )
        seats.append({"seat": s, "deck_id": did, "win_credit": w_credit})
    return {
        "game_id": game_id,
        "seed": seed,
        "engine_commit": canonical_xmage_engine_pin(),
        "bridge_jar_sha256": None,
        "bridge_qualification_state": "UNKNOWN",
        "covered_by_sealed_epoch": False,
        "pilot": "GenericCommanderPilot 1.0.0",
        "decision_policy": "heuristic",
        "seats": seats,
    }


def test_estimate_series_duration_matches_540_games_per_hour() -> None:
    est = paired_series.estimate_series_duration(20)
    assert est["budget_pairs"] == 20
    assert est["max_games"] == 40
    assert est["estimated_games_per_hour"] == 540
    assert est["estimated_seconds"] == round(40 * 3600.0 / 540.0)
    assert est["estimated_minutes"] == round(est["estimated_seconds"] / 60.0, 1)
    # 540/h is the batch-series measurement (#1251), not one of paired series
    assert est["throughput_measured_for_paired_series"] is False
    assert "ungemessen" in str(est["throughput_source"])
    assert "ungemessen" in str(est["basis"])


def test_series_plan_names_the_detectable_difference_and_its_assumptions() -> None:
    from commander_lab.engine.rules.full_game_comparison import (
        PLANNED_PAIR_SD,
        difference_quantiles,
    )

    plan = paired_series.estimate_series_duration(40)["planning"]
    assert isinstance(plan, dict)
    # the evaluation's arithmetic: t at seeds - 1 = 9 df, (t95 + t80) * 0.63 / sqrt(40) = 31.3 pp,
    # with the design effect 1.75 of four seats per seed 41.5 pp (normal quantiles: 27.9 / 36.9)
    t95, t80 = difference_quantiles(9)
    expected = (t95 + t80) * PLANNED_PAIR_SD / 40**0.5 * 100
    assert plan["detectable_pp_low"] == round(expected, 1) == 31.3
    assert plan["detectable_pp_high"] == round(expected * 1.75**0.5, 1) == 41.5
    # 5 pp needs about 1254 pairs (independent seeds) up to 2195 (design effect 1.75)
    assert (plan["pairs_needed_low"], plan["pairs_needed_high"]) == (1254, 2195)
    assumptions = plan["assumptions"]
    assert assumptions["confidence"] == 0.95 and assumptions["power"] == 0.80
    assert assumptions["degrees_of_freedom"] == 9
    assert assumptions["pair_sd_independent_exact"] == 0.6124
    assert "unmeasured" in assumptions["pair_sd_basis"]
    one_seat = paired_series.estimate_series_duration(40, seats_per_seed=1)["planning"]
    assert one_seat["detectable_pp_high"] == one_seat["detectable_pp_low"] == 28.6
    assert one_seat["assumptions"]["degrees_of_freedom"] == 39
    # cross-check with the methods paper: about 5.5 pp at 1000 pairs
    assert paired_series.planned_detectable_difference_pp(1000, 1)["detectable_pp_low"] == 5.6
    # a job plans with its own seats per seed, not a fixed four
    assert (
        paired_series.estimate_series_duration(40, seats_per_seed=3)["planning"]["assumptions"][
            "seats_per_seed"
        ]
        == 3
    )


def test_validate_series_id_rejects_path_traversal() -> None:
    assert paired_series.validate_series_id("paired-123-1-abcd") == "paired-123-1-abcd"
    for bad in ["../etc/passwd", "foo/bar", "a b", ".hidden", ""]:
        with pytest.raises(ValueError, match="invalid series_id"):
            paired_series.validate_series_id(bad)


def test_paired_series_decided_early_stop_and_tier_invariance(tmp_path: Path) -> None:
    store, folder = _make_store(tmp_path)
    try:
        for name in ("Sol Ring", "Llanowar Elves", "Arcane Signet"):
            _seed_signal(store, name, edhrec_pct=0.5, cohort_pct=0.6)
        tier_before = strength_view.compute(store, COMMANDER, StrengthSettings())

        rev_base = create_revision(
            store,
            deck_id="chulane-test",
            name="Chulane Test",
            branch="main",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-sol-ring", 1, "main"),
                RevisionCard("cid-llanowar", 1, "main"),
                RevisionCard("cid-forest", 97, "main"),
            ],
        )
        rev_var = create_revision(
            store,
            deck_id="chulane-test",
            name="Chulane Test",
            branch="variant",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-sol-ring", 1, "main"),
                RevisionCard("cid-signet", 1, "main"),
                RevisionCard("cid-forest", 97, "main"),
            ],
        )

        # Deterministic mock where variant always wins and base always loses -> decides early
        def _play(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            did = "chulane-test--base" if arm == "base" else "chulane-test--variant"
            return {
                "exposure": _mock_exposure(  # type: ignore[typeddict-item]
                    f"{arm}-{seed}-{seat}",
                    seed=seed,
                    seat=seat,
                    tested_deck_id=did,
                    won=(arm == "variant"),
                ),
                "failure_class": None,
            }

        mgr = PairedSeriesManager()
        job = mgr.start_series(
            store,
            folder,
            base_revision_id=rev_base,
            variant_revision_id=rev_var,
            pod="precon",
            budget_pairs=40,
            look_every_pairs=8,
            base_seed=2000,
            rotate_seats=True,
            play_override=_play,
        )
        # Same deck_id on both revisions must be automatically disambiguated
        assert job.base_deck.deck_id != job.variant_deck.deck_id

        finished = _wait_job(mgr, folder, job.series_id)
        assert finished["status"] == "completed"
        res = finished["result"]
        assert isinstance(res, dict)
        assert res["status"] == "DECIDED"
        assert res["answer"] == "ABOVE"
        assert res["pairs_completed"] < 40
        assert res["difference_pp"] == pytest.approx(100.0)
        assert res["data_class"] == "SIMULATED_RESULT"

        disk_file = folder / "games" / f"{job.series_id}.paired.json"
        assert disk_file.is_file()
        assert len(mgr.list_series(folder)) == 1

        # Simulation results NEVER touch strength_view weights or tiers (weight stays 0)
        tier_after = strength_view.compute(store, COMMANDER, StrengthSettings())
        assert tier_after["cards"] == tier_before["cards"]
    finally:
        store.close()


def test_paired_series_not_decided_and_preflight_same_revision_rejected(tmp_path: Path) -> None:
    store, folder = _make_store(tmp_path)
    try:
        rev_a = create_revision(
            store,
            deck_id="deck-a",
            name="Deck A",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-sol-ring", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )
        rev_b = create_revision(
            store,
            deck_id="deck-b",
            name="Deck B",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-signet", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )

        def _noop_play(_arm: str, _seed: int, _seat: int) -> paired_comparison.PlayedGame:
            return {"exposure": None, "failure_class": "noop"}

        mgr = PairedSeriesManager()
        with pytest.raises(ValueError, match="verschiedene"):
            mgr.start_series(
                store,
                folder,
                base_revision_id=rev_a,
                variant_revision_id=rev_a,
                play_override=_noop_play,
            )

        # Tied outcomes -> exhausts budget and reports NOT_DECIDED
        def _tied(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            did = "deck-a" if arm == "base" else "deck-b"
            return {
                "exposure": _mock_exposure(  # type: ignore[typeddict-item]
                    f"{arm}-{seed}-{seat}",
                    seed=seed,
                    seat=seat,
                    tested_deck_id=did,
                    won=False,
                ),
                "failure_class": None,
            }

        job = mgr.start_series(
            store,
            folder,
            base_revision_id=rev_a,
            variant_revision_id=rev_b,
            budget_pairs=8,
            look_every_pairs=4,
            rotate_seats=False,
            play_override=_tied,
        )
        finished = _wait_job(mgr, folder, job.series_id)
        assert finished["status"] == "completed"
        assert finished["result"]["status"] == "NOT_DECIDED"  # type: ignore[index]
        assert finished["result"]["pairs_completed"] == 8  # type: ignore[index]
    finally:
        store.close()


def test_paired_series_plays_the_variant_in_the_baseline_library_slots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A one-card swap reaches the engine in the baseline's slots, not re-sorted.

    Studio snapshots list their cards by name, so a swap that crosses the alphabet shifts
    every card in between to another library slot and the paired games of one seed share
    no shuffle. The engine reads the deck files, so the files themselves must hold the
    aligned order.
    """
    from collections import Counter

    from commander_lab.engine.rules.project import load_rules_deck_snapshot

    # synthetic card names: the engine/pilot card preflight is not under test here
    monkeypatch.setattr(builder, "sim_readiness_available", lambda: False)
    store, folder = _make_store(tmp_path)
    try:
        named = [f"Middle Card {letter}" for letter in "BCDEFGHIJK"]
        for index, name in enumerate([*named, "Zephyr Card", "Aardvark Card"]):
            _add_card(store, f"cid-slot-{index}", name)
        shared = [RevisionCard(f"cid-slot-{index}", 1, "main") for index in range(len(named))]
        commander = RevisionCard("cid-chulane", 1, "commander")
        forests = RevisionCard("cid-forest", 88, "main")
        rev_base = create_revision(
            store,
            deck_id="slot-base",
            name="Slot Base",
            cards=[commander, *shared, RevisionCard("cid-slot-10", 1, "main"), forests],
        )
        rev_var = create_revision(
            store,
            deck_id="slot-variant",
            name="Slot Variant",
            cards=[commander, *shared, RevisionCard("cid-slot-11", 1, "main"), forests],
        )

        def _noop(_arm: str, _seed: int, _seat: int) -> paired_comparison.PlayedGame:
            return {"exposure": None, "failure_class": "noop"}

        mgr = PairedSeriesManager()
        job = mgr.start_series(
            store,
            folder,
            base_revision_id=rev_base,
            variant_revision_id=rev_var,
            budget_pairs=4,
            look_every_pairs=4,
            rotate_seats=False,
            play_override=_noop,
        )
        finished = _wait_job(mgr, folder, job.series_id)
        base_file = job.paths_by_deck_id[job.base_deck.deck_id]
        variant_file = job.paths_by_deck_id[job.variant_deck.deck_id]
        base_main = load_rules_deck_snapshot(base_file).mainboard
        variant_main = load_rules_deck_snapshot(variant_file).mainboard
        differing = [
            (index, b, v)
            for index, (b, v) in enumerate(zip(base_main, variant_main, strict=True))
            if b != v
        ]
        assert differing == [(base_main.index("Zephyr Card"), "Zephyr Card", "Aardvark Card")]
        # the variant still plays exactly its own cards
        revision_cards = Counter([*named, "Aardvark Card", *(["Forest"] * 88)])
        assert Counter(variant_main) == revision_cards
        assert job.variant_deck.mainboard == variant_main

        alignment = finished["slot_alignment"]
        assert isinstance(alignment, dict)
        assert alignment["swapped_slots"] == 1
        assert alignment["appended"] == 0 and alignment["dropped"] == 0
        assert (
            alignment["played_mainboard_sha256"]
            == hashlib.sha256("\n".join(variant_main).encode()).hexdigest()
        )
        result = finished["result"]
        assert isinstance(result, dict)
        assert result["execution"]["slot_alignment"] == alignment
        # consecutive seeds on purpose: the starting seat is seed % players
        assert finished["seed_plan"] == {
            "purpose": "unspecified",
            "first_seed": 1000,
            "last_seed": 1003,
            "seeds_planned": 4,
            "seed_rule": "consecutive",
            "player_count": 4,
            "starting_seat_rule": "seed % player_count",
        }
        assert result["execution"]["seed_plan"] == finished["seed_plan"]
        with pytest.raises(ValueError, match="purpose"):
            mgr.start_series(
                store,
                folder,
                base_revision_id=rev_base,
                variant_revision_id=rev_var,
                play_override=_noop,
                purpose="whatever",
            )
    finally:
        store.close()


def test_opponent_resolution_all_pods_and_fail_closed() -> None:
    for pod_name, expected_ids in launch.POD_PRESETS.items():
        paths = paired_series._resolve_opponent_paths(pod_name, None)
        assert len(paths) == len(expected_ids) == 3
        assert all(p.is_file() for p in paths)

    with pytest.raises(ValueError, match="Unbekannter Gegnertisch"):
        paired_series._resolve_opponent_paths("nonexistent-pod", None)

    with pytest.raises(ValueError, match="Unbekanntes Gegner-Deck"):
        paired_series._resolve_opponent_paths("precon", ["missing/deck-id"])

    with pytest.raises(ValueError, match="doppelt"):
        paired_series._resolve_opponent_paths("precon", ["kaervek/current", "kaervek/current"])

    with pytest.raises(ValueError, match="zwischen 1 und 5"):
        paired_series._resolve_opponent_paths("precon", [])


def test_simulator_readiness_audit_fail_closed_gaps_and_real_chulane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _folder = _make_store(tmp_path)
    try:
        for name in ("Sol Ring", "Llanowar Elves", "Arcane Signet"):
            _seed_signal(store, name, edhrec_pct=0.8, cohort_pct=0.8)
        _add_card(store, "cid-mystery", "Mystery Card Not In Engine", roles=("removal",))
        _seed_signal(store, "Mystery Card Not In Engine", edhrec_pct=0.95, cohort_pct=0.95)

        # DFC card in deck with separate front_name so engine_name != oracle_name
        with store.connection:
            _ensure_source(store, "src-card-fixture", "ORIGINAL_SOURCE", "Test Card Fixture")
            oid_dfc = "oid-cid-dfc"
            store.connection.execute(
                "INSERT OR REPLACE INTO card "
                "(card_id, oracle_id, oracle_name, color_identity, mana_cost, mana_value, "
                "type_line, oracle_text, is_basic_land, commander_legal, source_id) "
                "VALUES ('cid-dfc', ?, 'Bala Ged Recovery // Bala Ged Sanctuary', 'G', '{2}{G}', 3.0, "
                "'Sorcery // Land', '', 0, 1, 'src-card-fixture')",
                (oid_dfc,),
            )
            store.connection.execute(
                "INSERT OR REPLACE INTO inventory "
                "(card_id, observed, owned_lower_bound, reserved, available_lower_bound, quantity_exact, source_id) "
                "VALUES ('cid-dfc', 1, 1, 0, 1, 1, 'src-card-fixture')"
            )
            store.connection.execute(
                "INSERT OR REPLACE INTO scryfall_card "
                "(oracle_id, scryfall_id, name, front_name, layout, mana_cost, mana_value, "
                "type_line, oracle_text, color_identity, commander_legality, keywords, produced_mana, source_id) "
                "VALUES (?, 'scry-cid-dfc', 'Bala Ged Recovery // Bala Ged Sanctuary', "
                "'Bala Ged Recovery', 'modal_dfc', '{2}{G}', 3.0, 'Sorcery // Land', '', 'G', 'legal', '[]', '[]', 'src-card-fixture')",
                (oid_dfc,),
            )
        _seed_signal(
            store,
            "Bala Ged Recovery // Bala Ged Sanctuary",
            edhrec_pct=0.9,
            cohort_pct=0.9,
        )

        deck_cards = [
            RevisionCard("cid-chulane", 1, "commander"),
            RevisionCard("cid-sol-ring", 1, "main"),
            RevisionCard("cid-dfc", 1, "main"),
            RevisionCard("cid-forest", 97, "main"),
        ]

        # 1. Fail closed when catalogs unavailable
        unk = paired_series.simulator_readiness_audit(
            store,
            [COMMANDER],
            cards=deck_cards,
            available_check=lambda: False,
        )
        assert unk["available"] is False
        assert unk["status"] == "UNKNOWN"

        # 1b. Fail closed when CardCatalogError is raised during pilot catalog probe/lookup
        monkeypatch.setattr(
            paired_series,
            "card_facts",
            lambda _name: (_ for _ in ()).throw(CardCatalogError("corrupt pilot catalog")),
        )
        unk_corrupt = paired_series.simulator_readiness_audit(
            store,
            [COMMANDER],
            cards=deck_cards,
            available_check=lambda: True,
        )
        assert unk_corrupt["available"] is False
        assert unk_corrupt["status"] == "UNKNOWN"
        monkeypatch.undo()

        # 2. Reports missing engine status & missing pilot knowledge; excludes DFC in deck
        looked_up_names: list[str] = []

        def _status_lookup(name: str) -> str:
            looked_up_names.append(name)
            return "MISSING" if "Mystery" in name else "OK"

        audit = paired_series.simulator_readiness_audit(
            store,
            [COMMANDER],
            cards=deck_cards,
            tiers=("S", "A"),
            available_check=lambda: True,
            status_lookup=_status_lookup,
            pilot_known=lambda name: "Mystery" not in name,
        )
        assert audit["available"] is True
        assert audit["status"] == "GAPS_FOUND"
        assert audit["deck"]["total"] == 4  # type: ignore[index]
        assert audit["deck"]["ready"] == 4  # type: ignore[index]
        assert "Bala Ged Recovery" in looked_up_names
        free = audit["free_top_candidates"]
        assert isinstance(free, dict)
        cand_names = {item["name"] for item in free["items"]}
        assert "Bala Ged Recovery // Bala Ged Sanctuary" not in cand_names
        issue_names = [i["name"] for i in free["issues"]]
        assert "Mystery Card Not In Engine" in issue_names

        # 3. Clean audit passes when all deck + Tier-S/A candidates are OK
        clean = paired_series.simulator_readiness_audit(
            store,
            [COMMANDER],
            cards=deck_cards,
            tiers=("S", "A"),
            available_check=lambda: True,
            status_lookup=lambda _: "OK",
            pilot_known=lambda _: True,
        )
        assert clean["status"] == "OK"

        # 4. cards=None falls back cleanly to repo baseline when present
        fallback = paired_series.simulator_readiness_audit(
            store,
            [COMMANDER],
            cards=None,
            tiers=("S", "A"),
            available_check=lambda: True,
            status_lookup=lambda _: "OK",
            pilot_known=lambda _: True,
        )
        assert fallback["available"] is True
        assert fallback["deck"]["total"] >= 1  # type: ignore[index]

        # 5. Live catalog sanity check (skipped only if local catalogs absent)
        if builder.sim_readiness_available():
            live_chulane = paired_series.simulator_readiness_audit(
                store, [COMMANDER], cards=deck_cards
            )
            assert live_chulane["available"] is True
            assert live_chulane["deck"]["total"] == 4  # type: ignore[index]
    finally:
        store.close()


def test_paired_manager_isolates_distinct_data_folders(tmp_path: Path) -> None:
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    store_a, _ = _make_store(folder_a)
    store_b, _ = _make_store(folder_b)
    try:
        rev_a = create_revision(
            store_a,
            deck_id="iso-a",
            name="Iso A",
            branch="main",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-forest", 99, "main"),
            ],
        )
        rev_b = create_revision(
            store_a,
            deck_id="iso-a",
            name="Iso A",
            branch="var",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-sol-ring", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )

        def _tied(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            did = "iso-a--base" if arm == "base" else "iso-a--variant"
            return {
                "exposure": _mock_exposure(  # type: ignore[typeddict-item]
                    f"{arm}-{seed}-{seat}", seed=seed, seat=seat, tested_deck_id=did, won=False
                ),
                "failure_class": None,
            }

        mgr = PairedSeriesManager()
        job = mgr.start_series(
            store_a,
            folder_a / "studio_data",
            base_revision_id=rev_a,
            variant_revision_id=rev_b,
            budget_pairs=4,
            look_every_pairs=4,
            rotate_seats=False,
            play_override=_tied,
        )
        _wait_job(mgr, folder_a / "studio_data", job.series_id)
        assert len(mgr.list_series(folder_a / "studio_data")) == 1
        assert mgr.list_series(folder_b / "studio_data") == []
        assert mgr.get_series(folder_b / "studio_data", job.series_id) is None
    finally:
        store_a.close()
        store_b.close()


def test_web_paired_and_readiness_routes_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, folder = _make_store(tmp_path)
    try:
        for name in ("Sol Ring", "Llanowar Elves", "Arcane Signet"):
            _seed_signal(store, name, edhrec_pct=0.7, cohort_pct=0.7)
        rev_a = create_revision(
            store,
            deck_id="chulane-web",
            name="Chulane Web",
            branch="main",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-sol-ring", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )
        rev_b = create_revision(
            store,
            deck_id="chulane-web",
            name="Chulane Web",
            branch="var",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-signet", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )
    finally:
        store.close()

    # Pre-seed one persisted .paired.json file on disk to test list/get routes cleanly
    persisted_id = "paired-999999-1-abcd1234"
    games_dir = folder / "games"
    games_dir.mkdir(parents=True, exist_ok=True)
    (games_dir / f"{persisted_id}.paired.json").write_text(
        json.dumps(
            {
                "schema": paired_series.SCHEMA_PAIRED_JOB,
                "series_id": persisted_id,
                "status": "completed",
                "base_ref": rev_a,
                "variant_ref": rev_b,
                "pod": "precon",
                "budget_pairs": 4,
                "pairs_attempted": 4,
                "created_at": now_utc(),
                "result": {"status": "NOT_DECIDED", "difference_pp": 0.0},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("STUDIO_GAMES_DIR", str(games_dir))
    app = create_app(folder)
    client = TestClient(app)
    hdr = {"x-studio": "1"}

    listed = client.get("/api/simulations/paired")
    assert listed.status_code == 200
    assert any(item["series_id"] == persisted_id for item in listed.json())

    one = client.get(f"/api/simulations/paired/{persisted_id}")
    assert one.status_code == 200
    assert one.json()["status"] == "completed"

    missing_get = client.get("/api/simulations/paired/paired-unknown-1")
    assert missing_get.status_code == 404

    missing_cancel = client.post("/api/simulations/paired/paired-unknown-1/cancel", headers=hdr)
    assert missing_cancel.status_code == 404

    bad_id = client.get("/api/simulations/paired/invalid!id")
    assert bad_id.status_code == 422

    # Same revision must return 422
    same_err = client.post(
        "/api/simulations/paired",
        json={"base_revision_id": rev_a, "variant_revision_id": rev_a},
        headers=hdr,
    )
    assert same_err.status_code == 422

    # Readiness audit route
    audit_resp = client.post(
        "/api/simulations/readiness-audit",
        json={"commander": COMMANDER, "tiers": ["S", "A"]},
        headers=hdr,
    )
    assert audit_resp.status_code == 200
    payload = audit_resp.json()
    assert payload["schema"] == paired_series.SCHEMA_READINESS_AUDIT
    assert payload["commander"] == [COMMANDER]


def test_paired_js_csp_and_in_place_slot_refresh() -> None:
    paired_js = (STATIC_DIR / "paired.js").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert '<script src="paired.js"></script>' in index_html
    assert ".innerHTML" not in paired_js
    assert ".outerHTML" not in paired_js
    assert "eval(" not in paired_js
    assert "style:" not in paired_js
    assert "style =" not in paired_js
    assert "paired-monitor-slot" in paired_js
    assert "paired-history-slot" in paired_js
    assert "refreshPairedSlots(" in app_js


def _paired_js(calls: str) -> object:
    """Run paired.js under node with a German number stub and return ``calls`` as JSON."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = (
        "const StudioUI = {num: (v, d = 0) => Number(v).toLocaleString('de-DE', "
        "{minimumFractionDigits: d, maximumFractionDigits: d})};\n"
        + (STATIC_DIR / "paired.js").read_text(encoding="utf-8")
        + f"\nprocess.stdout.write(JSON.stringify({calls}));\n"
    )
    out = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=30, check=True
    )
    return json.loads(out.stdout)


def test_paired_js_renders_the_backend_plan_and_honest_sentences() -> None:
    """The dialog shows the backend's plan numbers; the sentences depend on the question."""
    plan = json.dumps(paired_series.planned_detectable_difference_pp(40, 4))
    out = _paired_js(
        "{"
        f"zero: planPairedLines({plan}, 0), above: planPairedLines({plan}, 2.5),"
        "nd0: notDecidedText({pairs_completed: 40, detectable_difference_pp: 31.25,"
        " question: {threshold_pp: 0}}),"
        "nd5: notDecidedText({pairs_completed: 40, detectable_difference_pp: null,"
        " question: {threshold_pp: 5}}),"
        "same: pairedAlignmentText({swapped_slots: 1, appended: 0, dropped: 0}),"
        "uneven: pairedAlignmentText({swapped_slots: 1, appended: 2, dropped: 0}),"
        "legacy: pairedAlignmentText(null),"
        "short: [pairedAlignmentShort(null), pairedAlignmentShort({appended: 0, dropped: 1}),"
        " pairedAlignmentShort({appended: 0, dropped: 0})],"
        "est: estimatePairedText(40, 4)}"
    )
    assert isinstance(out, dict)
    zero, above = out["zero"], out["above"]
    assert "ab etwa 31,3 bis 41,5 Prozentpunkten (95 %, Power 80 %)" in zero[0]
    assert "das heißt nie, dass eine Karte egal ist" in zero[0]
    assert "etwa 1.254 bis 2.195 Paare" in zero[1]
    assert "rund 800 Partien für ±3 pp" in zero[1]
    assert "0,63 als vorsichtiger Planungswert (exakt 0,612" in zero[2]
    assert "gepaart: Korrelation ungemessen" in zero[2]
    assert "Student-t mit 9 Freiheitsgraden" in zero[2]
    assert "Design-Effekt 1,75" in zero[2]
    # a question with a threshold never reads as "no difference"
    assert "Schwelle von 2,5 pp" in above[0] and "kein Unterschied" not in above[0]
    assert out["nd0"] == (
        "Kein Unterschied nachweisbar bei n = 40 Paaren; nachweisbar wären mindestens 31,3 pp "
        "(95 %, Power 80 %, aus der gemessenen Paar-Streuung). Das heißt nicht, dass die Karte "
        "egal ist."
    )
    assert "nicht entschieden bei n = 40" in out["nd5"] and "unbekannt" in out["nd5"]
    assert "Kein Unterschied" not in out["nd5"]
    assert out["same"] == "an Basis ausgerichtet: 1 getauscht, 0 angehängt, 0 entfallen"
    assert out["uneven"].endswith("nicht deckungsgleich (Kartenzahl verschieden)")
    assert out["legacy"] == "nicht ausgerichtet (ältere Serie)"
    assert out["short"] == ["nicht ausgerichtet (älter)", "nicht deckungsgleich", "ausgerichtet"]
    assert "für gepaarte Serien ist der Durchsatz ungemessen" in out["est"]
    paired_js = (STATIC_DIR / "paired.js").read_text(encoding="utf-8")
    assert "/api/simulations/paired-plan?" in paired_js
    assert 'res.stop_reason === "BUDGET_EXHAUSTED"' in paired_js


def test_paired_plan_route_serves_the_python_plan(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "studio_data"))
    response = client.get(
        "/api/simulations/paired-plan", params={"budget_pairs": 40, "seats_per_seed": 4}
    )
    assert response.status_code == 200
    assert response.json() == paired_series.planned_detectable_difference_pp(40, 4)
    bad = client.get("/api/simulations/paired-plan", params={"budget_pairs": 1})
    assert bad.status_code == 422


def test_aligned_variant_file_keeps_other_zones_and_refuses_a_wrong_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.engine.rules.project import load_rules_deck_snapshot
    from commander_lab.models import RulesDeckInput

    fillers = tuple(f"Filler {index:02d}" for index in range(96))

    def _deck(deck_id: str, main: tuple[str, ...]) -> RulesDeckInput:
        return RulesDeckInput(
            deck_id=deck_id,
            name=deck_id,
            commander_names=(COMMANDER,),
            mainboard=(*main, *fillers),
        )

    snap: dict[str, object] = {
        "deck_id": "v",
        "name": "v",
        "commander": {"commanders": [COMMANDER]},
        "cards": [
            {"oracle_name": "Aardvark", "quantity": 1, "zone": "main"},
            {"oracle_name": COMMANDER, "quantity": 1, "zone": "commander"},
            {"oracle_name": "Forest", "quantity": 2, "zone": "main"},
            {"oracle_name": "Spare", "quantity": 1, "zone": "sideboard"},
        ],
    }
    path = tmp_path / "variant.json"
    base = _deck("b", ("Forest", "Zephyr", "Forest"))
    variant = _deck("v", ("Aardvark", "Forest", "Forest"))
    aligned, alignment = paired_series._align_variant_file(base, variant, snap, path)
    assert aligned.mainboard == ("Forest", "Aardvark", "Forest", *fillers)
    assert alignment.swapped_slots == 1
    written = json.loads(path.read_text(encoding="utf-8"))
    zones = {(c["oracle_name"], c["zone"]) for c in written["cards"]}
    assert (COMMANDER, "commander") in zones and ("Spare", "sideboard") in zones
    assert load_rules_deck_snapshot(path).sideboard == ("Spare",)

    # a file that does not reload in the aligned order is refused, never played
    def _wrong(_path: object) -> RulesDeckInput:
        return _deck("v", ("Aardvark", "Forest", "Forest"))

    monkeypatch.setattr(paired_series, "load_rules_deck_snapshot", _wrong)
    with pytest.raises(ValueError, match="aligned order"):
        paired_series._align_variant_file(base, variant, snap, path)


# ---- Serien im Deck-Verlauf (#1404): studio/deck_series.py, GET /api/decks/{id}/series ----


def _stored_series(
    series_id: str,
    base: str,
    variant: str,
    *,
    status: str = "completed",
    budget: int = 40,
    played: int = 40,
    stop_reason: str = "BUDGET_EXHAUSTED",
    with_result: bool = True,
    created_at: str = "2026-11-10T10:00:00Z",
) -> dict[str, object]:
    """A job file in the shape ``PairedSeriesJob.to_dict`` writes."""
    result: dict[str, object] | None = None
    if with_result:
        result = {
            "status": "NOT_DECIDED",
            "stop_reason": stop_reason,
            "pairs_completed": played,
            "pairs_censored": 0,
            "pairs_played": played,
            "difference_pp": 2.5,
            "difference_ci95_pp": [-4.0, 9.0],
            "decision_level_pct": 95.0,
            "decision_ci_pp": [-5.5, 10.5],
            "seeds": [1000, 1001, 1002],
            "tested_seats": [0, 1, 2, 3],
            "pilots": ["pilot-1"],
            "bridge_jar_sha256s": ["a" * 64],
            "bridge_qualification_states": ["BRIDGE_ALIGNED"],
            "covered_by_sealed_epoch": True,
        }
    return {
        "schema": paired_series.SCHEMA_PAIRED_JOB,
        "series_id": series_id,
        "status": status,
        "base_ref": base,
        "variant_ref": variant,
        "pod": "precon",
        "budget_pairs": budget,
        "pairs_attempted": played,
        "tested_seats": [0, 1, 2, 3],
        "created_at": created_at,
        "error": None,
        "result": result,
    }


def _write_series(games: Path, payload: dict[str, object]) -> None:
    games.mkdir(parents=True, exist_ok=True)
    (games / f"{payload['series_id']}.paired.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_deck_series_filter_status_and_skips(tmp_path: Path) -> None:
    from commander_lab.studio import deck_series

    games = tmp_path / "games"
    wanted = ["rev@mine-1", "rev@mine-2"]
    _write_series(games, _stored_series("paired-1-1-aaaaaaaa", "rev@mine-1", "rev@other"))
    _write_series(
        games,
        _stored_series(
            "paired-2-1-bbbbbbbb",
            "repo:x",
            "rev@mine-2",
            played=12,
            stop_reason="DECIDED_ABOVE",
            created_at="2026-11-11T10:00:00Z",
        ),
    )
    _write_series(
        games,
        _stored_series(
            "paired-3-1-cccccccc",
            "rev@mine-1",
            "rev@other",
            status="cancelled",
            played=7,
            with_result=False,
            created_at="2026-11-12T10:00:00Z",
        ),
    )
    _write_series(
        games,
        _stored_series(
            "paired-4-1-dddddddd",
            "rev@mine-1",
            "rev@other",
            status="running",
            played=3,
            with_result=False,
            created_at="2026-11-13T10:00:00Z",
        ),
    )
    _write_series(games, _stored_series("paired-5-1-eeeeeeee", "rev@x", "rev@y"))
    (games / "paired-6-1-ffffffff.paired.json").write_text("{not json", encoding="utf-8")
    foreign = _stored_series("paired-7-1-99999999", "rev@mine-1", "rev@other")
    foreign["schema"] = "something-else"
    _write_series(games, foreign)
    mismatch = _stored_series("paired-8-1-88888888", "rev@mine-1", "rev@other")
    (games / "paired-9-1-77777777.paired.json").write_text(json.dumps(mismatch), encoding="utf-8")

    out = deck_series.deck_series(tmp_path, wanted)
    series = out["series"]
    assert isinstance(series, list)
    assert [item["series_id"] for item in series] == [
        "paired-4-1-dddddddd",
        "paired-3-1-cccccccc",
        "paired-2-1-bbbbbbbb",
        "paired-1-1-aaaaaaaa",
    ]
    assert out["skipped"] == 3
    status = {item["series_id"]: item for item in series}
    assert status["paired-1-1-aaaaaaaa"]["status"] == "completed"
    assert status["paired-2-1-bbbbbbbb"]["status"] == "stopped_early"
    assert status["paired-3-1-cccccccc"]["status"] == "cancelled"
    assert status["paired-4-1-dddddddd"]["status"] == "incomplete"
    done = status["paired-1-1-aaaaaaaa"]
    assert done["counts_as_result"] is True
    assert (done["pairs_completed"], done["pairs_planned"]) == (40, 40)
    assert done["difference_pp"] == 2.5
    assert done["difference_ci95_pp"] == [-4.0, 9.0]
    assert (done["seeds"], done["tested_seats"]) == ([1000, 1001, 1002], [0, 1, 2, 3])
    for sid in ("paired-3-1-cccccccc", "paired-4-1-dddddddd"):
        item = status[sid]
        assert item["counts_as_result"] is False
        assert item["difference_pp"] is None
        assert item["difference_ci95_pp"] is None
        assert item["pairs_completed"] is None
    by_rev = out["by_revision"]
    assert isinstance(by_rev, dict)
    assert {entry["role"] for entry in by_rev["rev@mine-2"]} == {"variant"}
    assert {entry["role"] for entry in by_rev["rev@mine-1"]} == {"base"}
    assert by_rev["rev@mine-2"][0]["counterpart_ref"] == "repo:x"
    # series written before the alignment carry no slot_alignment: marked, never pooled
    assert done["slot_alignment"] is None
    assert done["slot_alignment_state"] == "not_aligned_legacy"
    aligned = _stored_series("paired-10-1-12121212", "rev@mine-2", "rev@other")
    aligned["slot_alignment"] = {"swapped_slots": 1, "appended": 0, "dropped": 0}
    uneven = _stored_series("paired-11-1-34343434", "rev@mine-2", "rev@other")
    uneven["slot_alignment"] = {"swapped_slots": 0, "appended": 1, "dropped": 0}
    _write_series(games, aligned)
    _write_series(games, uneven)
    again = {
        item["series_id"]: item for item in deck_series.deck_series(tmp_path, wanted)["series"]
    }
    assert again["paired-10-1-12121212"]["slot_alignment_state"] == "aligned"
    assert again["paired-11-1-34343434"]["slot_alignment_state"] == "not_congruent"


def test_deck_series_empty_and_missing_folder(tmp_path: Path) -> None:
    from commander_lab.studio import deck_series

    out = deck_series.deck_series(tmp_path / "nowhere", ["rev@a"])
    assert out["series"] == []
    assert out["by_revision"] == {}
    assert out["skipped"] == 0
    assert out["data_class"] == "SIMULATED_RESULT"


def test_deck_series_route_filters_revisions_404_and_403(tmp_path: Path) -> None:
    store, folder = _make_store(tmp_path)
    try:
        cards = [
            RevisionCard("cid-chulane", 1, "commander"),
            RevisionCard("cid-forest", 99, "main"),
        ]
        rev_a = create_revision(store, deck_id="chulane-s", name="Chulane S", cards=cards)
        rev_b = create_revision(
            store,
            deck_id="chulane-s",
            name="Chulane S",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-forest", 98, "main"),
            ],
            parent_revision_id=rev_a,
        )
        assert rev_a != rev_b
        other = create_revision(store, deck_id="other-deck", name="Other", cards=cards)
    finally:
        store.close()
    _write_series(folder / "games", _stored_series("paired-1-1-aaaaaaaa", rev_a, rev_b))
    _write_series(folder / "games", _stored_series("paired-2-1-bbbbbbbb", other, "repo:z"))
    client = TestClient(create_app(folder))

    got = client.get("/api/decks/chulane-s/series")
    assert got.status_code == 200
    body = got.json()
    assert [item["series_id"] for item in body["series"]] == ["paired-1-1-aaaaaaaa"]
    assert {entry["role"] for entry in body["by_revision"][rev_a]} == {"base"}
    assert {entry["role"] for entry in body["by_revision"][rev_b]} == {"variant"}
    none_yet = client.get("/api/decks/other-deck/series").json()
    assert [item["series_id"] for item in none_yet["series"]] == ["paired-2-1-bbbbbbbb"]
    assert client.get("/api/decks/unknown-deck/series").status_code == 404
    foreign = client.get("/api/decks/chulane-s/series", headers={"host": "evil.example"})
    assert foreign.status_code == 403


def test_deck_series_js_csp_and_history_hook() -> None:
    js = (STATIC_DIR / "deckseries.js").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert '<script src="deckseries.js"></script>' in index_html
    assert "renderDeckSeries(" in app_js
    for forbidden in (".innerHTML", ".outerHTML", "eval(", "style:", "style =", "toLocaleString"):
        assert forbidden not in js
    assert "keine gespeicherte Serie" in js
    assert "DECK_SERIES_ALIGNMENT_TEXT[item.slot_alignment_state]" in js
    assert "nicht ausgerichtet (ältere Serie" in js


def test_deck_series_survives_hostile_files_and_malformed_results(tmp_path: Path) -> None:
    from commander_lab.studio import deck_series

    games = tmp_path / "games"
    _write_series(games, _stored_series("paired-1-1-aaaaaaaa", "rev@m", "rev@o"))
    (games / "paired-2-1-bbbbbbbb.paired.json").write_text("[" * 100000, encoding="utf-8")
    (games / "paired-3-1-cccccccc.paired.json").write_text(
        " " * (deck_series.MAX_FILE_BYTES + 1), encoding="utf-8"
    )
    (games / "paired-7-1-11111111.paired.json").mkdir()  # not a regular file
    special = 1
    if hasattr(os, "mkfifo"):  # a FIFO without a writer must be skipped, not opened
        os.mkfifo(games / "paired-8-1-22222222.paired.json")
        special += 1
    for sid, result in (
        ("paired-4-1-dddddddd", "not-a-dict"),
        ("paired-5-1-eeeeeeee", {"pairs_completed": "40", "pairs_played": "x", "seeds": "s"}),
        ("paired-6-1-ffffffff", {"pairs_completed": 0, "stop_reason": "NO_PAIRS"}),
    ):
        payload = _stored_series(sid, "rev@m", "rev@o")
        payload["result"] = result
        _write_series(games, payload)

    out = deck_series.deck_series(tmp_path, ["rev@m"])
    series = out["series"]
    assert isinstance(series, list)
    assert len(series) == 4
    assert out["skipped"] == 2 + special
    status = {item["series_id"]: item["status"] for item in series}
    assert status["paired-1-1-aaaaaaaa"] == "completed"
    for sid in ("paired-4-1-dddddddd", "paired-5-1-eeeeeeee", "paired-6-1-ffffffff"):
        assert status[sid] == "incomplete"


def test_deck_series_limits_are_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from commander_lab.studio import deck_series

    games = tmp_path / "games"
    for number in range(1, 6):
        _write_series(
            games,
            _stored_series(
                f"paired-{number}-1-aaaaaaa{number}",
                "rev@m",
                "rev@o",
                created_at=f"2026-11-0{number}T10:00:00Z",
            ),
        )
    monkeypatch.setattr(deck_series, "SCAN_LIMIT", 4)
    out = deck_series.deck_series(tmp_path, ["rev@m"])
    assert out["scan_truncated"] == 1
    assert out["scan_limit"] == 4
    assert len(cast(list[object], out["series"])) == 4
    monkeypatch.setattr(deck_series, "SCAN_LIMIT", 10)
    monkeypatch.setattr(deck_series, "SERIES_LIMIT", 2)
    capped = deck_series.deck_series(tmp_path, ["rev@m"])
    assert capped["truncated"] is True
    assert capped["scan_truncated"] == 0
    assert len(cast(list[object], capped["series"])) == 2


def test_deck_series_uncounted_seats_are_planned_only() -> None:
    from commander_lab.studio import deck_series

    raw = _stored_series("paired-1-1-aaaaaaaa", "rev@m", "rev@o", status="cancelled")
    raw["result"] = {"tested_seats": [9], "seeds": [1]}
    entry = deck_series._entry(raw, deck_series.series_status(raw))
    assert entry["counts_as_result"] is False
    assert entry["seats_planned"] is True
    assert entry["tested_seats"] == [0, 1, 2, 3]


def test_estimate_series_duration_scales_with_workers_and_api_validates_parallel_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    est_4 = paired_series.estimate_series_duration(40, workers=4, games_per_jvm=6)
    assert est_4["workers"] == 4
    assert est_4["games_per_jvm"] == 6
    assert est_4["estimated_games_per_hour"] == 540 * 4
    assert est_4["estimated_seconds"] == round(80 * 3600.0 / (540 * 4))

    store, folder = _make_store(tmp_path)
    try:
        rev_a = create_revision(
            store,
            deck_id="chulane-par",
            name="Chulane Par",
            branch="main",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-sol-ring", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )
        rev_b = create_revision(
            store,
            deck_id="chulane-par",
            name="Chulane Par",
            branch="var",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-signet", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )

        def _play(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            did = "chulane-par--base" if arm == "base" else "chulane-par--variant"
            return {
                "exposure": _mock_exposure(  # type: ignore[typeddict-item]
                    f"{arm}-{seed}-{seat}",
                    seed=seed,
                    seat=seat,
                    tested_deck_id=did,
                    won=(arm == "variant"),
                ),
                "failure_class": None,
            }

        mgr = PairedSeriesManager()
        job = mgr.start_series(
            store,
            folder,
            base_revision_id=rev_a,
            variant_revision_id=rev_b,
            budget_pairs=40,
            look_every_pairs=8,
            workers=4,
            games_per_jvm=6,
            play_override=_play,
        )
        assert job.workers == 4
        assert job.games_per_jvm == 6
        assert job.to_dict()["execution"] == {
            "workers": 4,
            "games_per_jvm": 6,
            "serial_gc": False,
            "appcds": False,
        }
        finished = _wait_job(mgr, folder, job.series_id)
        assert finished["status"] == "completed"
        assert finished["result"]["status"] == "DECIDED"  # type: ignore[index]

        app = create_app(folder)
        client = TestClient(app)
        bad_workers = client.post(
            "/api/simulations/paired",
            json={
                "base_revision_id": rev_a,
                "variant_revision_id": rev_b,
                "workers": 17,
            },
            headers={"x-studio": "1"},
        )
        assert bad_workers.status_code == 422
        bad_batch = client.post(
            "/api/simulations/paired",
            json={
                "base_revision_id": rev_a,
                "variant_revision_id": rev_b,
                "games_per_jvm": 25,
            },
            headers={"x-studio": "1"},
        )
        assert bad_batch.status_code == 422

        monkeypatch.setattr(
            paired_series.paired_series_manager, "start_series", lambda *_a, **_k: job
        )
        ok_resp = client.post(
            "/api/simulations/paired",
            json={
                "base_revision_id": rev_a,
                "variant_revision_id": rev_b,
                "workers": 3,
                "games_per_jvm": 5,
            },
            headers={"x-studio": "1"},
        )
        assert ok_resp.status_code == 200
    finally:
        store.close()
