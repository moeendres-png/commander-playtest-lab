"""Card outcomes from simulated games: first dealt hand versus not. All data is synthetic."""

from __future__ import annotations

import gzip
import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore
from commander_lab.studio.__main__ import main
from commander_lab.studio.card_outcomes import (
    DATA_CLASS,
    GameExposure,
    SeatExposure,
    aggregate,
    game_exposures,
    load_exposures,
    newcombe_difference,
    outcomes_for_folder,
    ranked,
)
from commander_lab.studio.simulations import wilson_score_interval
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill

COMMIT = "a" * 40
DECK = "deck/a"
OTHER = "deck/b"


def _frame(
    n: int,
    seat: int,
    dc: str,
    *,
    hand: list[str] | None,
    chosen: list[str] | None = None,
    turn: int = 1,
    active: int | None = None,
    extra: dict[int, list[str]] | None = None,
) -> dict[str, object]:
    players: list[dict[str, object]] = []
    for s in (0, 1):
        row: dict[str, object] = {"seat": s, "life": 40}
        if s == seat and hand is not None:
            row["hand"] = hand
        if extra and s in extra:
            row["hand"] = extra[s]
        players.append(row)
    return {
        "kind": "frame",
        "n": n,
        "turn": turn,
        "seat": seat,
        "active_seat": active,
        "decision_class": dc,
        "chosen": chosen or [],
        "players": players,
    }


def _write_log(
    folder: Path,
    game_id: str,
    frames: list[dict[str, object]],
    *,
    winners: Sequence[int] = (0,),
    status: str | None = "finished",
    commit: str = COMMIT,
    seed: int = 1,
    commanders: tuple[str, str] = ("Cmd A", "Cmd B"),
    decks: tuple[str, str] = (DECK, OTHER),
    gz: bool = True,
) -> Path:
    header = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "game_id": game_id,
        "seed": seed,
        "engine_commit": commit,
        "pilot": "Pilot 1.0.0",
        "decision_policy": "policy-1",
        "seats": [
            {"seat": 0, "deck_id": decks[0], "commanders": [commanders[0]]},
            {"seat": 1, "deck_id": decks[1], "commanders": [commanders[1]]},
        ],
    }
    lines: list[dict[str, object]] = [header, *frames]
    if status is not None:
        lines.append({"kind": "result", "status": status, "winner_seats": list(winners)})
    text = "".join(json.dumps(line) + "\n" for line in lines)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (f"{game_id}.jsonl.gz" if gz else f"{game_id}.jsonl")
    if gz:
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


def _simple_frames(hand0: list[str]) -> list[dict[str, object]]:
    return [
        _frame(1, 0, "mulligan", hand=hand0, chosen=["Keep opening hand"]),
        _frame(2, 1, "mulligan", hand=["Other"], chosen=["Keep opening hand"]),
    ]


# --- extraction ------------------------------------------------------------------------


def test_first_hand_is_the_first_mulligan_frame_even_after_a_mulligan(tmp_path: Path) -> None:
    first = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    kept = ["B1", "B2", "B3", "B4", "B5", "B6"]
    frames = [
        _frame(1, 0, "choose_object", hand=[], chosen=["Full Game Seat 1"]),
        _frame(2, 0, "mulligan", hand=first, chosen=["Take mulligan"]),
        _frame(3, 0, "mulligan", hand=kept[:], chosen=["Take mulligan"]),
        _frame(4, 0, "target", hand=kept, chosen=["B6"]),
        _frame(5, 0, "mulligan", hand=kept[:5], chosen=["Keep opening hand"]),
    ]
    path = _write_log(tmp_path, "g1", frames)
    game = game_exposures(path)
    assert game is not None
    seat = game["seats"][0]
    assert seat["first_dealt_hand"] == first  # the empty pre-deal hand is not a hand
    assert seat["mulligans_taken"] == 2
    assert seat["result"] == "win"
    assert game["winner_seats"] == [0]
    assert (game["seed"], game["engine_commit"]) == (1, COMMIT)


