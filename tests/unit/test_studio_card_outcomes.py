"""Card outcomes from simulated games: first dealt hand versus not. All data is synthetic."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import shutil
import threading
from collections.abc import Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, card_outcomes
from commander_lab.studio.__main__ import main
from commander_lab.studio.card_outcomes import (
    DATA_CLASS,
    GameExposure,
    SeatExposure,
    aggregate,
    format_table,
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
_DEFAULT = object()


def _hash(label: str) -> str:
    """A 64-hex deck state of the fixtures (the header names one per seat since #1657)."""
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


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
        "active_seat": active,
        "seat": seat,
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
    deck_hashes: object = _DEFAULT,
    revisions: tuple[str | None, str | None] = (None, None),
    fingerprint: str | None = None,
) -> Path:
    """One game log. Every seat names a deck state derived from its deck id unless
    ``deck_hashes`` gives others; ``deck_hashes=None`` writes a log of before #1657."""
    hashes: tuple[str | None, str | None] = (
        (_hash(decks[0]), _hash(decks[1]))
        if deck_hashes is _DEFAULT
        else ((None, None) if deck_hashes is None else deck_hashes)  # type: ignore[assignment]
    )
    seats: list[dict[str, object]] = []
    for index in (0, 1):
        row: dict[str, object] = {"seat": index, "deck_id": decks[index]}
        if hashes[index] is not None:
            row["deck_hash"] = hashes[index]
        if revisions[index] is not None:
            row["studio_revision_id"] = revisions[index]
        row["commanders"] = [commanders[index]]
        seats.append(row)
    header = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "game_id": game_id,
        "seed": seed,
        "engine_commit": commit,
        "pilot": "Pilot 1.0.0",
        "decision_policy": "policy-1",
        "seats": seats,
    }
    if fingerprint is not None:
        header["pilot_fingerprint"] = fingerprint
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


def test_the_pilot_fingerprint_is_the_identity_and_unknown_never_pools(tmp_path: Path) -> None:
    """#1658: games of one deck state with two fingerprints, or with and without one, are
    refused like mixed pilot versions; the same fingerprint counts together."""
    frames = [_frame(1, 0, "mulligan", hand=["A"], chosen=["Keep hand"])]
    fp_a, fp_b = _hash("pilot-a"), _hash("pilot-b")
    _write_log(tmp_path, "g1", frames, seed=1, fingerprint=fp_a)
    _write_log(tmp_path, "g2", frames, seed=2, fingerprint=fp_a)
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["pilots"] == [f"fp:{fp_a}"]
    for game_id, fingerprint in (("g3", None), ("g3", fp_b)):
        _write_log(tmp_path, game_id, frames, seed=3, fingerprint=fingerprint)
        with pytest.raises(ValueError, match="mixed pilot versions"):
            outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)


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


# --- one read per log, each game once, chance findings ----------------------------------


def _long_frames() -> list[dict[str, object]]:
    frames = _simple_frames(["Forest", "Spell"])
    for turn in range(1, 9):
        for seat in (0, 1):
            frames.append(
                _frame(
                    len(frames) + 1,
                    seat,
                    "choose_object",
                    hand=[f"Card {turn}", "Forest"],
                    turn=turn,
                    active=seat,
                )
            )
    frames.append(_frame(99, 0, "mulligan", hand=["Late"], chosen=["Take mulligan"], turn=9))
    return frames


def test_fast_extraction_equals_full_parse_and_parses_fewer_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_log(tmp_path, "long", _long_frames())
    full = card_outcomes._read(path, fast=False)
    calls = {"n": 0}
    real = json.loads

    def counting(text: str | bytes) -> object:
        calls["n"] += 1
        return real(text)

    monkeypatch.setattr(card_outcomes.json, "loads", counting)
    fast = card_outcomes._read(path, fast=True)
    fast_calls = calls["n"]
    calls["n"] = 0
    card_outcomes._read(path, fast=False)
    assert fast == full and fast[0] is not None
    assert fast_calls < calls["n"]


