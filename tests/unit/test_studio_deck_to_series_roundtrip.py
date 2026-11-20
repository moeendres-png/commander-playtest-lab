"""Roundtrip test: saved deck revision -> game -> paired series -> deck history (#1531).

Fake-Grenze (keine echte Engine):
- ``POST /api/games`` nutzt ``launch.start_game`` inkl. ``prepare_table_deck_paths`` und ersetzt
  nur ``launch.engine_command``, ``launch._preflight_game_cards`` (falls vorhanden) sowie
  ``launch.subprocess.Popen`` (schreibt einen minimalen ``.jsonl``-Marker).
- ``POST /api/simulations/paired`` ersetzt ``_preflight_snapshot_cards`` (No-Op) und nutzt
  ``play_override`` mit synthetischen Exposures (``engine_commit="5bd29ab6f318"``).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from commander_lab.studio import launch, paired_comparison, paired_series
from commander_lab.studio.decks import lab_snapshot
from commander_lab.studio.store import DataClass, StudioStore
from commander_lab.studio.web import create_app


def _seed_cards(store: StudioStore) -> None:
    src = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title="roundtrip_test_source",
        sha256="0" * 64,
    )
    cards = [
        ("c_chulane", "Chulane, Teller of Tales", "WUG"),
        ("c_forest", "Forest", "G"),
        ("c_island", "Island", "U"),
        ("c_plains", "Plains", "W"),
        ("c_sol_ring", "Sol Ring", "C"),
    ]
    for card_id, name, ci in cards:
        store.connection.execute(
            "INSERT OR IGNORE INTO card(card_id, oracle_name, color_identity, source_id) "
            "VALUES (?, ?, ?, ?)",
            (card_id, name, ci, src),
        )
    store.connection.execute(
        "INSERT OR IGNORE INTO deck(deck_id, name, created_at) VALUES (?, ?, ?)",
        ("chulane-rt", "Chulane Roundtrip", "2026-11-18T00:00:00Z"),
    )
    store.connection.execute(
        "INSERT OR IGNORE INTO deck(deck_id, name, created_at) VALUES (?, ?, ?)",
        ("other-rt", "Other Deck", "2026-11-18T00:00:00Z"),
    )
    store.connection.commit()


def _deck_payload(forest_count: int, island_count: int) -> list[dict[str, object]]:
    return [
        {"card_id": "c_chulane", "quantity": 1, "zone": "commander"},
        {"card_id": "c_sol_ring", "quantity": 1, "zone": "main"},
        {"card_id": "c_plains", "quantity": 20, "zone": "main"},
        {"card_id": "c_forest", "quantity": forest_count, "zone": "main"},
        {"card_id": "c_island", "quantity": island_count, "zone": "main"},
    ]


def test_deck_revision_to_game_and_paired_series_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = StudioStore.open(tmp_path)
    try:
        _seed_cards(store)
    finally:
        store.close()

    app = create_app(tmp_path)
    client = TestClient(app)
    headers = {"X-Studio": "1"}

    # 1. Save base, variant and two revisions on an unrelated deck via the deckbuilder route
    res_base = client.post(
        "/api/decks/chulane-rt/revisions",
        headers=headers,
        json={"cards": _deck_payload(40, 38), "note": "Basis 40 Forest", "branch": "main"},
    )
    assert res_base.status_code == 200
    base_rev = res_base.json()["revision_id"]

    res_var = client.post(
        "/api/decks/chulane-rt/revisions",
        headers=headers,
        json={
            "cards": _deck_payload(38, 40),
            "parent_revision_id": base_rev,
            "note": "Variante 38 Forest",
            "branch": "var-islands",
        },
    )
    assert res_var.status_code == 200
    var_rev = res_var.json()["revision_id"]

    res_other = client.post(
        "/api/decks/other-rt/revisions",
        headers=headers,
        json={"cards": _deck_payload(45, 33), "note": "Anderes Deck", "branch": "main"},
    )
    assert res_other.status_code == 200
    other_rev = res_other.json()["revision_id"]

    res_other_var = client.post(
        "/api/decks/other-rt/revisions",
        headers=headers,
        json={
            "cards": _deck_payload(44, 34),
            "parent_revision_id": other_rev,
            "note": "Anderes Deck Var",
            "branch": "var",
        },
    )
    assert res_other_var.status_code == 200
    other_var_rev = res_other_var.json()["revision_id"]

    # Read canonical deck_hash from store for exact comparison
    store = StudioStore.open(tmp_path)
    try:
        base_snap = lab_snapshot(store, base_rev)
        var_snap = lab_snapshot(store, var_rev)
        other_snap = lab_snapshot(store, other_rev)
    finally:
        store.close()

    # 2. Start a game from base_rev via POST /api/games through launch.start_game
    #    and prepare_table_deck_paths, mocking only the engine command & Popen.
    captured_commands: list[list[str]] = []

    class _FakePopen:
        def __init__(self, command: list[str], **_kwargs: object) -> None:
            captured_commands.append(list(command))
            game_id = command[command.index("--game-id") + 1]
            marker = tmp_path / "games" / f"{game_id}.jsonl"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text('{"event":"fake"}\n', encoding="utf-8")

        def poll(self) -> int:
            return 0

    precon_ids = [deck_id for deck_id, *_rest in launch._precons()[:3]]
    assert len(precon_ids) == 3

    with monkeypatch.context() as mp:
        mp.setattr(launch, "engine_command", lambda *_a, **_kw: ("fake-java",))
        if hasattr(launch, "_preflight_game_cards"):
            mp.setattr(launch, "_preflight_game_cards", lambda *_a, **_kw: None)
        mp.setattr(launch.subprocess, "Popen", _FakePopen)

        res_game = client.post(
            "/api/games",
            headers=headers,
            json={
                "revision_id": base_rev,
                "opponent_ids": precon_ids,
                "seed": 42,
            },
        )
    assert res_game.status_code == 200, res_game.text
    game_id = res_game.json()["game_id"]
    assert len(captured_commands) == 1
    cmd = captured_commands[0]
    written_own_deck = Path(cmd[cmd.index("--deck") + 1])
    assert written_own_deck.is_file()
    written_payload = json.loads(written_own_deck.read_text(encoding="utf-8"))
    assert written_payload["studio_deck_hash"] == base_snap["studio_deck_hash"]
    assert (tmp_path / "games" / f"{game_id}.jsonl").is_file()

    # 3. Start a paired series (base_rev vs var_rev) via POST /api/simulations/paired
    monkeypatch.setattr(paired_series, "_preflight_snapshot_cards", lambda *a, **kw: None)
    monkeypatch.setattr(
        paired_series,
        "series_engine",
        lambda *a, **kw: launch.SeriesEngine(
            command=("fake-java",),
            jar_path=None,
            games_per_jvm=1,
            serial_gc=False,
            appcds_archive=None,
            appcds_used=False,
        ),
    )

    orig_start_series = paired_series.paired_series_manager.start_series

    def _make_player(base_deck_id: str, var_deck_id: str) -> paired_comparison.PairPlayer:
        def fake_pair_player(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            deck_id = base_deck_id if arm == "base" else var_deck_id
            # Variant wins every game (100%); base loses every game (0%) -> +100 pp
            winner_seats = [seat] if arm == "variant" else [(seat + 1) % 4]
            return {
                "exposure": {
                    "game_id": f"sim-{deck_id}-{arm}-{seed}-{seat}",
                    "seed": seed,
                    "engine_commit": "5bd29ab6f318",
                    "pilot": "GenericCommanderPilot 1.0.0",
                    "decision_policy": "xmage-full-game-policy-1.0.0",
                    "winner_seats": winner_seats,
                    "seats": [
                        {
                            "seat": seat,
                            "deck_id": deck_id,
                            "win_credit": 1.0 if seat in winner_seats else 0.0,
                            "first_hand": [],
                            "seen_by_turn_3": [],
                        }
                    ],
                },
                "failure_class": None,
            }

        return fake_pair_player

    def wrapped_start_series(*args: object, **kwargs: object) -> paired_series.PairedSeriesJob:
        base_id = str(kwargs.get("base_revision_id", "")).split("@", 1)[0]
        var_id = str(kwargs.get("variant_revision_id", "")).split("@", 1)[0]
        if base_id == var_id:
            base_id = f"{base_id}--base"
            var_id = f"{var_id}--variant"
        kwargs["play_override"] = _make_player(base_id, var_id)
        return orig_start_series(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(paired_series.paired_series_manager, "start_series", wrapped_start_series)

    res_paired = client.post(
        "/api/simulations/paired",
        headers=headers,
        json={
            "base_revision_id": base_rev,
            "variant_revision_id": var_rev,
            "pod": "precon",
            "budget_pairs": 4,
            "look_every_pairs": 2,
            "base_seed": 100,
        },
    )
    assert res_paired.status_code == 200, res_paired.text
    series_id = res_paired.json()["series_id"]

    # Also start a second series for the OTHER deck to verify deck-history isolation
    res_other_paired = client.post(
        "/api/simulations/paired",
        headers=headers,
        json={
            "base_revision_id": other_rev,
            "variant_revision_id": other_var_rev,
            "pod": "precon",
            "budget_pairs": 4,
            "look_every_pairs": 2,
            "base_seed": 200,
        },
    )
    assert res_other_paired.status_code == 200, res_other_paired.text
    other_series_id = res_other_paired.json()["series_id"]

    # Wait for both background series to complete (including disk persistence)
    deadline = time.monotonic() + 10.0
    for sid in (series_id, other_series_id):
        series_file = tmp_path / "games" / f"{sid}.paired.json"
        while time.monotonic() < deadline:
            poll = client.get(f"/api/simulations/paired/{sid}", headers=headers)
            assert poll.status_code == 200
            payload = poll.json()
            if payload["status"] == "completed" and series_file.is_file():
                disk_doc = json.loads(series_file.read_text(encoding="utf-8"))
                if disk_doc.get("status") == "completed":
                    break
            if payload["status"] in {"failed", "cancelled"}:
                pytest.fail(f"series {sid} ended with {payload['status']}: {payload.get('error')}")
            time.sleep(0.05)
        else:  # pragma: no cover
            pytest.fail(
                f"series {sid} did not complete in time (last={client.get(f'/api/simulations/paired/{sid}', headers=headers).json()})"
            )

    # Verify the written paired deck snapshots carry the exact saved deck_hash
    deck_dir = tmp_path / "games" / "paired_decks" / series_id
    base_written = json.loads(sorted(deck_dir.glob("base-*.json"))[0].read_text())
    var_written = json.loads(sorted(deck_dir.glob("variant-*.json"))[0].read_text())
    assert (str(base_written["studio_deck_hash"]), str(var_written["studio_deck_hash"])) == (
        str(base_snap["studio_deck_hash"]),
        str(var_snap["studio_deck_hash"]),
    )

    # 4. Read GET /api/decks/{deck_id}/series and verify SIMULATED_RESULT, outcomes & isolation
    res_hist = client.get("/api/decks/chulane-rt/series", headers=headers)
    assert res_hist.status_code == 200
    hist = res_hist.json()
    assert hist["data_class"] == "SIMULATED_RESULT"
    by_rev = hist["by_revision"]
    assert base_rev in by_rev
    assert var_rev in by_rev
    assert other_rev not in by_rev

    base_entries = [ref for ref in by_rev[base_rev] if ref["series_id"] == series_id]
    var_entries = [ref for ref in by_rev[var_rev] if ref["series_id"] == series_id]
    assert len(base_entries) == 1 and len(var_entries) == 1
    assert base_entries[0]["role"] == "base"
    assert base_entries[0]["counterpart_ref"] == var_rev
    assert var_entries[0]["role"] == "variant"
    assert var_entries[0]["counterpart_ref"] == base_rev
    assert all(ref["series_id"] != other_series_id for ref in by_rev[base_rev])
    assert all(ref["series_id"] != other_series_id for ref in by_rev[var_rev])

    series_entries = [s for s in hist["series"] if s["series_id"] == series_id]
    assert len(series_entries) == 1
    entry = series_entries[0]
    assert entry["base_ref"] == base_rev
    assert entry["variant_ref"] == var_rev
    assert entry["status"] == "completed", entry
    assert entry["counts_as_result"] is True
    assert entry["pairs_completed"] == 4
    assert entry["difference_pp"] == 100.0
    assert entry["stop_reason"] == "BUDGET_EXHAUSTED"

    # Series on other_rev must not leak chulane-rt's base-vs-var series into other-rt
    res_other_hist = client.get("/api/decks/other-rt/series", headers=headers)
    assert res_other_hist.status_code == 200
    other_hist = res_other_hist.json()
    assert other_hist["data_class"] == "SIMULATED_RESULT"
    other_by_rev = other_hist["by_revision"]
    assert other_rev in other_by_rev
    assert base_rev not in other_by_rev
    assert var_rev not in other_by_rev
    other_sids = {ref["series_id"] for ref in other_by_rev[other_rev]}
    assert other_series_id in other_sids
    assert series_id not in other_sids
    assert other_snap["studio_deck_hash"] != base_snap["studio_deck_hash"]

    # 5. B2 (#1658): draft -> variant -> plan -> series (fake engine) -> adopt. The plan file is
    #    written before the first game, the history shows the experiment and its decision, and
    #    adopting moves the deck's ``main`` branch to the variant.
    plan = {
        "question": "38 statt 40 Wälder",
        "question_kind": "axis",
        "deck_id": "chulane-rt",
        "base": {"revision_id": base_rev},
        "variants": [{"revision_id": var_rev}],
        "table": {"seats": 4, "opponents": precon_ids},
        "purpose": "exploration",
        "budget_pairs": 4,
        "look_every_pairs": 2,
        "first_seed": 300,
    }
    res_exp = client.post("/api/experiments", headers=headers, json={"plan": plan})
    assert res_exp.status_code == 200, res_exp.text
    experiment = res_exp.json()
    exp_dir = tmp_path / "games" / "experiments" / experiment["experiment_id"]
    assert json.loads((exp_dir / "plan.json").read_text())["plan_sha"] == experiment["plan_sha"]
    exp_file = tmp_path / "games" / f"{experiment['series_id']}.paired.json"
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if exp_file.is_file() and json.loads(exp_file.read_text())["status"] == "completed":
            break
        time.sleep(0.05)
    else:  # pragma: no cover
        pytest.fail("experiment series did not complete in time")
    res_adopt = client.post(
        f"/api/experiments/{experiment['experiment_id']}/decision",
        headers=headers,
        json={"decision": "adopted", "note": "Owner übernimmt"},
    )
    assert res_adopt.status_code == 200, res_adopt.text
    assert res_adopt.json()["tested"] is True
    store = StudioStore.open(tmp_path)
    try:
        main_now = store.connection.execute(
            "SELECT revision_id FROM deck_branch WHERE deck_id = 'chulane-rt' AND branch = 'main'"
        ).fetchone()[0]
    finally:
        store.close()
    assert main_now == var_rev
    hist = client.get("/api/decks/chulane-rt/series", headers=headers).json()
    exp_entry = next(s for s in hist["series"] if s["series_id"] == experiment["series_id"])
    assert exp_entry["counts_as_result"] is True and exp_entry["difference_pp"] == 100.0
    assert exp_entry["experiment"]["decision"] == "adopted"
    assert exp_entry["experiment"]["decision_text"] == "übernommen"
    assert exp_entry["experiment"]["plan_sha"] == experiment["plan_sha"]
    # the series played before B2 (no plan) is still in the history, unchanged
    assert any(s["series_id"] == series_id and s["experiment"] is None for s in hist["series"])
