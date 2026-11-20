"""SIMULATE at five and six seats behind the seat lock (#1702, Refs #1661, #1656, #1681).

The lock is not released here: ``launch.MAX_RELEASED_SEATS`` stays 4 and every test that plays a
five- or six-seat series lifts it in memory only (``monkeypatch``). The bridge is a test bridge
(``play_override``: synthetic exposures with N seat rows), no real engine ran: NOT_RUN.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from commander_lab.studio import launch, paired_comparison, paired_series
from commander_lab.studio.card_outcomes import outcomes_for_folder
from commander_lab.studio.store import StudioStore
from commander_lab.studio.table_spec import TableSpec
from commander_lab.studio.web import create_app
from tests.unit.test_studio_card_outcomes import DECK, _hash, _seats, _simple_frames, _write_log
from tests.unit.test_studio_experiments import _cards, _seed

HEADERS = {"X-Studio": "1"}
PODS = tuple(launch.POD_PRESETS)


# -- pod presets for n - 1 opponents ----------------------------------------------------------


@pytest.mark.parametrize("pod", PODS)
def test_pod_presets_name_five_distinct_existing_opponents_and_keep_the_four_seat_table(
    pod: str,
) -> None:
    by_id = {deck_id for deck_id, *_rest in launch._precons()}
    five = launch.pod_opponent_ids(pod, 5)
    assert len(five) == len(set(five)) == 5
    assert set(five) <= by_id  # every named deck exists in the repository
    # the four-seat table is the old preset, unchanged, and a smaller table is its prefix
    assert launch.pod_opponent_ids(pod, 3) == launch.POD_PRESETS[pod]
    for count in range(1, 6):
        assert launch.pod_opponent_ids(pod, count) == five[:count]
    assert five[:3] == launch.POD_PRESETS[pod]


def test_pod_preset_with_too_few_decks_is_an_honest_error_never_a_fill_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(launch, "POD_PRESET_EXTRA_OPPONENTS", {})
    assert len(launch.pod_opponent_ids("precon", 3)) == 3
    with pytest.raises(ValueError, match=r"nennt nur 3 Decks.*braucht 4.*nichts aufgefüllt"):
        launch.pod_opponent_ids("precon", 4)
    with pytest.raises(ValueError, match="braucht 5"):
        launch.pod_opponent_ids("precon", 5)
    with pytest.raises(ValueError, match="Unbekannter Gegnertisch"):
        launch.pod_opponent_ids("no-such-pod", 2)
    for bad in (0, 6):
        with pytest.raises(ValueError, match="1 to 5 opponents"):
            launch.pod_opponent_ids("precon", bad)


# -- the rotation plan -------------------------------------------------------------------------


@pytest.mark.parametrize("seats", [5, 6])
def test_a_block_is_n_squared_pairs_and_plays_every_start_and_tested_seat_once(
    seats: int,
) -> None:
    plan = paired_series.rotation_plan(seats, seats * seats, first_seed=2000)
    assert plan["tested_seats"] == list(range(seats))
    assert plan["seeds_planned"] == seats
    assert plan["pairs_per_block"] == plan["games_per_arm_per_block"] == seats * seats
    assert plan["max_games"] == 2 * seats * seats
    assert plan["rotation_complete"] is True and plan["remainder_pairs"] == 0
    assert plan["full_blocks"] == 1
    assert (plan["cells_total"], plan["cells_missing"]) == (seats * seats, 0)
    assert plan["cells_min_pairs"] == plan["cells_max_pairs"] == 1
    two = paired_series.rotation_plan(seats, 2 * seats * seats, first_seed=7)
    assert two["full_blocks"] == 2 and two["cells_min_pairs"] == two["cells_max_pairs"] == 2


def test_a_budget_that_is_no_whole_block_says_the_rotation_is_incomplete() -> None:
    short = paired_series.rotation_plan(5, 20)
    assert short["rotation_complete"] is False
    assert (short["full_blocks"], short["remainder_pairs"]) == (0, 20)
    assert short["cells_missing"] == 5 and short["cells_min_pairs"] == 0  # start seat 4 never
    six = paired_series.rotation_plan(6, 40)  # a budget the page offers today
    assert (six["seeds_planned"], six["full_blocks"], six["remainder_pairs"]) == (7, 1, 4)
    assert six["rotation_complete"] is False and six["cells_missing"] == 0
    assert six["cells_min_pairs"] == 1 and six["cells_max_pairs"] == 2
    fixed = paired_series.rotation_plan(5, 5, rotate_seats=False)
    assert fixed["tested_seats"] == [0] and fixed["rotation_complete"] is True
    for bad in (1, 7):
        with pytest.raises(ValueError, match="Tischgröße"):
            paired_series.rotation_plan(bad, 10)


# -- duration: measured for four seats only ---------------------------------------------------


def test_duration_is_unknown_where_no_throughput_is_measured_and_never_zero() -> None:
    four = paired_series.estimate_series_duration(40, table_size=4)
    assert four["duration_known"] is True and four["minimum_minutes"] == 8.9
    assert four["measured_table_seats"] == 4 and four["measured_games"] is None
    for seats in (2, 3, 5, 6):
        est = paired_series.estimate_series_duration(25, seats_per_seed=seats, table_size=seats)
        assert est["duration_known"] is False
        for key in ("minimum_seconds", "minimum_minutes", "estimated_seconds", "estimated_minutes"):
            assert est[key] is None, key
        assert est["minimum_is_lower_bound"] is False
        assert est["max_games"] == 50 and est["table_size"] == seats
        basis = str(est["basis"])
        assert basis.startswith("unbekannt (UNKNOWN)") and f"{seats} Sitzen" in basis
        assert "n = 0 Partien" in basis and "#1251" in basis and "bis zu 50 (25 je Arm)" in basis
    # the call without a table keeps naming the measured table, as before
    assert paired_series.estimate_series_duration(20)["duration_known"] is True


# -- the lock stays; the plan route plans behind it -------------------------------------------


def test_the_lock_constant_and_the_switch_are_unchanged() -> None:
    assert launch.MAX_RELEASED_SEATS == 4
    with pytest.raises(ValueError, match="tables of 5 seats are locked"):
        launch.validate_released_seat_count(4)
    with pytest.raises(ValueError, match="tables of 6 seats are locked"):
        launch.validate_released_seat_count(5)
    assert launch.validate_released_seat_count(5, allow_unreleased_seats=True) == 6


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """A Studio with a chulane-b2 base and variant; the paired series plays with a test bridge
    that answers N-seat exposures and records every game asked for."""
    store = StudioStore.open(tmp_path)
    try:
        _seed(store)
    finally:
        store.close()
    monkeypatch.setattr(paired_series, "_preflight_snapshot_cards", lambda *a, **k: None)
    calls: list[tuple[str, int, int]] = []
    manager = paired_series.paired_series_manager
    original = manager.start_series

    def player(table: int, base_id: str, variant_id: str) -> paired_comparison.PairPlayer:
        def play(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
            calls.append((arm, seed, seat))
            deck_id = base_id if arm == "base" else variant_id
            winners = [seat] if arm == "variant" else [(seat + 1) % table]
            rows = [
                {
                    "seat": s,
                    "deck_id": deck_id if s == seat else f"opp-{s}",
                    "win_credit": 1.0 if s in winners else 0.0,
                    "first_hand": [],
                    "seen_by_turn_3": [],
                }
                for s in range(table)
            ]
            return {
                "exposure": {
                    "game_id": f"t1702-{arm}-{seed}-{seat}",
                    "seed": seed,
                    "engine_commit": "5bd29ab6f318",
                    "pilot": "GenericCommanderPilot 1.0.0",
                    "decision_policy": "xmage-full-game-policy-1.0.0",
                    "winner_seats": winners,
                    "seats": rows,
                },
                "failure_class": None,
            }

        return play

    def start(*args: object, **kwargs: object) -> paired_series.PairedSeriesJob:
        base = str(kwargs["base_revision_id"]).split("@", 1)[0]
        ids = kwargs.get("opponent_ids")
        table = kwargs.get("table_size") or (len(ids) + 1 if isinstance(ids, list) else 4)
        kwargs["play_override"] = player(int(str(table)), f"{base}--base", f"{base}--variant")
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(manager, "start_series", start)
    client = TestClient(create_app(tmp_path))
    revs: dict[str, str] = {}
    for name, forests, parent in (("base", 40, None), ("variant", 38, "base")):
        res = client.post(
            "/api/decks/chulane-b2/revisions",
            headers=HEADERS,
            json={
                "cards": _cards(forests),
                "note": name,
                "branch": "main" if parent is None else name,
                **({"parent_revision_id": revs[parent]} if parent else {}),
            },
        )
        assert res.status_code == 200, res.text
        revs[name] = res.json()["revision_id"]
    return {"client": client, "folder": tmp_path, "revs": revs, "calls": calls, "player": player}


def _body(lab: dict[str, object], **over: object) -> dict[str, object]:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    body: dict[str, object] = {
        "base_revision_id": revs["base"],
        "variant_revision_id": revs["variant"],
        "pod": "precon",
        "base_seed": 2000,
        "look_every_pairs": 100,
    }
    body.update(over)
    return body


def _post(lab: dict[str, object], **over: object) -> object:
    client = lab["client"]
    assert isinstance(client, TestClient)
    return client.post("/api/simulations/paired", headers=HEADERS, json=_body(lab, **over))


def _finished(lab: dict[str, object], series_id: str) -> dict[str, object]:
    folder = Path(str(lab["folder"]))
    path = folder / "games" / f"{series_id}.paired.json"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("status") in {"completed", "failed", "cancelled"}:
                assert raw["status"] == "completed", raw.get("error")
                return raw
        time.sleep(0.05)
    pytest.fail(f"series {series_id} did not finish")


@pytest.mark.parametrize("seats", [5, 6])
def test_studio_still_refuses_a_five_or_six_seat_series_and_writes_nothing(
    lab: dict[str, object], seats: int
) -> None:
    for over in (
        {"table_size": seats, "budget_pairs": seats * seats},  # a pod preset sized to the table
        {"opponent_ids": list(launch.pod_opponent_ids("precon", seats - 1))},
        {"table_size": seats, "opponent_ids": list(launch.pod_opponent_ids("precon", seats - 1))},
    ):
        res = _post(lab, **over)
        assert res.status_code == 422, res.text  # type: ignore[attr-defined]
        assert f"tables of {seats} seats are locked" in res.json()["detail"]  # type: ignore[attr-defined]
    assert lab["calls"] == []
    assert not list((Path(str(lab["folder"])) / "games").glob("*.paired.json"))


def test_series_start_checks_the_table_size_against_the_opponents(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    res = _post(lab, table_size=5, opponent_ids=list(launch.pod_opponent_ids("precon", 3)))
    assert res.status_code == 422  # type: ignore[attr-defined]
    assert "braucht 4 Gegner, angegeben sind 3" in res.json()["detail"]  # type: ignore[attr-defined]
    monkeypatch.setattr(launch, "POD_PRESET_EXTRA_OPPONENTS", {})  # a preset too short for 5 seats
    res = _post(lab, table_size=5, budget_pairs=25)
    assert res.status_code == 422  # type: ignore[attr-defined]
    assert "nichts aufgefüllt" in res.json()["detail"]  # type: ignore[attr-defined]
    assert lab["calls"] == []
    assert not list((Path(str(lab["folder"])) / "games").glob("*.paired.json"))


@pytest.mark.parametrize("seats", [5, 6])
def test_with_the_lock_lifted_locally_the_series_route_plans_and_plays_whole_blocks(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch, seats: int
) -> None:
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)  # in memory, this test only
    block = seats * seats
    res = _post(lab, table_size=seats, budget_pairs=block)
    assert res.status_code == 200, res.text  # type: ignore[attr-defined]
    job = _finished(lab, res.json()["series_id"])  # type: ignore[attr-defined]
    # the table: the pod preset's first seats - 1 opponents, recorded by id (a resume plays them)
    assert job["opponent_ids"] == list(launch.pod_opponent_ids("precon", seats - 1))
    assert len(job["opponent_deck_ids"]) == seats - 1  # type: ignore[arg-type]
    assert job["seed_plan"]["player_count"] == seats  # type: ignore[index]
    assert job["seed_plan"]["seeds_planned"] == seats  # type: ignore[index]
    assert job["tested_seats"] == list(range(seats))
    assert job["seed_plan"]["first_seed"] == 2000  # type: ignore[index]
    assert job["seed_plan"]["last_seed"] == 2000 + seats - 1  # type: ignore[index]
    # every planned game was asked for: both arms, every (starting seat, tested seat) once
    calls = lab["calls"]
    assert isinstance(calls, list) and len(calls) == 2 * block
    for arm in ("base", "variant"):
        cells = Counter((seed % seats, seat) for a, seed, seat in calls if a == arm)
        assert set(cells) == {(s, t) for s in range(seats) for t in range(seats)}
        assert set(cells.values()) == {1}
    result = job["result"]
    assert isinstance(result, dict)
    assert result["pairs_completed"] == block and result["pairs_censored"] == 0
    assert result["data_class"] == "SIMULATED_RESULT"
    assert job["games_played"] == 2 * block and job["games_planned_max"] == 2 * block
    # duration: nothing is measured at this table, so the record says unknown, never a number
    estimate = job["estimate"]
    assert isinstance(estimate, dict)
    assert estimate["duration_known"] is False and estimate["minimum_minutes"] is None
    assert estimate["table_size"] == seats and estimate["max_games"] == 2 * block


def test_series_without_a_table_size_keeps_the_four_seat_preset(
    lab: dict[str, object],
) -> None:
    res = _post(lab, budget_pairs=16)
    assert res.status_code == 200, res.text  # type: ignore[attr-defined]
    job = _finished(lab, res.json()["series_id"])  # type: ignore[attr-defined]
    assert job["opponent_ids"] is None  # as before: the preset is named by its pod
    assert job["seed_plan"]["player_count"] == 4  # type: ignore[index]
    assert job["tested_seats"] == [0, 1, 2, 3]
    assert job["estimate"]["duration_known"] is True  # type: ignore[index]


def test_a_series_started_by_manager_with_the_switch_plays_five_seats(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The existing opt-in (``allow_unreleased_seats``) reaches the opponents' deck files too."""
    client = lab["client"]
    revs = lab["revs"]
    assert isinstance(client, TestClient) and isinstance(revs, dict)
    store = StudioStore.open(Path(str(lab["folder"])))
    try:
        job = paired_series.paired_series_manager.start_series(
            store,
            Path(str(lab["folder"])),
            base_revision_id=revs["base"],
            variant_revision_id=revs["variant"],
            pod="precon",
            table_size=5,
            budget_pairs=25,
            look_every_pairs=100,
            allow_unreleased_seats=True,
        )
        assert job.tested_seats == [0, 1, 2, 3, 4] and len(job.seeds) == 5
    finally:
        store.close()
    done = _finished(lab, job.series_id)
    assert done["seed_plan"]["player_count"] == 5  # type: ignore[index]