def test_cache_is_used_on_second_call_and_invalidated_by_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_log(tmp_path, "g1", _simple_frames(["X"]))
    calls = {"n": 0}
    real = card_outcomes._read_log

    def counting(p: Path, *, fast: bool = True) -> object:
        calls["n"] += 1
        return real(p, fast=fast)

    monkeypatch.setattr(card_outcomes, "_read_log", counting)
    first = load_exposures(tmp_path)
    second = load_exposures(tmp_path)
    assert calls["n"] == 1 and first == second
    assert list((tmp_path / ".outcomes-cache").glob("*.json"))
    _write_log(tmp_path, "g1", _simple_frames(["Changed"]))
    third = load_exposures(tmp_path)
    assert calls["n"] == 2
    assert third["exposures"][0]["seats"][0]["first_dealt_hand"] == ["Changed"]
    del path


def test_corrupt_cache_entry_is_rebuilt_and_running_logs_are_not_cached(tmp_path: Path) -> None:
    _write_log(tmp_path, "g1", _simple_frames(["X"]))
    _write_log(tmp_path, "run", _simple_frames(["X"]), status=None, gz=False)
    load_exposures(tmp_path)
    cache = tmp_path / ".outcomes-cache"
    assert [p.name for p in cache.glob("*.json")] == ["g1.jsonl.gz.json"]
    (cache / "g1.jsonl.gz.json").write_text("{not json", encoding="utf-8")
    report = load_exposures(tmp_path)
    assert [g["game_id"] for g in report["exposures"]] == ["g1"]
    assert json.loads((cache / "g1.jsonl.gz.json").read_text(encoding="utf-8"))


def test_same_game_id_under_different_names_counts_once(tmp_path: Path) -> None:
    first = _write_log(tmp_path, "g1", _simple_frames(["X"]))
    for name in ("copy-a", "copy-b"):
        shutil.copy(first, tmp_path / f"{name}.jsonl.gz")
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["games_total"] == 1
    assert table["duplicate_logs_ignored"] == 2
    assert any("duplicate" in w for w in table["warnings"])


def _two_seat_game(deck_a: str, deck_b: str) -> GameExposure:
    return {
        "game_id": "m",
        "seed": 1,
        "engine_commit": COMMIT,
        "pilot": "P1",
        "decision_policy": "policy-1",
        "winner_seats": [1],
        "seats": [_seat(0, deck_a, ["Low"], 0.0), _seat(1, deck_b, ["High"], 1.0)],
    }


def test_deck_at_two_seats_counts_only_the_lowest_seat() -> None:
    table = aggregate([_two_seat_game(DECK, DECK)], deck_id=DECK, min_exposed=1)
    assert table["games_total"] == 1 and table["multi_seat_games"] == 1
    assert [c["card"] for c in table["cards"]] == ["Low"]


def test_table_reports_comparisons_and_expected_chance_findings() -> None:
    games = _synthetic(_block("A", 5, 3) + _block("B", 5, 2))
    table = aggregate(games, deck_id=DECK, min_exposed=1)
    measured = sum(1 for c in table["cards"] if c["status"] == "MEASURED")
    assert table["comparisons"] == measured
    assert table["expected_chance_findings"] == round(0.05 * measured, 1)
    text = format_table(table)
    assert "by chance" in text and "hypotheses to re-test, not as verdicts" in text
    assert f"{measured} cards compared at 95 %" in text


def test_newcombe_uses_unrounded_wilson_bounds() -> None:
    games = _synthetic(_block("A", 37, 11) + _block("B", 58, 29))
    row = next(
        c for c in aggregate(games, deck_id=DECK, min_exposed=1)["cards"] if c["card"] == "A"
    )
    n_in, w_in = row["games_in_first_hand"], row["wins_in_first_hand"]
    n_not, w_not = row["games_not_in_first_hand"], row["wins_not_in_first_hand"]
    ci_in = card_outcomes.wilson_unrounded(w_in, n_in)
    ci_not = card_outcomes.wilson_unrounded(w_not, n_not)
    _, lo, hi = newcombe_difference(w_in / n_in, ci_in, w_not / n_not, ci_not)
    assert row["difference_ci95_pp"] == [round(lo * 100, 3), round(hi * 100, 3)]
    assert math.isclose(ci_in[0], wilson_score_interval(w_in, n_in)[0], abs_tol=5e-5)


