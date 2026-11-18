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


def test_estimate_series_duration_is_a_floor_at_the_measured_batch_rate() -> None:
    est = paired_series.estimate_series_duration(20)
    assert est["budget_pairs"] == 20
    assert est["max_games"] == 40
    # the one measured rate: 541.2 games/hour for a whole 6-worker batch series (#1251)
    assert est["measured_batch_games_per_hour"] == 541.2
    assert est["minimum_seconds"] == round(40 * 3600.0 / 541.2)
    assert est["minimum_minutes"] == round(est["minimum_seconds"] / 60.0, 1)
    assert (est["estimated_seconds"], est["estimated_minutes"]) == (
        est["minimum_seconds"],
        est["minimum_minutes"],
    )
    assert est["minimum_is_lower_bound"] is True
    assert str(est["basis"]).startswith("mindestens ~")
    assert "estimated_games_per_hour" not in est
    # throughput of paired series is unmeasured
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
        pytest.skip("node is not installed: paired.js rendering NOT RUN, not a pass")
    script = (
        "const StudioUI = {num: (v, d = 0) => Number(v).toLocaleString('de-DE', "
        "{minimumFractionDigits: d, maximumFractionDigits: d})};\n"
        + (STATIC_DIR / "paired.js").read_text(encoding="utf-8")
        + f"\n(async () => {{ const out = {calls}; "
        "process.stdout.write(JSON.stringify(out)); })();\n"
    )
    out = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=30, check=True
    )
    return json.loads(out.stdout)


def test_paired_js_renders_the_backend_plan_and_honest_sentences() -> None:
    """The dialog shows the backend's plan numbers; the sentences depend on the question."""
    plan = json.dumps(paired_series.planned_detectable_difference_pp(40, 4))
    single = json.dumps(paired_series.planned_detectable_difference_pp(4, 4))
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
        "est: estimatePairedText(40, 4), est8: estimatePairedText(40, 8),"
        f"single: planPairedLines({single}, 0),"
        "loaded: await loadPairedPlanLines(async (url) => ({budget_pairs: 77,"
        " detectable_pp_low: 12.3, detectable_pp_high: 45.6, reference_effect_pp: 5,"
        " pairs_needed_low: 11, pairs_needed_high: 22, assumptions: {pair_sd: 0.63,"
        " pair_sd_independent_exact: 0.6124, degrees_of_freedom: 3, seats_per_seed: 2,"
        " design_effect: 1.25, block_correlation_assumed: 0.25}, url}), 77, 2, 0),"
        "url: await (async () => { let seen = ''; await loadPairedPlanLines("
        "async (u) => { seen = u; return {assumptions: {}}; }, 60, 4, 0); return seen; })()}"
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
    # the duration is a floor at the measured whole-series rate, never a maximum
    assert out["est"].startswith("Dauer: mindestens ~8,9 min für bis zu 80 Partien")
    assert "Für gepaarte Serien ist der Durchsatz ungemessen" in out["est"]
    assert "max." not in out["est"] and "keine sichere Untergrenze" not in out["est"]
    assert "keine sichere Untergrenze" in out["est8"]
    # one seed: no detectable difference can be planned (unknown, as in the evaluation)
    assert "unbekannt (nur ein Seed" in out["single"][0]
    # the plan box shows what the API returned, not numbers of its own
    loaded = out["loaded"]
    assert "ab etwa 12,3 bis 45,6 Prozentpunkten" in loaded[0]
    assert "etwa 11 bis 22 Paare" in loaded[1]
    assert "Student-t mit 3 Freiheitsgraden" in loaded[2]
    assert out["url"] == "/api/simulations/paired-plan?budget_pairs=60&seats_per_seed=4"
    paired_js = (STATIC_DIR / "paired.js").read_text(encoding="utf-8")
    assert "/api/simulations/paired-plan?" in paired_js
    assert 'res.stop_reason === "BUDGET_EXHAUSTED"' in paired_js
    # the history table carries the slot column for every stored series
    assert 'h("th", {}, "Plätze")' in paired_js
    assert "pairedAlignmentShort(item.slot_alignment)" in paired_js
    assert "loadPairedPlanLines(deps.api," in paired_js