def _stored_locked_table_series(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch, seats: int
) -> str:
    """A series of ``seats`` seats with two Studio deck states among its opponents, started with
    the lock lifted locally, then marked interrupted so that it can be resumed."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    precons = list(launch.pod_opponent_ids("precon", seats - 1))[: seats - 3]
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    res = _post(
        lab,
        table_size=seats,
        budget_pairs=seats * seats,
        opponent_ids=[revs["base"], revs["variant"], *precons],
    )
    assert res.status_code == 200, res.text  # type: ignore[attr-defined]
    series_id = str(res.json()["series_id"])  # type: ignore[attr-defined]
    _finished(lab, series_id)
    path = Path(str(lab["folder"])) / "games" / f"{series_id}.paired.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["seed_plan"]["player_count"] == seats and len(raw["opponent_ids"]) == seats - 1
    raw["status"] = "interrupted"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 4)  # the lock as shipped
    return series_id


@pytest.mark.parametrize("seats", [5, 6])
def test_resume_refuses_a_stored_five_or_six_seat_table_and_plays_nothing(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch, seats: int
) -> None:
    """The review of #1708: a resume read the table size from the stored opponents and never
    asked the lock. Studio deck states among the opponents slipped past the precon resolver."""
    series_id = _stored_locked_table_series(lab, monkeypatch, seats)
    calls = lab["calls"]
    assert isinstance(calls, list)
    played = len(calls)
    client = lab["client"]
    assert isinstance(client, TestClient)
    res = client.post(f"/api/simulations/paired/{series_id}/resume", headers=HEADERS)
    assert res.status_code == 422, res.text
    assert f"tables of {seats} seats are locked" in res.json()["detail"]  # as on a start
    with pytest.raises(ValueError, match=f"tables of {seats} seats are locked"):
        paired_series.paired_series_manager.resume_series(
            Path(str(lab["folder"])),
            series_id,
            play_override=lambda *a, **k: {},  # type: ignore[arg-type,return-value]
        )
    assert len(calls) == played  # no game was asked for
    path = Path(str(lab["folder"])) / "games" / f"{series_id}.paired.json"
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "interrupted"


@pytest.mark.parametrize("seats", [5, 6])
def test_resume_of_a_stored_five_or_six_seat_table_runs_with_the_lock_lifted_locally(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch, seats: int
) -> None:
    series_id = _stored_locked_table_series(lab, monkeypatch, seats)
    revs = lab["revs"]
    player = lab["player"]
    assert isinstance(revs, dict) and callable(player)
    base = str(revs["base"]).split("@", 1)[0]
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)  # in memory, this test only
    job = paired_series.paired_series_manager.resume_series(
        Path(str(lab["folder"])),
        series_id,
        play_override=player(seats, f"{base}--base", f"{base}--variant"),
    )
    assert len(job.opponents) == seats - 1
    done = _finished(lab, series_id)
    assert done["seed_plan"]["player_count"] == seats  # type: ignore[index]


@pytest.mark.parametrize(("seats", "released"), [(4, True), (5, False), (6, False)])
def test_the_plan_route_plans_a_locked_table_and_says_it_starts_nothing(
    lab: dict[str, object], seats: int, released: bool
) -> None:
    client = lab["client"]
    assert isinstance(client, TestClient)
    block = seats * seats
    res = client.get(
        f"/api/simulations/paired-plan?budget_pairs={block}&table_size={seats}", headers=HEADERS
    )
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan["assumptions"]["seats_per_seed"] == seats  # the table size reaches the plan
    assert plan["assumptions"]["degrees_of_freedom"] == seats - 1
    table = plan["table"]
    assert table["table_size"] == seats and table["tested_seats"] == list(range(seats))
    assert table["rotation_complete"] is True and table["pairs_per_block"] == block
    assert table["released"] is released and table["max_released_seats"] == 4
    if released:
        assert table["locked_text"] is None
    else:
        assert "nicht freigegeben" in table["locked_text"]
        assert "Das Studio startet 2 bis 4 Sitze" in table["locked_text"]
    effort = table["effort"]
    assert effort["max_games"] == 2 * block and effort["duration_known"] is released
    assert (effort["minimum_minutes"] is not None) is released
    assert "planning" not in effort
    # a fixed seat plays one seat per seed
    fixed = client.get(
        f"/api/simulations/paired-plan?budget_pairs=10&table_size={seats}&rotate_seats=false",
        headers=HEADERS,
    ).json()
    assert fixed["assumptions"]["seats_per_seed"] == 1 and fixed["table"]["tested_seats"] == [0]
    # without a table size the plan is the old one
    old = client.get("/api/simulations/paired-plan?budget_pairs=40", headers=HEADERS).json()
    assert "table" not in old and old["assumptions"]["seats_per_seed"] == 4
    assert (
        client.get(
            "/api/simulations/paired-plan?budget_pairs=10&table_size=7", headers=HEADERS
        ).status_code
        == 422
    )


@pytest.mark.parametrize("seats", [2, 4, 5, 6])
def test_the_plan_route_names_the_opponents_of_the_pod_for_the_table(
    lab: dict[str, object], seats: int
) -> None:
    client = lab["client"]
    assert isinstance(client, TestClient)
    res = client.get(
        f"/api/simulations/paired-plan?budget_pairs=25&table_size={seats}&pod=precon",
        headers=HEADERS,
    )
    assert res.status_code == 200, res.text
    opponents = res.json()["table"]["opponent_ids"]
    assert opponents == list(launch.pod_opponent_ids("precon", seats - 1))
    assert len(opponents) == seats - 1 and len(set(opponents)) == seats - 1
    # without a pod the plan names no opponents (nothing invented)
    plain = client.get(
        f"/api/simulations/paired-plan?budget_pairs=25&table_size={seats}", headers=HEADERS
    ).json()
    assert "opponent_ids" not in plain["table"]


def test_the_plan_route_pod_errors_are_a_422_with_the_reason(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = lab["client"]
    assert isinstance(client, TestClient)
    unknown = client.get(
        "/api/simulations/paired-plan?budget_pairs=25&table_size=5&pod=no-such-pod",
        headers=HEADERS,
    )
    assert unknown.status_code == 422 and "Unbekannter Gegnertisch" in unknown.text
    no_size = client.get("/api/simulations/paired-plan?budget_pairs=25&pod=precon", headers=HEADERS)
    assert no_size.status_code == 422 and "table_size" in no_size.text
    # too few decks in the pod: honest error, no fill-up
    monkeypatch.setattr(launch, "POD_PRESET_EXTRA_OPPONENTS", {})
    short = client.get(
        "/api/simulations/paired-plan?budget_pairs=25&table_size=5&pod=precon", headers=HEADERS
    )
    assert short.status_code == 422
    assert "nennt nur 3 Decks" in short.text and "nichts aufgefüllt" in short.text
    ok = client.get(
        "/api/simulations/paired-plan?budget_pairs=16&table_size=4&pod=precon", headers=HEADERS
    )
    assert ok.status_code == 200 and len(ok.json()["table"]["opponent_ids"]) == 3


def test_the_plan_route_reads_the_lock_at_call_time(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = lab["client"]
    assert isinstance(client, TestClient)
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    table = client.get(
        "/api/simulations/paired-plan?budget_pairs=25&table_size=5", headers=HEADERS
    ).json()["table"]
    assert table["released"] is True and table["max_released_seats"] == 6


# -- TableSpec carries the seat count; an experiment plans the whole rotation -----------------


def test_table_spec_carries_five_and_six_seats_only_behind_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opponents = list(launch.pod_opponent_ids("precon", 5))
    for seats in (5, 6):
        with pytest.raises(ValidationError, match="locked"):
            TableSpec(seats=seats, opponents=opponents[: seats - 1])
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    for seats in (5, 6):
        spec = TableSpec(seats=seats, opponents=opponents[: seats - 1])
        assert spec.tested_seats() == list(range(seats))
        assert spec.canonical()["seats"] == seats
    with pytest.raises(ValidationError, match="braucht 5 Gegner"):
        TableSpec(seats=6, opponents=opponents[:4])
    with pytest.raises(ValidationError):
        TableSpec(seats=7, opponents=opponents)


@pytest.mark.parametrize("seats", [5, 6])
def test_an_experiment_plan_at_five_and_six_seats_plans_the_rotation_and_starts_the_series(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch, seats: int
) -> None:
    client = lab["client"]
    revs = lab["revs"]
    assert isinstance(client, TestClient) and isinstance(revs, dict)
    plan = {
        "schema": "studio-experiment-plan-1",
        "question": "38 statt 40 Wälder",
        "question_kind": "axis",
        "deck_id": "chulane-b2",
        "base": {"revision_id": revs["base"]},
        "variants": [{"revision_id": revs["variant"]}],
        "table": {"seats": seats, "opponents": list(launch.pod_opponent_ids("precon", seats - 1))},
        "purpose": "exploration",
        "budget_pairs": seats * seats,
        "look_every_pairs": 100,
        "first_seed": 300,
    }
    locked = client.post("/api/experiments", headers=HEADERS, json={"plan": plan})
    assert locked.status_code == 422 and "locked" in locked.text  # the lock holds
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": plan})
    assert res.status_code == 200, res.text
    started = res.json()
    assert started["tested_seats"] == list(range(seats))
    assert started["seeds"]["count"] == seats and started["seeds"]["last"] == 300 + seats - 1
    assert started["seeds"]["starting_seat_rule"] == "seed % seats"
    job = _finished(lab, started["series_id"])
    assert job["seed_plan"]["player_count"] == seats  # type: ignore[index]
    assert job["tested_seats"] == list(range(seats))
    assert job["experiment"]["plan_sha"] == started["plan_sha"]  # type: ignore[index]
    assert len(lab["calls"]) == 2 * seats * seats  # type: ignore[arg-type]


# -- results: the table size is its own stratum -----------------------------------------------


def test_five_and_six_seat_games_of_one_stand_land_in_their_own_strata(tmp_path: Path) -> None:
    """Acceptance #1702 item 5: 4-, 5- and 6-seat logs of one deck state give three strata,
    never one sum (the layer exists since #1693/#1700; this holds it for the locked sizes)."""
    games = tmp_path / "games"
    for size in (4, 5, 6):
        for n in range(size):  # 4, 5 and 6 games: every stratum has its own n
            _write_log(
                games,
                f"t{size}-{n}",
                _simple_frames(["Sol Ring"] if n == 0 else ["Forest"]),
                winners=(0,) if n % 2 == 0 else (1,),
                seed=size * 10 + n,
                extra_seats=_seats(size - 2),
            )
    table = outcomes_for_folder(games, deck_id=DECK, min_exposed=1)
    assert table["strata"] == 3
    by_size = {s["table_size"]: s for s in table["stands"]}
    assert set(by_size) == {4, 5, 6}
    assert {k: v["games_total"] for k, v in by_size.items()} == {4: 4, 5: 5, 6: 6}
    assert all(s["deck_hash"] == _hash(DECK) for s in table["stands"])
    assert {k: len(v["pods"][0]["opponents"]) for k, v in by_size.items()} == {4: 3, 5: 4, 6: 5}
    assert table["status"] == "NOT_POOLED" and table["cards"] == []
    assert table["pooling"].get("differing_axis") == "table_size"
    assert table["games_total"] == 15


@pytest.mark.parametrize("mixed", [False, True], ids=["precons", "precons-and-deck-state"])
def test_a_five_seat_series_started_with_the_switch_does_not_resume_under_the_lock(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch, mixed: bool
) -> None:
    """Review #1708 (P2): a five-seat series started with the switch and then interrupted is not
    resumed while the lock is 4, also when one opponent is a Studio deck state (the precons alone
    are only three, the table is five): the whole table is checked, before the split."""
    client = lab["client"]
    revs = lab["revs"]
    folder = Path(str(lab["folder"]))
    assert isinstance(client, TestClient) and isinstance(revs, dict)
    opponents = list(launch.pod_opponent_ids("precon", 4))
    if mixed:
        res = client.post(
            "/api/decks/other-b2/revisions",
            headers=HEADERS,
            json={"cards": _cards(45), "note": "opp", "branch": "main"},
        )
        assert res.status_code == 200, res.text
        opponents = [*opponents[:3], res.json()["revision_id"]]
    store = StudioStore.open(folder)
    try:
        job = paired_series.paired_series_manager.start_series(
            store,
            folder,
            base_revision_id=revs["base"],
            variant_revision_id=revs["variant"],
            pod="precon",
            opponent_ids=opponents,
            budget_pairs=25,
            look_every_pairs=100,
            allow_unreleased_seats=True,
        )
    finally:
        store.close()
    assert job.tested_seats == [0, 1, 2, 3, 4]
    _finished(lab, job.series_id)
    path = folder / "games" / f"{job.series_id}.paired.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["status"] = "cancelled"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert launch.MAX_RELEASED_SEATS == 4
    with pytest.raises(ValueError, match="tables of 5 seats are locked"):
        paired_series.paired_series_manager.resume_series(
            folder,
            job.series_id,
            play_override=lambda *_a: {"exposure": None, "failure_class": None},
        )