# --- every deck at the table (#1267 point 1) --------------------------------------------


def test_outcomes_for_all_decks_covers_every_seat(tmp_path: Path) -> None:
    _write_log(tmp_path, "g1", _simple_frames(["X"]), decks=(DECK, OTHER), seed=1)
    _write_log(tmp_path, "g2", _simple_frames(["Y"]), decks=(OTHER, "deck/c"), seed=2)
    _write_log(tmp_path, "g3", _simple_frames(["Z"]), decks=(DECK, DECK), seed=3)
    tables = card_outcomes.outcomes_for_all_decks(tmp_path, min_exposed=1)
    assert sorted(tables) == [DECK, OTHER, "deck/c"]
    # g1 seat 0 plus g3, where the deck sits twice and counts once (its lowest seat)
    assert tables[DECK]["games_total"] == 2
    assert tables[DECK]["multi_seat_games"] == 1
    # the opponent is measured too: g1 seat 1 and g2 seat 0
    assert tables[OTHER]["games_total"] == 2
    assert tables[OTHER]["cards"]
    assert tables["deck/c"]["games_total"] == 1


def test_all_decks_command_prints_every_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    games = tmp_path / "games"
    _write_log(games, "g1", _simple_frames(["Forest"]), decks=(DECK, OTHER), seed=1)
    out = tmp_path / "all.json"
    code = main(
        ["card-outcomes", "--games-dir", str(games), "--min-exposed", "1", "--out", str(out)]
    )
    assert code == 0
    text = capsys.readouterr().out
    assert f"{DECK}  [" in text and f"{OTHER}  [" in text
    written = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(written) == [DECK, OTHER]
    assert written[OTHER]["games_total"] == 1


def test_api_lists_every_deck_in_the_logs(tmp_path: Path) -> None:
    _write_log(tmp_path / "games", "g1", _simple_frames(["X"]), decks=(DECK, OTHER))
    _write_log(
        tmp_path / "games",
        "run",
        _simple_frames(["X"]),
        status=None,
        gz=False,
        decks=("deck/c", OTHER),
    )
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/api/outcomes/decks")
    assert response.status_code == 200
    decks = {row["deck_id"]: row for row in response.json()["decks"]}
    assert decks[DECK]["games"] == 1 and decks[OTHER]["games"] == 1
    # the unfinished game seats deck/c: listed with no finished game, one skipped
    assert decks["deck/c"]["games"] == 0 and decks["deck/c"]["games_skipped"] == 1


# --- robustness from the #1245 review (#1267 point 5) ------------------------------------


def test_structurally_damaged_cache_entry_is_rebuilt_not_raised(tmp_path: Path) -> None:
    _write_log(tmp_path, "g1", _simple_frames(["X"]))
    load_exposures(tmp_path)
    cache = next((tmp_path / ".outcomes-cache").glob("*.json"))
    payload = json.loads(cache.read_text(encoding="utf-8"))
    # Valid JSON, valid envelope (version, size, mtime all match) — but the seats
    # inside are damaged. The shallow check let this through and aggregate raised.
    payload["exposure"]["seats"] = [42]
    cache.write_text(json.dumps(payload), encoding="utf-8")
    report = load_exposures(tmp_path)
    assert [g["game_id"] for g in report["exposures"]] == ["g1"]
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["games_total"] == 1


def test_non_finite_cached_credit_is_rebuilt_not_scored(tmp_path: Path) -> None:
    _write_log(tmp_path, "g1", _simple_frames(["X"]))
    load_exposures(tmp_path)
    cache = next((tmp_path / ".outcomes-cache").glob("*.json"))
    payload = json.loads(cache.read_text(encoding="utf-8"))
    # JSON round-trips the NaN literal as a float, so a bare type check lets
    # it through and every rate of the table turns NaN. A non-finite credit
    # must make the entry a miss, rebuilt from the log like any damage.
    payload["exposure"]["seats"][0]["win_credit"] = float("nan")
    cache.write_text(json.dumps(payload), encoding="utf-8")
    report = load_exposures(tmp_path)
    assert [g["game_id"] for g in report["exposures"]] == ["g1"]
    credit = report["exposures"][0]["seats"][0]["win_credit"]
    assert math.isfinite(credit) and credit == 1.0


