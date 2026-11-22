"""SIMULATE at seven and eight seats (#1672, register entry E17).

The Owner instructed on 2026-11-22: "ja kümmer dich drum, dass es halt geht und führe es auch ein
für die Simulationen" (#1672, comment 7071394382). Seven and eight seats are released for
simulations only (``launch.MAX_RELEASED_SEATS`` = 8); PLAY stays at six
(``launch.MAX_RELEASED_PLAY_SEATS``), the Partie page shows at most six seats
(``launch.MAX_PARTIE_SEATS``), the series pool stays refused above four seats (no wall-clock
limit), the replay tape stays at five seats. Both lock states stay tested: the shipped eight and
the lock set back to six in memory (the rollback one-liner). The bridge is a test bridge
(``play_override``), no real engine ran here: NOT_RUN.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules import failure_privacy
from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    XmageFullGameRunner,
    smoke_progress_contract,
)
from commander_lab.engine.rules.full_game_comparison import DeckComparisonSpec
from commander_lab.engine.rules.full_game_pilot.state import _PolicyState
from commander_lab.semantic_replay.tape import TapeGameManifest
from commander_lab.studio import deck_series, launch, maturity, number_contract, paired_series
from commander_lab.studio import play as studio_play
from commander_lab.studio.table_spec import (
    GAME_WALL_LIMIT_SECONDS,
    TableSpec,
    game_wall_limit_seconds,
)
from commander_lab.studio.web import PlayConcedeBody, create_app
from tests.unit.test_seats56_evaluation import _pods, _raw_series
from tests.unit.test_seats_5_6_simulate_1702 import (  # noqa: F401  (``lab`` is a fixture)
    HEADERS,
    _finished,
    _post,
    lab,
)
from tests.unit.test_ws223_cardinality_regression import (
    XMAGE_COMMIT,
    _binding,
    _handshake_lane,
    _scenario,
)

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src/commander_lab/studio/static"
SEVEN_EIGHT = (7, 8)
PODS = tuple(launch.POD_PRESETS)


# -- the locks: SIMULATE eight, PLAY six, the Partie page six ----------------------------------


def test_the_shipped_values_release_seven_and_eight_seats_for_simulate_only() -> None:
    assert (launch.MIN_SEATS, launch.MAX_SEATS) == (2, 8)
    assert launch.MAX_RELEASED_SEATS == 8
    assert launch.MAX_RELEASED_PLAY_SEATS == 6
    assert launch.MAX_PARTIE_SEATS == 6
    for seats in SEVEN_EIGHT:
        assert launch.validate_released_seat_count(seats - 1) == seats
        with pytest.raises(ValueError, match=f"tables of {seats} seats are locked"):
            launch.validate_released_seat_count(seats - 1, play=True)
    with pytest.raises(ValueError, match="1 to 7 opponents"):
        launch.validate_released_seat_count(8, allow_unreleased_seats=True)


@pytest.mark.parametrize("seats", SEVEN_EIGHT)
def test_setting_the_simulate_lock_back_to_six_takes_back_seven_and_eight_everywhere(
    monkeypatch: pytest.MonkeyPatch, seats: int
) -> None:
    """The rollback is one line (``MAX_RELEASED_SEATS = 6``); every SIMULATE path follows it."""
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    opponents = list(launch.pod_opponent_ids("precon", seats - 1))
    with pytest.raises(ValueError, match=f"tables of {seats} seats are locked"):
        launch.validate_released_seat_count(seats - 1)
    with pytest.raises(ValueError, match=f"tables of {seats} seats are locked"):
        launch.resolve_opponent_paths("precon", opponents)
    with pytest.raises(ValidationError, match="locked"):
        TableSpec(seats=seats, opponents=opponents)
    plan = paired_series.table_plan(seats, seats * seats)
    table = plan["table"]
    assert isinstance(table, dict)
    assert table["released"] is False and table["max_released_seats"] == 6
    assert "Das Studio startet 2 bis 6 Sitze" in str(table["locked_text"])
    # the measurement switch still opens it, up to what the engine seats
    assert launch.validate_released_seat_count(seats - 1, allow_unreleased_seats=True) == seats
    # six seats are untouched by the rollback
    assert launch.validate_released_seat_count(5) == 6


def test_the_partie_route_shows_at_most_six_seats_whatever_the_simulate_lock_says(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path), headers=HEADERS)
    ids = [f"precon-{n}" for n in range(6)]  # seven seats
    for body in (
        {"revision_id": "r", "opponent_ids": ids, "seed": 1},
        {"revision_id": "r", "opponent_ids": ids, "seed": 1, "human_seats": [0]},
    ):
        refused = client.post("/api/games", json=body)
        assert refused.status_code == 422, refused.text
    # one level down: a watched AI game of seven seats is refused before any file is written
    with pytest.raises(ValueError, match="the Partie page shows 2 to 6 seats"):
        launch.prepare_table_deck_paths(
            None,  # type: ignore[arg-type]
            tmp_path,
            revision_id="r",
            opponent_ids=ids,
            seed=1,
        )
    assert not (tmp_path / "games").exists()
    # a human seat beyond the sixth does not exist on the page
    with pytest.raises(ValidationError):
        PlayConcedeBody(seat=6)


def test_the_series_dialog_offers_eight_seats_and_its_lock_line_follows_the_server() -> None:
    js = (STATIC / "paired.js").read_text(encoding="utf-8")
    assert f"const PAIRED_MAX_SEATS = {launch.MAX_SEATS};" in js
    assert f"const PAIRED_RELEASED_SEATS = {launch.MAX_RELEASED_SEATS};" in js
    partie = (STATIC / "partie.js").read_text(encoding="utf-8")
    assert "const OPPONENT_COUNTS_AI = [1, 2, 3, 4, 5];" in partie  # PLAY page stays at six
    assert "const OPPONENT_COUNTS_PLAY = [1, 2, 3, 4, 5];" in partie


# -- the engine layer: 2..8, nine refused ------------------------------------------------------


def _future(player_count: int) -> FutureXmageScenario:
    return FutureXmageScenario(
        candidate_id="s78",
        deck_hash="a" * 64,
        opponent_deck_ids=tuple(f"o{n}" for n in range(1, player_count)),
        player_count=player_count,
        seat=player_count,
        scenario_id=f"s78-{player_count}",
        seed=7,
        xmage_commit="b" * 40,
        bridge_version="t",
        pilot_identity="t",
        pilot_version="t",
        decision_policy_version="t",
    )


def test_every_engine_bound_seats_eight_and_refuses_nine() -> None:
    assert (XmageFullGameRunner.MIN_PLAYERS, XmageFullGameRunner.MAX_PLAYERS) == (2, 8)
    for seats in SEVEN_EIGHT:
        assert _future(seats).player_count == seats
        assert _binding(seats, f"fixture-{seats}").seat == seats
    with pytest.raises(ValidationError):
        _future(9)
    with pytest.raises(ValidationError):
        _binding(9, "fixture-9")
    for seats, invalid in ((7, False), (8, False), (9, True)):
        contract = smoke_progress_contract((), player_count=seats, through_turn=seats)
        assert ("invalid player count" in contract["violations"]) is invalid, seats
    with pytest.raises(ValueError, match="two to eight pilot bindings"):
        _PolicyState(tuple(object() for _ in range(9)), 1)  # type: ignore[arg-type]
    # the public message list follows the message (never a raw private text)
    assert "full-game policy requires two to eight pilot bindings" in (
        failure_privacy._PUBLIC_CONFIGURATION_ERRORS
    )
    with pytest.raises(ValueError, match="two to eight seats"):
        studio_play.load_decks([Path("x.json")] * 9)
    fields = DeckComparisonSpec.model_fields["opponents"].metadata
    assert any(getattr(m, "max_length", None) == 7 for m in fields)


def test_a_bridge_built_before_1672_still_runs_six_and_refuses_seven() -> None:
    """The handshake accepts a bridge that announces 6 (the jar before #1672) for tables of up to
    six seats, so the Owner's Studio keeps working until the jar is rebuilt; a table above the
    bridge's maximum is refused (fail-closed). Any other announced maximum is refused."""
    provider = {"engine": "xmage", "engine_commit": XMAGE_COMMIT}
    XmageFullGameRunner._validate_handshake(_scenario(6), provider, _handshake_lane(2, 6))
    XmageFullGameRunner._validate_handshake(_scenario(6), provider, _handshake_lane(2, 8))
    seven = _scenario(6).model_copy(update={"player_count": 7})
    eight = _scenario(6).model_copy(update={"player_count": 8})
    XmageFullGameRunner._validate_handshake(eight, provider, _handshake_lane(2, 8))
    for scenario in (seven, eight):
        with pytest.raises(FullGameConformanceError):  # the message is redacted (private)
            XmageFullGameRunner._validate_handshake(scenario, provider, _handshake_lane(2, 6))
    for announced in (5, 7, 9, 10):
        with pytest.raises(FullGameConformanceError):
            XmageFullGameRunner._validate_handshake(
                _scenario(4), provider, _handshake_lane(2, announced)
            )


def test_the_bridge_seats_eight_and_the_midgame_lane_keeps_six() -> None:
    session = (
        ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java"
    ).read_text(encoding="utf-8")
    assert "static final int MAX_PLAYERS = 8;" in session
    assert "static final int MIDGAME_MAX_PLAYERS = 6;" in session
    midgame = (
        ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageMidgameJsonlBridge.java"
    ).read_text(encoding="utf-8")
    assert '"max_players", XmageFullGameSession.MAX_PLAYERS' not in midgame
    assert midgame.count('"max_players", XmageFullGameSession.MIDGAME_MAX_PLAYERS') == 2
    # every mid-game entry builds its scaffolding through the guard before any session exists
    scaffolding = midgame.index("String deckTag, XmageLosslessHiddenPlan lossless) {\n")
    assert midgame[scaffolding:].split("\n")[1].strip() == (
        "requireMidgamePlayerCount(plan.playerCount());"
    )
    assert "playerCount > XmageFullGameSession.MIDGAME_MAX_PLAYERS" in midgame
    restoration = (
        ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java"
    ).read_text(encoding="utf-8")
    # a restoration plan on the full-game lane follows the full-game maximum (F5 at 7/8 uses it)
    assert "validated.playerCount() > XmageFullGameSession.MAX_PLAYERS" in restoration


# -- what stays: replay tape five, series pool four, conformance table six ---------------------


def test_the_replay_tape_stays_at_five_seats_and_the_pool_stays_refused_above_four() -> None:
    schema = TapeGameManifest.model_json_schema()["properties"]["player_count"]
    assert schema["maximum"] == 5
    assert set(GAME_WALL_LIMIT_SECONDS) == {2, 3, 4}  # no wall-clock limit, no pool, at 5 to 8
    for seats in (5, 6, *SEVEN_EIGHT):
        with pytest.raises(ValueError, match=f"keine Wandzeit-Grenze für {seats} Sitze"):
            game_wall_limit_seconds(seats)


def test_the_conformance_table_is_not_widened() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "conf1672", ROOT / "scripts" / "run_external_full_game_conformance.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SUPPORTED_PLAYER_COUNTS == (2, 3, 4, 5, 6)  # 7/8 conformance: NOT_RUN


# -- pod presets: seven distinct existing opponents --------------------------------------------


@pytest.mark.parametrize("pod", PODS)
def test_pod_presets_name_seven_distinct_existing_opponents(pod: str) -> None:
    by_id = {deck_id for deck_id, *_rest in launch._precons()}
    seven = launch.pod_opponent_ids(pod, 7)
    assert len(seven) == len(set(seven)) == 7
    assert set(seven) - {"kaervek/current", "opponent/hosts-of-mordor-precon"} <= by_id
    assert seven[:5] == launch.pod_opponent_ids(pod, 5)  # the six-seat table is a prefix
    assert launch.pod_opponent_ids(pod, 6) == seven[:6]


def test_a_preset_cut_short_is_an_honest_error_at_seven_or_eight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    short = {k: v[:2] for k, v in launch.POD_PRESET_EXTRA_OPPONENTS.items()}
    monkeypatch.setattr(launch, "POD_PRESET_EXTRA_OPPONENTS", short)
    assert len(launch.pod_opponent_ids("precon", 5)) == 5
    for opponents in (6, 7):
        with pytest.raises(ValueError, match="nichts aufgefüllt"):
            launch.pod_opponent_ids("precon", opponents)


# -- the plan: base win rate 1/N, Wilson +-20 %, duration UNKNOWN with a warning --------------


@pytest.mark.parametrize(("seats", "pct"), [(7, 14.3), (8, 12.5)])
def test_the_plan_uses_the_base_win_rate_one_over_n(seats: int, pct: float) -> None:
    base = paired_series.planning_baseline(seats)
    assert base["applies_to_plan"] is True and base["win_rate_pct"] == pct
    assert base["half_width_pp"] == round(100.0 / seats * 0.2, 2)  # +-20 % relative
    assert base["games_needed_wilson"] == paired_series.wilson_games_needed(1.0 / seats)
    sd = paired_series.planning_pair_sd(seats)
    p = 1.0 / seats
    expected = round(0.63 * (2 * p * (1 - p)) ** 0.5 / (2 * 0.25 * 0.75) ** 0.5, 4)
    assert sd == expected and sd < paired_series.planning_pair_sd(6)
    plan = paired_series.planned_detectable_difference_pp(seats * seats, seats, seats)
    assert plan["assumptions"]["pair_sd"] == sd  # type: ignore[index]
    rotation = paired_series.rotation_plan(seats, seats * seats)
    assert rotation["rotation_complete"] is True and rotation["pairs_per_block"] == seats * seats


@pytest.mark.parametrize("seats", SEVEN_EIGHT)
def test_the_duration_at_seven_and_eight_is_unknown_and_names_the_measured_single_game(
    seats: int,
) -> None:
    est = paired_series.estimate_series_duration(seats * seats, table_size=seats)
    assert est["duration_known"] is False and est["duration_kind"] == "unknown"
    for key in ("minimum_seconds", "minimum_minutes", "estimated_seconds", "estimated_minutes"):
        assert est[key] is None, key  # unknown is never 0
    assert est["wall_ratio_vs_four_seats"] is None and est["pool_reference_part_b"] is None
    basis = str(est["basis"])
    assert basis.startswith("unbekannt (UNKNOWN)")
    ref = paired_series.SINGLE_GAME_REFERENCE_7_8[seats]
    median = f"{ref['wall_seconds_median']:.1f}".replace(".", ",")
    assert f"Hinweis {seats} Sitze" in basis and f"Median {median} s" in basis
    assert (
        f"{ref['rss_mib_median']} MiB" in basis and f"höchstens {ref['rss_mib_max']} MiB" in basis
    )
    assert "n = 6/6 Partien" in basis and "SIMULATED_RESULT" in basis
    assert "mehreren Partien je JVM ist unbekannt (n = 0)" in basis and "wenige Worker" in basis
    single = est["single_game_reference"]
    assert isinstance(single, dict)
    assert single["games"] == single["planned"] == 6
    assert single["multi_game_jvm_memory_known"] is False
    for seats_other in (4, 5, 6):
        other = paired_series.estimate_series_duration(10, table_size=seats_other)
        assert other["single_game_reference"] is None
        assert "Hinweis" not in str(other["basis"])


def test_the_page_mirrors_the_single_game_reference_and_shows_the_warning() -> None:
    js = (STATIC / "paired.js").read_text(encoding="utf-8")
    declared = re.search(r"const PAIRED_SINGLE_GAME_REFERENCE_7_8 = (\{.*\});", js)
    assert declared is not None
    mirror = json.loads(re.sub(r"(\d+):", r'"\1":', declared.group(1)))
    for seats, ref in paired_series.SINGLE_GAME_REFERENCE_7_8.items():
        low, high = ref["wall_seconds_range"]  # type: ignore[misc]
        assert mirror[str(seats)] == [
            ref["wall_seconds_median"],
            low,
            high,
            ref["rss_mib_median"],
            ref["rss_mib_max"],
            ref["decisions_median"],
            ref["games"],
            ref["planned"],
        ]
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")  # NOT_RUN, never PASS
    harness = (
        "const fs = require('fs');"
        "const StudioUI = { num: (v, d = 0) => Number(v).toLocaleString('de-DE', "
        "{ minimumFractionDigits: d, maximumFractionDigits: d }) };"
        "const src = fs.readFileSync('paired.js', 'utf8');"
        "const p = new Function('document', 'StudioUI', src + ';return {estimatePairedText};')"
        "({}, StudioUI);"
        "console.log(JSON.stringify({ eight: p.estimatePairedText(64, 4, 8),"
        " seven: p.estimatePairedText(49, 4, 7), six: p.estimatePairedText(36, 4, 6) }));"
    )
    done = subprocess.run(
        [node, "-e", harness], capture_output=True, text=True, check=True, cwd=STATIC, timeout=60
    )
    out = json.loads(done.stdout)
    assert out["eight"].startswith("Dauer: unbekannt (UNKNOWN)")
    assert "Hinweis 8 Sitze" in out["eight"] and "98,8 s" in out["eight"]
    assert "945 MiB" in out["eight"] and "n = 6/6 Partien" in out["eight"]
    assert "Hinweis 7 Sitze" in out["seven"] and "1.343 MiB" in out["seven"]
    assert "Hinweis" not in out["six"] and "mindestens" not in out["eight"]


# -- the series: a 7/8-seat series plays whole blocks under the shipped lock -------------------


@pytest.mark.parametrize("seats", SEVEN_EIGHT)
def test_a_seven_or_eight_seat_series_plays_whole_blocks_under_the_shipped_lock(
    lab: dict[str, object],  # noqa: F811
    seats: int,
) -> None:
    block = seats * seats
    res = _post(lab, table_size=seats, budget_pairs=block)
    assert res.status_code == 200, res.text  # type: ignore[attr-defined]
    job = _finished(lab, res.json()["series_id"])  # type: ignore[attr-defined]
    assert job["opponent_ids"] == list(launch.pod_opponent_ids("precon", seats - 1))
    assert job["seed_plan"]["player_count"] == seats  # type: ignore[index]
    assert job["tested_seats"] == list(range(seats))
    calls = lab["calls"]
    assert isinstance(calls, list) and len(calls) == 2 * block
    for arm in ("base", "variant"):
        cells = Counter((seed % seats, seat) for a, seed, seat in calls if a == arm)
        assert set(cells) == {(s, t) for s in range(seats) for t in range(seats)}
    result = job["result"]
    assert isinstance(result, dict) and result["data_class"] == "SIMULATED_RESULT"
    assert result["pairs_completed"] == block
    estimate = job["estimate"]
    assert isinstance(estimate, dict)
    assert estimate["duration_kind"] == "unknown" and estimate["minimum_minutes"] is None
    # the stored series proves its table from the plan and the games
    assert deck_series.series_table_check(job) == (seats, "consistent")


@pytest.mark.parametrize("seats", SEVEN_EIGHT)
def test_with_the_lock_at_six_a_seven_or_eight_seat_series_is_refused_and_writes_nothing(
    lab: dict[str, object],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    seats: int,
) -> None:
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    res = _post(lab, table_size=seats, budget_pairs=seats * seats)
    assert res.status_code == 422, res.text  # type: ignore[attr-defined]
    assert f"tables of {seats} seats are locked" in res.json()["detail"]  # type: ignore[attr-defined]
    assert lab["calls"] == []
    assert not list((Path(str(lab["folder"])) / "games").glob("*.paired.json"))


def test_the_plan_route_plans_eight_seats_and_refuses_nine(
    lab: dict[str, object],  # noqa: F811
) -> None:
    client = lab["client"]
    assert isinstance(client, TestClient)
    res = client.get(
        "/api/simulations/paired-plan?budget_pairs=64&table_size=8&pod=precon", headers=HEADERS
    )
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan["table"]["released"] is True and plan["table"]["table_size"] == 8
    assert plan["table"]["opponent_ids"] == list(launch.pod_opponent_ids("precon", 7))
    assert plan["baseline"]["win_rate_pct"] == 12.5
    assert plan["table"]["effort"]["duration_known"] is False
    for query in ("table_size=9", "seats_per_seed=9"):
        bad = client.get(f"/api/simulations/paired-plan?budget_pairs=10&{query}", headers=HEADERS)
        assert bad.status_code == 422, query


# -- evidence: "Tisch mit 7/8 Sitzen", cohorts never mixed ------------------------------------


def test_seven_and_eight_seat_series_are_their_own_cohorts_and_name_their_table() -> None:
    series: list[dict[str, Any]] = []
    for sid, seats in (("s6", 6), ("s7", 7), ("s8", 8)):
        raw = _raw_series(series_id=sid, seed_plan={"player_count": seats})
        entry = deck_series._entry(raw, "completed")
        assert entry["table_size"] == seats
        entry["difference_pp"] = 4.0
        series.append(entry)
    figures = {
        str(z["id"]).split(".")[1]: z for z in number_contract.series_zahlen({"series": series}, {})
    }
    assert figures["s7"]["kohorte"] == "Tisch precon · Tisch mit 7 Sitzen"
    assert figures["s8"]["kohorte"] == "Tisch precon · Tisch mit 8 Sitzen"
    assert len({str(z["kohorte"]) for z in figures.values()}) == 3  # never one sum
    assert maturity.table_fields(8, "consistent") == {
        "tisch_sitze": 8,
        "tisch_text": "Tisch mit 8 Sitzen (Zufallsbasis 1/8)",
    }
    assert maturity.table_fields(7, "unobserved")["tisch_sitze"] is None
    # games of eight seats prove a table of eight; nine seats are no seatable table
    for seats in SEVEN_EIGHT:
        raw = {**_raw_series(result={**_pods(seats), "pairs_completed": 25}), "seed_plan": None}
        assert deck_series.series_table_check(raw) == (seats, "consistent")
    raw9 = {**_raw_series(result={**_pods(9), "pairs_completed": 25}), "seed_plan": None}
    assert deck_series.series_table_check(raw9) == (None, "unreadable")


@pytest.mark.parametrize("seats", SEVEN_EIGHT)
def test_an_experiment_plan_at_seven_and_eight_seats_follows_the_simulate_lock(
    lab: dict[str, object],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    seats: int,
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
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)  # the rollback, in memory
    locked = client.post("/api/experiments", headers=HEADERS, json={"plan": plan})
    assert locked.status_code == 422 and "locked" in locked.text
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 8)  # E17
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": plan})
    assert res.status_code == 200, res.text
    started = res.json()
    assert started["tested_seats"] == list(range(seats))
    assert started["seeds"]["count"] == seats
    job = _finished(lab, started["series_id"])
    assert job["seed_plan"]["player_count"] == seats  # type: ignore[index]
    assert len(lab["calls"]) == 2 * seats * seats  # type: ignore[arg-type]


def test_the_batch_route_follows_the_simulate_lock_at_seven_and_eight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the lock at six (the rollback) a batch of seven or eight seats is refused before any
    game; under the shipped lock the refusal is no longer the seat lock (here: unknown decks)."""
    from commander_lab.studio.store import StudioStore
    from tests.unit.test_studio_simulations import _seed_test_deck

    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
    finally:
        store.close()
    client = TestClient(create_app(tmp_path))

    def post(seats: int) -> Any:
        return client.post(
            "/api/simulations/batch",
            headers=HEADERS,
            json={
                "revision_id": rev_id,
                "opponent_ids": [f"precon/d{i}" for i in range(seats - 1)],
                "games_count": 2,
                "base_seed": 100,
            },
        )

    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    for seats in SEVEN_EIGHT:
        res = post(seats)
        assert res.status_code == 422
        assert f"tables of {seats} seats are locked" in res.json()["detail"]
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 8)
    for seats in SEVEN_EIGHT:
        res = post(seats)
        assert "seats are locked" not in res.text
        assert res.status_code in (409, 422), res.text  # unknown decks / no engine, never a game