def test_hand_of_another_seat_is_never_attributed(tmp_path: Path) -> None:
    frames = [
        _frame(1, 0, "mulligan", hand=["Mine"], chosen=["Keep opening hand"]),
        # the engine would not publish this, but if a frame of seat 1 carried seat 0's row
        # with a hand, it still must not be attributed to seat 0
        _frame(2, 1, "mulligan", hand=["Theirs"], extra={0: ["Leak"]}),
    ]
    game = game_exposures(_write_log(tmp_path, "g1", frames))
    assert game is not None
    assert game["seats"][0]["first_dealt_hand"] == ["Mine"]
    assert "Leak" not in game["seats"][0]["seen_by_own_turn_3"]
    assert game["seats"][1]["first_dealt_hand"] == ["Theirs"]


def test_seen_by_own_turn_3_stops_after_the_third_own_turn(tmp_path: Path) -> None:
    frames = [_frame(1, 0, "mulligan", hand=["H"], chosen=["Keep opening hand"])]
    for n, (turn, active) in enumerate([(1, 0), (2, 1), (3, 0), (5, 0), (7, 0)], start=2):
        frames.append(_frame(n, 0, "priority", hand=[f"T{turn}"], turn=turn, active=active))
    game = game_exposures(_write_log(tmp_path, "g1", frames))
    assert game is not None
    assert game["seats"][0]["seen_by_own_turn_3"] == ["H", "T1", "T2", "T3", "T5"]


def test_unfinished_and_failed_games_are_skipped_not_lost(tmp_path: Path) -> None:
    _write_log(tmp_path, "ok", _simple_frames(["X"]))
    _write_log(tmp_path, "running", _simple_frames(["X"]), status=None)
    _write_log(tmp_path, "failed", _simple_frames(["X"]), status="failed")
    assert game_exposures(tmp_path / "running.jsonl.gz") is None
    assert game_exposures(tmp_path / "failed.jsonl.gz") is None
    report = load_exposures(tmp_path)
    assert [g["game_id"] for g in report["exposures"]] == ["ok"]
    assert report["skipped_with_deck"] == {DECK: 2, OTHER: 2}
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert (table["games_total"], table["games_skipped"]) == (1, 2)
    row = table["cards"][0]
    assert row["games_total"] == 1 and row["wins_in_first_hand"] == 1.0  # no phantom losses


def test_draw_handling_and_result_labels(tmp_path: Path) -> None:
    shared = game_exposures(_write_log(tmp_path, "shared", _simple_frames(["X"]), winners=[0, 1]))
    nobody = game_exposures(_write_log(tmp_path, "nobody", _simple_frames(["X"]), winners=[]))
    lost = game_exposures(_write_log(tmp_path, "lost", _simple_frames(["X"]), winners=[1]))
    assert shared is not None and nobody is not None and lost is not None
    assert [s["result"] for s in shared["seats"]] == ["draw", "draw"]
    assert [s["win_credit"] for s in shared["seats"]] == [0.5, 0.5]
    assert [s["win_credit"] for s in nobody["seats"]] == [0.0, 0.0]
    assert [s["result"] for s in lost["seats"]] == ["loss", "win"]
    table = aggregate([shared, nobody, lost], deck_id=DECK, min_exposed=1)
    assert table["draw_games"] == 2
    row = next(r for r in table["cards"] if r["card"] == "X")
    assert row["games_in_first_hand"] == 3 and row["wins_in_first_hand"] == 0.5


def test_commander_is_excluded_and_copies_count_once(tmp_path: Path) -> None:
    hand = ["Forest", "Forest", "Forest", "Cmd A", "Spell"]
    game = game_exposures(_write_log(tmp_path, "g1", _simple_frames(hand)))
    assert game is not None
    table = aggregate([game], deck_id=DECK, min_exposed=1)
    by_name = {r["card"]: r for r in table["cards"]}
    assert "Cmd A" not in by_name
    assert table["commanders_excluded"] == ["Cmd A"]
    assert by_name["Forest"]["games_in_first_hand"] == 1  # three copies, one exposed game
    assert by_name["Spell"]["games_in_first_hand"] == 1