def test_cache_temp_name_is_unique_per_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_log(tmp_path, "g1", _simple_frames(["X"]))
    exposure, deck_ids = card_outcomes._read_log(path)
    assert exposure is not None
    names: list[str] = []
    real_replace = os.replace

    def recording(src: str, dst: str) -> None:
        names.append(Path(src).name)
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", recording)
    cache = card_outcomes._cache_file(path)
    stat = path.stat()
    card_outcomes._store(cache, stat.st_size, stat.st_mtime_ns, exposure, deck_ids)
    worker = threading.Thread(
        target=card_outcomes._store,
        args=(cache, stat.st_size, stat.st_mtime_ns, exposure, deck_ids),
    )
    worker.start()
    worker.join()
    assert len(names) == 2 and names[0] != names[1]


def test_process_pool_failure_falls_back_to_serial_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for i in range(card_outcomes.PARALLEL_MIN_LOGS):
        _write_log(tmp_path, f"g{i}", _simple_frames(["X"]), seed=i)

    def broken(*args: object, **kwargs: object) -> object:
        raise RuntimeError("pool cannot start")

    monkeypatch.setattr(card_outcomes, "ProcessPoolExecutor", broken)
    report = load_exposures(tmp_path)
    assert len(report["exposures"]) == card_outcomes.PARALLEL_MIN_LOGS
    assert report["pool_fallback"] is True


# --- deck states (#1657) ---------------------------------------------------------------

STATE_A = _hash("state-a")
STATE_B = _hash("state-b")


def _stated(
    games: list[tuple[list[str], bool]],
    deck_hash: str | None,
    *,
    prefix: str,
    commit: str = COMMIT,
    opponent: str = OTHER,
    revision: str | None = None,
) -> list[GameExposure]:
    """Synthetic games of one deck state; ``deck_hash=None`` is a log of before #1657."""
    out = _synthetic(games, commit=commit)
    for index, game in enumerate(out):
        game["game_id"] = f"{prefix}{index}"
        game["seed"] = sum(map(ord, prefix)) * 1000 + index
        game["bridge_jar_sha256"] = "d" * 64  # a known jar: unknown provenance is not pooled
        game["seats"][0]["deck_hash"] = deck_hash
        game["seats"][0]["revision_id"] = revision
        game["seats"][1]["deck_id"] = opponent
    return out


def _simpson() -> tuple[list[GameExposure], list[GameExposure]]:
    """Two deck states with very different base rates and card exposure (Simpson setting).

    State A: "A" in 30 games with 24 wins, 10 games without "A" with 6 wins (+20 pp).
    State B: "A" in 10 games with 3 wins, 30 games without "A" with 3 wins (+20 pp).
    Raw sums: 27/40 with versus 9/40 without, +45 pp: a number no state shows.
    """
    a = _stated(
        [(["A"], i < 24) for i in range(30)] + [(["F"], i < 6) for i in range(10)],
        STATE_A,
        prefix="a",
        revision="deck/a@aaaa",
    )
    b = _stated(
        [(["A"], i < 3) for i in range(10)] + [(["F"], i < 3) for i in range(30)],
        STATE_B,
        prefix="b",
        revision="deck/a@bbbb",
    )
    return a, b