def test_paired_plan_route_serves_the_python_plan(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "studio_data"))
    response = client.get(
        "/api/simulations/paired-plan", params={"budget_pairs": 40, "seats_per_seed": 4}
    )
    assert response.status_code == 200
    assert response.json() == paired_series.planned_detectable_difference_pp(40, 4)
    for params in (
        {"budget_pairs": 1},
        {"budget_pairs": 1001},
        {"budget_pairs": "abc"},
        {"budget_pairs": 40, "seats_per_seed": 0},
        {"budget_pairs": 40, "seats_per_seed": 7},
    ):
        bad = client.get("/api/simulations/paired-plan", params=params)
        assert bad.status_code == 422, params
    edge = client.get("/api/simulations/paired-plan", params={"budget_pairs": 1000}).json()
    assert edge["budget_pairs"] == 1000
    one_seed = client.get(
        "/api/simulations/paired-plan", params={"budget_pairs": 4, "seats_per_seed": 4}
    ).json()
    assert one_seed["detectable_pp_low"] is None and one_seed["detectable_pp_high"] is None


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
    # #1513's 540/h per worker stays visible, but only as an unmeasured assumption; the
    # duration is the floor at the measured whole-series rate (#1251)
    assert est_4["assumed_games_per_hour_unmeasured"] == 540 * 4
    assert est_4["estimated_seconds"] == round(80 * 3600.0 / 541.2)
    many = paired_series.estimate_series_duration(40, workers=8)
    assert many["minimum_is_lower_bound"] is False
    assert "keine sichere Untergrenze" in str(many["basis"])

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