# --- statistics ------------------------------------------------------------------------


def _seat(seat: int, deck_id: str, hand: list[str], credit: float) -> SeatExposure:
    return {
        "seat": seat,
        "deck_id": deck_id,
        "commanders": [],
        "first_dealt_hand": hand,
        "mulligans_taken": 0,
        "seen_by_own_turn_3": [],
        "result": "win" if credit == 1.0 else "loss",
        "win_credit": credit,
    }


def _synthetic(
    games: list[tuple[list[str], bool]], *, commit: str = COMMIT, pilot: str = "P1"
) -> list[GameExposure]:
    out: list[GameExposure] = []
    for index, (hand, won) in enumerate(games):
        out.append(
            {
                "game_id": f"s{index}",
                "seed": index,
                "engine_commit": commit,
                "pilot": pilot,
                "decision_policy": "policy-1",
                "winner_seats": [0] if won else [1],
                "seats": [
                    _seat(0, DECK, hand, 1.0 if won else 0.0),
                    _seat(1, OTHER, ["Filler"], 0.0 if won else 1.0),
                ],
            }
        )
    return out


def _block(card: str, games: int, wins: int) -> list[tuple[list[str], bool]]:
    return [([card], i < wins) for i in range(games)]


def test_wilson_and_newcombe_match_hand_computed_values() -> None:
    """Hand values: card in 100 games with 60 wins, 100 other games with 40 wins.

    Wilson(p, n, z=1.95996): centre = (p + z^2/2n) / (1 + z^2/n), half-width =
    z * sqrt(p(1-p)/n + z^2/4n^2) / (1 + z^2/n); for 60/100: centre 0.596296, half-width
    0.094291, so (0.5020, 0.6906); for 40/100 mirror (0.3094, 0.4980). Newcombe hybrid score
    for d = p1 - p2 = 0.2: lower = d - sqrt((p1-l1)^2 + (u2-p2)^2) = 0.2 - 0.13859 = 0.0614,
    upper = d + sqrt((u1-p1)^2 + (p2-l2)^2) = 0.2 + 0.12813 = 0.3281.
    """
    games = _block("Card", 100, 60) + _block("Rest", 100, 40)
    table = aggregate(_synthetic(games), deck_id=DECK, min_exposed=100)
    row = next(r for r in table["cards"] if r["card"] == "Card")
    assert row["rate_in"] == pytest.approx(0.6)
    assert row["rate_not"] == pytest.approx(0.4)
    assert row["rate_in_ci95"] == pytest.approx([0.5020, 0.6906], abs=1e-4)
    assert row["rate_not_ci95"] == pytest.approx([0.3094, 0.4980], abs=1e-4)
    assert row["difference_pp"] == pytest.approx(20.0)
    assert row["difference_ci95_pp"] == pytest.approx([6.14, 32.81], abs=0.05)
    assert row["status"] == "MEASURED"
    d, lo, hi = newcombe_difference(
        0.6, wilson_score_interval(60, 100), 0.4, wilson_score_interval(40, 100)
    )
    assert (d, round(lo, 3), round(hi, 3)) == pytest.approx((0.2, 0.0614, 0.3281), abs=5e-4)


def test_insufficient_sample_is_flagged_reported_and_never_ranked() -> None:
    games = _block("Few", 99, 80) + _block("Rest", 300, 100) + _block("Base", 300, 100)
    table = aggregate(_synthetic(games), deck_id=DECK, min_exposed=100)
    few = next(r for r in table["cards"] if r["card"] == "Few")
    assert few["status"] == "INSUFFICIENT_SAMPLE"
    assert few["difference_pp"] is not None and few["difference_ci95_pp"] is not None
    result = ranked(table)
    assert [r["card"] for r in result["ranked"]] == ["Base", "Rest"]
    assert [u["card"] for u in result["unranked"]] == ["Few"]
    assert all(u["reason"] for u in result["unranked"])