def test_two_deck_states_give_two_tables_and_one_stratified_row() -> None:
    a, b = _simpson()
    table = card_outcomes.stand_tables([*a, *b], deck_id=DECK, min_exposed=5)
    assert table["strata"] == 2
    assert table["pooling"]["status"] == "POOLED"
    assert table["pooling"]["method"] == card_outcomes.POOLING_METHOD
    stands = {s["deck_hash"]: s for s in table["stands"]}
    assert set(stands) == {STATE_A, STATE_B}
    assert stands[STATE_A]["games_total"] == 40 and stands[STATE_B]["games_total"] == 40
    assert stands[STATE_A]["revision_ids"] == ["deck/a@aaaa"]
    per_state = {h: {r["card"]: r for r in s["cards"]}["A"] for h, s in stands.items()}
    assert per_state[STATE_A]["difference_pp"] == pytest.approx(20.0)
    assert per_state[STATE_B]["difference_pp"] == pytest.approx(20.0)
    assert table["unknown_stand"] is None
    assert table["games_total"] == 80  # n/N of the known states, counted once each
    row = {r["card"]: r for r in table["cards"]}["A"]
    assert row["strata"] == 2
    assert (row["games_in_first_hand"], row["games_not_in_first_hand"]) == (40, 40)
    assert row["rate_in"] is None and row["rate_not"] is None  # rates per state only
    # Mantel-Haenszel by hand: weights 30*10/40 = 7.5 and 10*30/40 = 7.5, both +20 pp
    assert row["difference_pp"] == pytest.approx(20.0)
    raw = aggregate([*a, *b], deck_id=DECK, min_exposed=5)
    raw_row = {r["card"]: r for r in raw["cards"]}["A"]
    assert raw_row["difference_pp"] == pytest.approx(45.0)  # what raw adding would claim
    assert row["difference_pp"] != raw_row["difference_pp"]
    lo, hi = row["difference_ci95_pp"] or [0.0, 0.0]
    assert lo < 20.0 < hi


def test_logs_without_a_hash_form_only_the_unknown_stand() -> None:
    a, _ = _simpson()
    old = _stated(_block("A", 7, 7) + _block("F", 5, 0), None, prefix="old")
    table = card_outcomes.stand_tables([*a, *old], deck_id=DECK, min_exposed=5)
    assert table["strata"] == 1 and table["pooling"]["status"] == "SINGLE_STAND"
    assert table["deck_hash"] == STATE_A
    assert table["games_total"] == 40  # never 52: the unknown stand is not added
    unknown = table["unknown_stand"]
    assert unknown is not None and unknown["deck_hash"] is None
    assert unknown["games_total"] == 12
    assert {r["card"]: r for r in unknown["cards"]}["A"]["games_in_first_hand"] == 7
    assert {r["card"]: r for r in table["cards"]}["A"]["games_in_first_hand"] == 30
    assert any("Stand unbekannt" in w for w in table["warnings"])
    only_old = card_outcomes.stand_tables(old, deck_id=DECK, min_exposed=5)
    assert only_old["status"] == "NO_GAMES" and only_old["cards"] == []
    assert only_old["strata"] == 0
    assert only_old["pooling"]["status"] == "NO_KNOWN_STAND"
    assert only_old["unknown_stand"] is not None
    assert only_old["unknown_stand"]["games_total"] == 12


def test_deck_states_are_never_pooled_across_a_pod_or_engine_change() -> None:
    a, _ = _simpson()
    b_pod = _stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_B, prefix="p", opponent="x")
    table = card_outcomes.stand_tables([*a, *b_pod], deck_id=DECK, min_exposed=5)
    assert table["status"] == "NOT_POOLED" and table["cards"] == []
    assert table["strata"] == 2 and len(table["stands"]) == 2
    assert "pod sets" in str(table["pooling"]["reason"])
    b_engine = _stated(
        _block("A", 10, 5) + _block("F", 10, 5), STATE_B, prefix="e", commit="b" * 40
    )
    for allow in (False, True):
        mixed = card_outcomes.stand_tables(
            [*a, *b_engine], deck_id=DECK, min_exposed=5, allow_mixed=allow
        )
        assert mixed["status"] == "NOT_POOLED" and mixed["cards"] == []
        assert "engine commit" in str(mixed["pooling"]["reason"])


def test_mantel_haenszel_of_one_stratum_is_the_plain_difference_with_wald_variance() -> None:
    n1, y1, n0, y0 = 40, 22.0, 60, 20.0
    result = card_outcomes.mantel_haenszel_difference([(n1, y1, n0, y0)])
    assert result is not None
    d, lo, hi, used = result
    p1, p0 = y1 / n1, y0 / n0
    wald = math.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    assert used == 1
    assert d == pytest.approx(p1 - p0)
    assert (lo, hi) == pytest.approx((d - 1.95996 * wald, d + 1.95996 * wald))
    assert card_outcomes.mantel_haenszel_difference([(0, 0.0, 10, 3.0)]) is None


