"""Self-contained unit tests for PR DB-C (#1404 op. 6 paired series & C-3 readiness audit)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, paired_comparison, paired_series, strength_view
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
        "engine_commit": "f4d12f6e8066203fba7aa38bd35ea3358117393d",
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
        mgr = PairedSeriesManager()
        with pytest.raises(ValueError, match="verschiedene"):
            mgr.start_series(
                store,
                folder,
                base_revision_id=rev_a,
                variant_revision_id=rev_a,
                play_override=lambda *_: {"exposure": None, "failure_class": "noop"},
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


def test_simulator_readiness_audit_fail_closed_gaps_and_real_chulane(tmp_path: Path) -> None:
    store, _folder = _make_store(tmp_path)
    try:
        for name in ("Sol Ring", "Llanowar Elves", "Arcane Signet"):
            _seed_signal(store, name, edhrec_pct=0.8, cohort_pct=0.8)
        _add_card(store, "cid-mystery", "Mystery Card Not In Engine", roles=("removal",))
        _seed_signal(store, "Mystery Card Not In Engine", edhrec_pct=0.95, cohort_pct=0.95)

        deck_cards = [
            RevisionCard("cid-chulane", 1, "commander"),
            RevisionCard("cid-sol-ring", 1, "main"),
            RevisionCard("cid-forest", 98, "main"),
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

        # 2. Reports missing engine status & missing pilot knowledge with exact denominators
        audit = paired_series.simulator_readiness_audit(
            store,
            [COMMANDER],
            cards=deck_cards,
            tiers=("S", "A"),
            available_check=lambda: True,
            status_lookup=lambda name: "MISSING" if "Mystery" in name else "OK",
            pilot_known=lambda name: "Mystery" not in name,
        )
        assert audit["available"] is True
        assert audit["status"] == "GAPS_FOUND"
        assert audit["deck"]["total"] == 3  # type: ignore[index]
        assert audit["deck"]["ready"] == 3  # type: ignore[index]
        free = audit["free_top_candidates"]
        assert isinstance(free, dict)
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
    finally:
        store.close()


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


def test_paired_js_csp_and_no_inline_styles() -> None:
    paired_js = (STATIC_DIR / "paired.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert '<script src="paired.js"></script>' in index_html
    assert ".innerHTML" not in paired_js
    assert ".outerHTML" not in paired_js
    assert "eval(" not in paired_js
    assert "style:" not in paired_js
    assert "style =" not in paired_js