def test_ranking_uses_the_lower_bound_not_the_point_estimate() -> None:
    games = _block("A", 100, 65) + _block("B", 400, 240) + _block("Rest", 1000, 400)
    table = aggregate(_synthetic(games), deck_id=DECK, min_exposed=100)
    rows = {r["card"]: r for r in table["cards"]}
    assert (rows["A"]["difference_pp"] or 0) > (rows["B"]["difference_pp"] or 0)
    assert (rows["A"]["difference_ci95_pp"] or [0])[0] < (rows["B"]["difference_ci95_pp"] or [0])[0]
    order = [r["card"] for r in ranked(table)["ranked"]]
    assert order.index("B") < order.index("A")


def test_table_carries_provenance_and_pods() -> None:
    table = aggregate(_synthetic(_block("A", 5, 2)), deck_id=DECK, min_exposed=100)
    assert table["data_class"] == DATA_CLASS == "SIMULATED_RESULT"
    assert "first dealt hand" in table["estimand"]
    assert table["engine_commits"] == [COMMIT] and table["pilots"] == ["P1"]
    assert table["seeds"] == 5
    assert table["pods"] == [{"opponents": [OTHER], "games": 5}]
    assert any("only 5 games" in w for w in table["warnings"])


def test_mixed_engine_commits_or_pilots_are_refused_unless_allowed() -> None:
    mixed = _synthetic(_block("A", 3, 1)) + _synthetic(_block("A", 3, 1), commit="b" * 40)
    with pytest.raises(ValueError, match="mixed engine commits"):
        aggregate(mixed, deck_id=DECK)
    pooled = aggregate(mixed, deck_id=DECK, allow_mixed=True)
    assert len(pooled["engine_commits"]) == 2
    assert any("mixed engine commits" in w for w in pooled["warnings"])
    pilots = _synthetic(_block("A", 3, 1)) + _synthetic(_block("A", 3, 1), pilot="P2")
    with pytest.raises(ValueError, match="mixed pilot versions"):
        aggregate(pilots, deck_id=DECK)


# --- API and CLI -----------------------------------------------------------------------


def test_api_returns_no_games_for_an_empty_folder(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "studio")) as client:
        response = client.get("/api/outcomes", params={"deck_id": "nobody"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NO_GAMES" and body["cards"] == []


def test_owner_marks_do_not_change_the_outcomes_response(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    assert store.path is not None
    folder = store.path.parent
    store.close()
    _write_log(folder / "games", "g1", _simple_frames(["Forest", "Spell"]))
    marker = {"X-Studio": "1"}
    with TestClient(create_app(folder)) as client:
        before = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1}).json()
        mark = {"favorite": True, "excluded": True, "note": "mine"}
        put = client.put("/api/cards/card:project:0007/mark", json=mark, headers=marker)
        assert put.status_code == 200
        after = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1}).json()
    assert before["games_total"] == 1 and before["cards"]
    assert before == after


def test_api_refuses_mixed_commits_with_409(tmp_path: Path) -> None:
    _write_log(tmp_path / "games", "g1", _simple_frames(["X"]))
    _write_log(tmp_path / "games", "g2", _simple_frames(["X"]), commit="b" * 40)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/outcomes", params={"deck_id": DECK}).status_code == 409


def test_command_prints_table_and_writes_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    games = tmp_path / "games"
    for i in range(3):
        _write_log(games, f"g{i}", _simple_frames(["Forest", "Spell"]), seed=i)
    out = tmp_path / "out.json"
    code = main(["card-outcomes", "--deck-id", DECK, "--games-dir", str(games), "--out", str(out)])
    assert code == 0
    text = capsys.readouterr().out
    assert "games 3" in text and "INSUFFICIENT_SAMPLE" in text
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["games_total"] == 3 and written["data_class"] == "SIMULATED_RESULT"