def test_header_hash_and_revision_are_read_per_seat(tmp_path: Path) -> None:
    path = _write_log(
        tmp_path,
        "g1",
        _simple_frames(["X"]),
        deck_hashes=(STATE_A, "not-a-hash"),
        revisions=("deck/a@aaaa", None),
    )
    game = game_exposures(path)
    assert game is not None
    assert game["seats"][0].get("deck_hash") == STATE_A
    assert game["seats"][0].get("revision_id") == "deck/a@aaaa"
    assert game["seats"][1].get("deck_hash") is None  # not 64 hex: Stand unbekannt


def test_cache_entry_of_before_deck_states_is_read_again(tmp_path: Path) -> None:
    """An entry written by the version-2 cache knows no hash; it must not pass as current."""
    path = _write_log(tmp_path, "g1", _simple_frames(["X"]), deck_hashes=(STATE_A, STATE_B))
    exposure = game_exposures(path)
    assert exposure is not None
    old_seats = [
        {k: v for k, v in seat.items() if k not in ("deck_hash", "revision_id")}
        for seat in exposure["seats"]
    ]
    stat = path.stat()
    old = {
        "version": 2,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "exposure": {**exposure, "seats": old_seats},
        "deck_ids": [DECK, OTHER],
    }
    card_outcomes._cache_file(path).write_text(json.dumps(old), encoding="utf-8")
    again = game_exposures(path)
    assert again is not None
    assert again["seats"][0].get("deck_hash") == STATE_A
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["strata"] == 1 and table["unknown_stand"] is None


def test_api_answers_per_deck_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMMANDER_LAB_CACHE_CHECK", "1")
    games = tmp_path / "games"
    _write_log(games, "g1", _simple_frames(["X"]), deck_hashes=(STATE_A, None))
    _write_log(games, "g2", _simple_frames(["Y"]), deck_hashes=(STATE_B, None))
    _write_log(games, "g3", _simple_frames(["Z"]), deck_hashes=None)
    with TestClient(create_app(tmp_path)) as client:
        body = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1}).json()
        decks = {r["deck_id"]: r for r in client.get("/api/outcomes/decks").json()["decks"]}
    assert body["schema"] == "studio-card-outcomes-2"
    assert body["strata"] == 2 and body["games_total"] == 2
    assert sorted(s["deck_hash"] for s in body["stands"]) == sorted([STATE_A, STATE_B])
    assert body["unknown_stand"]["games_total"] == 1
    assert decks[DECK]["games"] == 3
    assert (decks[DECK]["stands"], decks[DECK]["games_unknown_stand"]) == (2, 1)
    assert (decks[OTHER]["stands"], decks[OTHER]["games_unknown_stand"]) == (0, 3)


# --- review #1671: provenance per stand, unknown is not equal, mix axes, edge rows ---------


def _with(games: list[GameExposure], **fields: object) -> list[GameExposure]:
    for game in games:
        game.update(fields)  # type: ignore[typeddict-item]
    return games


def test_unknown_stand_names_its_provenance_and_bridge_ahead() -> None:
    old = _with(
        _stated(_block("A", 6, 3) + _block("F", 6, 3), None, prefix="o"),
        bridge_jar_sha256="c" * 64,
        bridge_qualification_state="BRIDGE_AHEAD_OF_QUALIFICATION",
    )
    table = card_outcomes.stand_tables(old, deck_id=DECK, min_exposed=1)
    unknown = table["unknown_stand"]
    assert unknown is not None
    assert unknown["pilots"] == ["P1"] and unknown["engine_commits"] == [COMMIT]
    assert unknown["bridge_jar_sha256s"] == ["c" * 64]
    assert unknown["bridge_qualification_states"] == ["BRIDGE_AHEAD_OF_QUALIFICATION"]
    assert any(w.startswith("BRIDGE_AHEAD_OF_QUALIFICATION") for w in unknown["warnings"])
    # the top level (no known stand) repeats the unknown stand's warnings, named
    assert any(
        w.startswith("Stand unbekannt: BRIDGE_AHEAD_OF_QUALIFICATION") for w in table["warnings"]
    )