def test_orphaned_running_series_is_reported_as_interrupted_and_resumed_identically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, folder = _make_store(tmp_path)
    try:
        rev_a = create_revision(
            store,
            deck_id="chulane",
            name="Chulane",
            branch="main",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-sol-ring", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )
        rev_b = create_revision(
            store,
            deck_id="chulane",
            name="Chulane",
            branch="var",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-signet", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )
        monkeypatch.setattr(paired_series, "_preflight_snapshot_cards", lambda *_a, **_k: None)

        def _make_deterministic_player(
            called: list[tuple[str, int, int]],
        ) -> paired_comparison.PairPlayer:
            def _play(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
                called.append((arm, seed, seat))
                if arm == "variant" and seed == 500 and seat == 1:
                    return {"exposure": None, "failure_class": "BRIDGE_TIMEOUT"}
                deck_id = "chulane--base" if arm == "base" else "chulane--variant"
                winner = [seat] if (arm == "variant" or seed % 2 == 0) else [(seat + 1) % 4]
                return {
                    "exposure": {
                        "game_id": f"g-{arm}-{seed}-{seat}",
                        "seed": seed,
                        "engine_commit": "5bd29ab6f318",
                        "pilot": "GenericCommanderPilot 1.0.0",
                        "decision_policy": "xmage-full-game-policy-1.0.0",
                        "winner_seats": winner,
                        "seats": [
                            {
                                "seat": seat,
                                "deck_id": deck_id,
                                "win_credit": 1.0 if seat in winner else 0.0,
                                "first_hand": [],
                                "seen_by_turn_3": [],
                            }
                        ],
                    },
                    "failure_class": None,
                }

            return _play

        # 1. Uninterrupted baseline run
        uninterrupted_calls: list[tuple[str, int, int]] = []
        mgr_full = paired_series.PairedSeriesManager()
        full_job = mgr_full.start_series(
            store,
            folder / "full",
            base_revision_id=rev_a,
            variant_revision_id=rev_b,
            pod="precon",
            budget_pairs=8,
            look_every_pairs=4,
            base_seed=500,
            workers=1,
            games_per_jvm=1,
            play_override=_make_deterministic_player(uninterrupted_calls),
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and full_job.status in {"pending", "running"}:
            time.sleep(0.02)
        assert full_job.status == "completed"
        assert full_job.result is not None

        # 2. Simulate an interrupted series on disk (first 3 pairs in progress.jsonl, status="running")
        mgr_init = paired_series.PairedSeriesManager()
        res_dir = folder / "resumed"

        class _CrashAfterThreePairs(RuntimeError):
            pass

        crash_calls: list[tuple[str, int, int]] = []
        base_player = _make_deterministic_player(crash_calls)

        def _crashing_player(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            if len(crash_calls) >= 6:
                raise _CrashAfterThreePairs("simulated power loss")
            return base_player(arm, seed, seat)

        crashed_job = mgr_init.start_series(
            store,
            res_dir,
            base_revision_id=rev_a,
            variant_revision_id=rev_b,
            pod="precon",
            budget_pairs=8,
            look_every_pairs=4,
            base_seed=500,
            workers=1,
            games_per_jvm=1,
            play_override=_crashing_player,
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and crashed_job.status in {"pending", "running"}:
            time.sleep(0.02)
        assert crashed_job.status == "failed"

        # Overwrite on-disk status to "running" to simulate a hard process kill without finally block
        disk_path = crashed_job.series_file()
        disk_payload = json.loads(disk_path.read_text(encoding="utf-8"))
        disk_payload["status"] = "running"
        disk_payload["ended_at"] = None
        disk_payload["error"] = None
        disk_payload["pairs_attempted"] = 3
        disk_path.write_text(json.dumps(disk_payload), encoding="utf-8")

        # 3. Fresh manager (no in-memory jobs) must report "interrupted" with 3/8 pairs
        mgr_fresh = paired_series.PairedSeriesManager()
        seen_one = mgr_fresh.get_series(res_dir, crashed_job.series_id)
        assert seen_one is not None
        assert seen_one["status"] == "interrupted"
        assert seen_one["pairs_attempted"] == 3
        assert seen_one["budget_pairs"] == 8
        assert seen_one["resumable"] is True
        listed = mgr_fresh.list_series(res_dir)
        assert any(
            row["series_id"] == crashed_job.series_id and row["status"] == "interrupted"
            for row in listed
        )

        # 4. Resume and verify only missing pairs play & final result matches uninterrupted run
        resumed_calls: list[tuple[str, int, int]] = []
        resumed_job = mgr_fresh.resume_series(
            res_dir,
            crashed_job.series_id,
            workers=1,
            games_per_jvm=1,
            play_override=_make_deterministic_player(resumed_calls),
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and resumed_job.status in {"pending", "running"}:
            time.sleep(0.02)
        assert resumed_job.status == "completed", resumed_job.error
        assert resumed_job.result is not None

        # Already-played 3 pairs (6 games) were NOT re-played
        assert len(resumed_calls) == len(uninterrupted_calls) - 6
        assert set(resumed_calls).isdisjoint(set(crash_calls))

        # Outcomes & O'Brien-Fleming looks are identical; censored failure class preserved
        for key in (
            "status",
            "answer",
            "stop_reason",
            "pairs_played",
            "pairs_completed",
            "pairs_censored",
            "difference_pp",
            "sign_test_p_value",
            "failure_classes",
        ):
            assert resumed_job.result[key] == full_job.result[key], key
        assert resumed_job.result["failure_classes"]["variant"].get("BRIDGE_TIMEOUT") == 1
        assert resumed_job.result["looks_planned"] == full_job.result["looks_planned"]
        assert resumed_job.result["looks_used"] == full_job.result["looks_used"]
        assert resumed_job.result["pairs"] == full_job.result["pairs"]
    finally:
        store.close()


def test_paired_resume_route_returns_updated_job_and_rejects_completed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, folder = _make_store(tmp_path)
    try:
        app = create_app(folder)
        client = TestClient(app)
        headers = {"x-studio": "1"}

        assert (
            client.post(
                "/api/simulations/paired/paired-missing-1/resume", headers=headers
            ).status_code
            == 404
        )

        # Write a completed series on disk -> 409 Conflict
        games_dir = folder / "games"
        games_dir.mkdir(parents=True, exist_ok=True)
        (games_dir / "paired-done-1.paired.json").write_text(
            json.dumps({"series_id": "paired-done-1", "status": "completed"}),
            encoding="utf-8",
        )
        assert (
            client.post("/api/simulations/paired/paired-done-1/resume", headers=headers).status_code
            == 409
        )

        # Mock resume_series on an interrupted series -> 200
        class _FakeJob:
            def to_dict(self) -> dict[str, object]:
                return {"series_id": "paired-int-1", "status": "running", "pairs_attempted": 3}

        monkeypatch.setattr(
            paired_series.paired_series_manager,
            "resume_series",
            lambda *_a, **_k: _FakeJob(),
        )
        ok = client.post("/api/simulations/paired/paired-int-1/resume", headers=headers)
        assert ok.status_code == 200
        assert ok.json()["series_id"] == "paired-int-1"
        assert ok.json()["status"] == "running"
    finally:
        store.close()


def test_paired_resume_persists_custom_opponents_and_rejects_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, folder = _make_store(tmp_path)
    try:
        rev_a = create_revision(
            store,
            deck_id="chulane",
            name="Chulane",
            branch="main",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-sol-ring", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )
        rev_b = create_revision(
            store,
            deck_id="chulane",
            name="Chulane",
            branch="var",
            cards=[
                RevisionCard("cid-chulane", 1, "commander"),
                RevisionCard("cid-signet", 1, "main"),
                RevisionCard("cid-forest", 98, "main"),
            ],
        )
        monkeypatch.setattr(paired_series, "_preflight_snapshot_cards", lambda *_a, **_k: None)

        custom_opponents = list(paired_series.POD_PRESETS["mixed"][:2])
        calls: list[tuple[str, int, int]] = []

        def _player(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            calls.append((arm, seed, seat))
            if len(calls) >= 2:
                raise RuntimeError("stop mid-pair")
            return {
                "exposure": _mock_exposure(  # type: ignore[typeddict-item]
                    f"{arm}-{seed}-{seat}",
                    seed=seed,
                    seat=seat,
                    tested_deck_id="chulane--base",
                    won=False,
                ),
                "failure_class": None,
            }

        mgr = paired_series.PairedSeriesManager()
        res_dir = folder / "opp_resume"
        job = mgr.start_series(
            store,
            res_dir,
            base_revision_id=rev_a,
            variant_revision_id=rev_b,
            pod="precon",
            opponent_ids=custom_opponents,
            budget_pairs=3,
            look_every_pairs=3,
            base_seed=700,
            workers=1,
            games_per_jvm=1,
            play_override=_player,
        )
        _wait_job(mgr, res_dir, job.series_id)
        assert job.status == "failed"

        disk_payload = json.loads(job.series_file().read_text(encoding="utf-8"))
        assert disk_payload["opponent_ids"] == custom_opponents
        assert len(disk_payload["opponent_deck_ids"]) == 2
        assert disk_payload["seed_plan"]["player_count"] == 3

        # Append a truncated line without trailing newline to progress.jsonl to verify crash guard
        prog_path = job.progress_file()
        with prog_path.open("ab") as handle:
            handle.write(b'{"arm":"variant","seed":700,"seat":0,"played":')

        # 1. Tampering opponent_ids to drop custom table must be rejected on resume
        tampered = dict(disk_payload)
        tampered["opponent_ids"] = None
        job.series_file().write_text(json.dumps(tampered), encoding="utf-8")
        mgr2 = paired_series.PairedSeriesManager()
        with pytest.raises(ValueError, match=r"weichen ab|Sitzanzahl"):
            mgr2.resume_series(
                res_dir,
                job.series_id,
                workers=1,
                games_per_jvm=1,
                play_override=lambda a, s, t: _player(a, s, t),
            )

        # 1b. Legacy series without opponent_deck_ids must NOT silently fall back to preset pod
        legacy = dict(disk_payload)
        legacy["opponent_ids"] = None
        legacy.pop("opponent_deck_ids", None)
        job.series_file().write_text(json.dumps(legacy), encoding="utf-8")
        legacy_view = mgr2.get_series(res_dir, job.series_id)
        assert legacy_view is not None and legacy_view["resumable"] is False
        with pytest.raises(ValueError, match="opponent_deck_ids fehlt"):
            mgr2.resume_series(
                res_dir,
                job.series_id,
                workers=1,
                games_per_jvm=1,
                play_override=lambda a, s, t: _player(a, s, t),
            )

        # 2. Restoring valid payload resumes mid-pair (base 700/0 skipped, variant 700/0 played)
        job.series_file().write_text(json.dumps(disk_payload), encoding="utf-8")
        resumed_calls: list[tuple[str, int, int]] = []

        def _resume_ok(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            resumed_calls.append((arm, seed, seat))
            return {
                "exposure": _mock_exposure(  # type: ignore[typeddict-item]
                    f"{arm}-{seed}-{seat}",
                    seed=seed,
                    seat=seat,
                    tested_deck_id=f"chulane--{arm}",
                    won=(arm == "variant"),
                ),
                "failure_class": None,
            }

        resumed = mgr2.resume_series(
            res_dir,
            job.series_id,
            workers=1,
            games_per_jvm=1,
            play_override=_resume_ok,
        )
        _wait_job(mgr2, res_dir, resumed.series_id)
        assert resumed.status == "completed", resumed.error
        assert ("base", 700, 0) not in resumed_calls
        assert ("variant", 700, 0) in resumed_calls
        assert len(resumed_calls) == 5  # 3 pairs * 2 arms - 1 already played base game
    finally:
        store.close()


def test_paired_resume_live_lockfile_and_engine_chunk_filtering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. Live running.lock prevents interrupted misclassification and double resume
    games_dir = tmp_path / "games"
    sid = "paired-999999-1-locktest"
    deck_dir = games_dir / "paired_decks" / sid
    deck_dir.mkdir(parents=True, exist_ok=True)
    (deck_dir / "base-a.json").write_text("{}", encoding="utf-8")
    (deck_dir / "variant-b.json").write_text("{}", encoding="utf-8")
    (games_dir / f"{sid}.paired.json").write_text(
        json.dumps(
            {
                "series_id": sid,
                "status": "running",
                "pod": "precon",
                "opponent_deck_ids": ["opp-a", "opp-b", "opp-c"],
                "budget_pairs": 4,
                "look_every_pairs": 2,
                "tested_seats": [0, 1],
                "threshold_pp": 0.0,
                "significance_level": 0.05,
                "seed_plan": {"first_seed": 100, "seeds_planned": 2, "player_count": 4},
            }
        ),
        encoding="utf-8",
    )
    (deck_dir / "running.lock").write_text(
        json.dumps({"series_id": sid, "pid": os.getpid(), "heartbeat": time.time()}),
        encoding="utf-8",
    )
    mgr = paired_series.PairedSeriesManager()
    live = mgr.get_series(tmp_path, sid)
    assert live is not None
    assert live["status"] == "running"
    assert live["resumable"] is False
    with pytest.raises(RuntimeError, match=r"running\.lock|läuft bereits"):
        mgr.resume_series(
            tmp_path, sid, play_override=lambda *_a: {"exposure": None, "failure_class": None}
        )

    # Stale heartbeat -> reported as interrupted & resumable even with current PID
    (deck_dir / "running.lock").write_text(
        json.dumps({"series_id": sid, "pid": os.getpid(), "heartbeat": time.time() - 600.0}),
        encoding="utf-8",
    )
    stale = mgr.get_series(tmp_path, sid)
    assert stale is not None
    assert stale["status"] == "interrupted"
    assert stale["resumable"] is True

    # Windows PID check must use OpenProcess (ctypes) and never os.kill
    import ctypes
    import sys
    from types import SimpleNamespace

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        os, "kill", lambda *_a: pytest.fail("os.kill must not be called on Windows")
    )
    win_state = {"alive": True}

    class _FakeK32:
        def OpenProcess(self, _access: int, _inherit: bool, pid: int) -> int:
            return 111 if pid == 4242 else 0

        def GetLastError(self) -> int:
            return 87

        def GetExitCodeProcess(self, _handle: int, out: object) -> int:
            out._obj.value = 259 if win_state["alive"] else 0  # type: ignore[attr-defined]
            return 1

        def CloseHandle(self, _handle: int) -> int:
            return 1

    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(kernel32=_FakeK32()), raising=False)
    (deck_dir / "running.lock").write_text(
        json.dumps({"series_id": sid, "pid": 4242, "heartbeat": time.time()}),
        encoding="utf-8",
    )
    win_live = mgr.get_series(tmp_path, sid)
    assert win_live is not None and win_live["status"] == "running"
    win_state["alive"] = False
    win_dead = mgr.get_series(tmp_path, sid)
    assert win_dead is not None and win_dead["status"] == "interrupted" and win_dead["resumable"]
    monkeypatch.undo()

    # Dead lockfile -> reported as interrupted & resumable
    (deck_dir / "running.lock").write_text(
        json.dumps({"series_id": sid, "pid": 99999999}), encoding="utf-8"
    )
    dead = mgr.get_series(tmp_path, sid)
    assert dead is not None
    assert dead["status"] == "interrupted"
    assert dead["resumable"] is True

    # Missing seed_plan -> not resumable
    (games_dir / f"{sid}.paired.json").write_text(
        json.dumps({"series_id": sid, "status": "failed", "pod": "precon"}), encoding="utf-8"
    )
    no_plan = mgr.get_series(tmp_path, sid)
    assert no_plan is not None
    assert no_plan["resumable"] is False

    # 2. Engine-path chunk filtering skips already-preloaded arm+seed+seat
    from commander_lab.models import RulesDeckInput

    base_deck = RulesDeckInput(
        deck_id="chulane--base",
        name="Base",
        commander_names=(COMMANDER,),
        mainboard=("Forest",) * 99,
    )
    var_deck = RulesDeckInput(
        deck_id="chulane--variant",
        name="Var",
        commander_names=(COMMANDER,),
        mainboard=("Island",) * 99,
    )
    opp_decks = [
        RulesDeckInput(
            deck_id=f"opp-{i}",
            name=f"Opp {i}",
            commander_names=(COMMANDER,),
            mainboard=("Plains",) * 99,
        )
        for i in range(3)
    ]
    paths_by_id = {
        d.deck_id: tmp_path / f"{d.deck_id}.json" for d in [base_deck, var_deck, *opp_decks]
    }
    recorded_calls: list[tuple[str, list[int]]] = []

    def _fake_play_recorded_games(
        _data_folder: Path,
        _deck_paths: list[Path],
        series_games: list[paired_comparison.SeriesGame],
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        seeds = [g.seed for g in series_games]
        arm = "variant" if any("--variant" in str(p) for p in _deck_paths) else "base"
        recorded_calls.append((arm, seeds))
        return [
            {
                "game_id": g.game_id,
                "seed": g.seed,
                "winner_seats": [0],
                "seats": [],
            }
            for g in series_games
        ]

    from commander_lab.studio import play_batch as studio_play_batch

    monkeypatch.setattr(studio_play_batch, "play_recorded_games", _fake_play_recorded_games)
    monkeypatch.setattr(
        paired_comparison,
        "_summary_to_played_game",
        lambda summary: {
            "exposure": _mock_exposure(
                str(summary["game_id"]),
                seed=int(summary["seed"]),  # type: ignore[arg-type]
                seat=0,
                tested_deck_id="chulane--variant"
                if "-variant-" in str(summary["game_id"])
                else "chulane--base",
                won=False,
            ),
            "failure_class": None,
        },
    )

    preloaded: dict[tuple[str, int, int], paired_comparison.PlayedGame] = {
        ("base", 100, 0): {
            "exposure": _mock_exposure(  # type: ignore[typeddict-item]
                "pre-base-100-0", seed=100, seat=0, tested_deck_id="chulane--base", won=False
            ),
            "failure_class": None,
        }
    }
    player = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="paired-chunk-test",
        base_deck=base_deck,
        variant_deck=var_deck,
        opponents=opp_decks,
        paths_by_deck_id=paths_by_id,
        seeds=[100],
        tested_seats=[0],
        budget_pairs=1,
        look_every_pairs=1,
        workers=1,
        games_per_jvm=1,
        preloaded=preloaded,
    )
    res_base = player("base", 100, 0)
    res_var = player("variant", 100, 0)
    assert res_base["exposure"] is not None
    assert res_var["exposure"] is not None
    assert recorded_calls == [("variant", [100])]