def test_unknown_provenance_is_never_equal_and_warnings_reach_the_top() -> None:
    a = _with(
        _stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_A, prefix="a", commit=""),
        engine_commit=None,
        bridge_qualification_state="BRIDGE_AHEAD_OF_QUALIFICATION",
    )
    b = _with(
        _stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_B, prefix="b", commit=""),
        engine_commit=None,
        bridge_qualification_state="BRIDGE_AHEAD_OF_QUALIFICATION",
    )
    table = card_outcomes.stand_tables([*a, *b], deck_id=DECK, min_exposed=1)
    assert table["status"] == "NOT_POOLED" and table["cards"] == []
    assert "unknown provenance" in str(table["pooling"]["reason"])
    assert any("BRIDGE_AHEAD_OF_QUALIFICATION" in w for w in table["warnings"])
    assert any(f"deck state {STATE_A[:12]}:" in w for w in table["warnings"])


@pytest.mark.parametrize(
    ("field", "other", "label"),
    [
        ("pilot", "P2", "pilot version"),
        ("engine_commit", "b" * 40, "engine commit"),
        ("bridge_jar_sha256", "e" * 64, "bridge jar SHA-256"),
        ("decision_policy", "policy-2", "decision polic"),
    ],
)
def test_every_mix_axis_refuses_pooling_and_raises_inside_a_stand(
    field: str, other: str, label: str
) -> None:
    def games(deck_hash: str, prefix: str, value: str | None = None) -> list[GameExposure]:
        out = _with(
            _stated(_block("A", 10, 5) + _block("F", 10, 5), deck_hash, prefix=prefix),
            bridge_jar_sha256="d" * 64,
        )
        return _with(out, **{field: value}) if value is not None else out

    across = card_outcomes.stand_tables(
        [*games(STATE_A, "a"), *games(STATE_B, "b", other)], deck_id=DECK, min_exposed=1
    )
    assert across["status"] == "NOT_POOLED" and across["cards"] == []
    assert label.split()[0] in str(across["pooling"]["reason"])
    inside = [*games(STATE_A, "a"), *games(STATE_A, "c", other)]
    with pytest.raises(ValueError, match="mixed"):
        card_outcomes.stand_tables(inside, deck_id=DECK, min_exposed=1)
    same = card_outcomes.stand_tables(
        [*games(STATE_A, "a"), *games(STATE_B, "b")], deck_id=DECK, min_exposed=1
    )
    assert same["pooling"]["status"] == "POOLED"


def test_edge_rate_in_a_stand_is_too_uncertain_and_never_ranked() -> None:
    """3/3 with the card against 0/40 without: Wald would give [100; 100] pp."""
    a = _stated([(["A"], True)] * 3 + [(["F"], False)] * 40, STATE_A, prefix="a")
    b = _stated(_block("A", 20, 10) + _block("F", 20, 10), STATE_B, prefix="b")
    table = card_outcomes.stand_tables([*a, *b], deck_id=DECK, min_exposed=1)
    row = {r["card"]: r for r in table["cards"]}["A"]
    assert row["status"] == "INSUFFICIENT_SAMPLE"
    assert "too uncertain" in str(row["reason"])
    assert "A" not in [r["card"] for r in ranked(table)["ranked"]]


def test_a_stand_without_the_card_on_one_side_adds_nothing_to_its_counts() -> None:
    a = _stated(_block("F", 30, 15), STATE_A, prefix="a")  # "A" never in the first hand
    b = _stated(_block("A", 10, 6) + _block("F", 10, 4), STATE_B, prefix="b")
    table = card_outcomes.stand_tables([*a, *b], deck_id=DECK, min_exposed=10)
    row = {r["card"]: r for r in table["cards"]}["A"]
    assert row["strata"] == 1
    assert (row["games_total"], row["games_not_in_first_hand"]) == (20, 10)
    assert row["status"] == "MEASURED"


def test_api_refuses_mixed_commits_inside_the_unknown_stand_with_409(tmp_path: Path) -> None:
    _write_log(tmp_path / "games", "g1", _simple_frames(["X"]), deck_hashes=None)
    _write_log(tmp_path / "games", "g2", _simple_frames(["X"]), commit="b" * 40, deck_hashes=None)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/outcomes", params={"deck_id": DECK}).status_code == 409
