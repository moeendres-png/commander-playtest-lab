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


# The pilot fingerprint every fixture game names unless told otherwise (#1658, #1687): a game
# without one forms the stratum "Pilot unbekannt".
PILOT_FP = _hash("pilot")


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
    fingerprint: object = _DEFAULT,
    extra_seats: Sequence[object] = (),
    bridge_jar: str | None = None,
    header_extra: dict[str, object] | None = None,
) -> Path:
    """One game log. Every seat names a deck state derived from its deck id unless
    ``deck_hashes`` gives others; ``deck_hashes=None`` writes a log of before #1657.
    ``extra_seats`` are further header seat rows (a bigger table, or a damaged seat list).
    The header names ``PILOT_FP`` unless ``fingerprint`` gives another; ``fingerprint=None``
    writes a log of before #1658 ("Pilot unbekannt")."""
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
    header_seats: list[object] = [*seats, *extra_seats]
    header = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "game_id": game_id,
        "seed": seed,
        "engine_commit": commit,
        "pilot": "Pilot 1.0.0",
        "decision_policy": "policy-1",
        "seats": header_seats,
    }
    named = PILOT_FP if fingerprint is _DEFAULT else fingerprint
    if named is not None:
        header["pilot_fingerprint"] = named
    if bridge_jar is not None:
        header["bridge_jar_sha256"] = bridge_jar
    header.update(header_extra or {})
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
    games: list[tuple[list[str], bool]],
    *,
    commit: str = COMMIT,
    pilot: str = "P1",
    fingerprint: str | None = PILOT_FP,
) -> list[GameExposure]:
    out: list[GameExposure] = []
    for index, (hand, won) in enumerate(games):
        out.append(
            {
                "game_id": f"s{index}",
                "seed": index,
                "engine_commit": commit,
                "pilot": pilot,
                "pilot_fingerprint": fingerprint,
                "decision_policy": "policy-1",
                "table_size": 2,
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
    assert table["engine_commits"] == [COMMIT] and table["pilots"] == [f"fp:{PILOT_FP}"]
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
    # logs without a fingerprint (before #1658) compare their pilot version strings
    pilots = _synthetic(_block("A", 3, 1), fingerprint=None) + _synthetic(
        _block("A", 3, 1), pilot="P2", fingerprint=None
    )
    with pytest.raises(card_outcomes.MixedPilotError, match="mixed pilot versions"):
        aggregate(pilots, deck_id=DECK)


def test_the_pilot_fingerprint_is_the_identity_and_unknown_never_pools(tmp_path: Path) -> None:
    """#1658, #1687: games of one deck state with two fingerprints, or with and without one,
    are never counted together: each fingerprint is a stratum of its own and a log without one
    sits only in "Pilot unbekannt"; the same fingerprint counts together."""
    frames = [_frame(1, 0, "mulligan", hand=["A"], chosen=["Keep hand"])]
    fp_a, fp_b = _hash("pilot-a"), _hash("pilot-b")
    _write_log(tmp_path, "g1", frames, seed=1, fingerprint=fp_a)
    _write_log(tmp_path, "g2", frames, seed=2, fingerprint=fp_a)
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["pilots"] == [f"fp:{fp_a}"] and table["pilot_fingerprint"] == fp_a
    assert table["games_total"] == 2 and table["strata"] == 1
    _write_log(tmp_path, "g3", frames, seed=3, fingerprint=None)
    with_old = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert with_old["strata"] == 1 and with_old["games_total"] == 2  # never 3
    (unknown,) = with_old["unknown_strata"]
    assert unknown["pilot_fingerprint"] is None and unknown["games_total"] == 1
    assert unknown["pilots"] == ["Pilot 1.0.0"]  # the version string of the old log
    assert any(
        "1 game(s) without a pilot fingerprint (Pilot unbekannt)" in w for w in with_old["warnings"]
    )
    _write_log(tmp_path, "g4", frames, seed=4, fingerprint=fp_b)
    both = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert both["strata"] == 2 and both["status"] == "NOT_POOLED" and both["cards"] == []
    by_print = {s["pilot_fingerprint"]: s["games_total"] for s in both["stands"]}
    assert by_print == {fp_a: 2, fp_b: 1}
    assert [s["pilots"] for s in both["stands"]] == [[f"fp:{fp_a}"], [f"fp:{fp_b}"]]
    assert [t["games_total"] for t in both["unknown_strata"]] == [1]


def test_two_fingerprints_at_one_stand_are_separate_strata_not_a_409(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance #1687 over the route: a pilot change at one deck state answers 200 with one
    stratum per fingerprint, each with its own n/N, never combined, and a log without a
    fingerprint only in "Pilot unbekannt"; the figures name the fingerprint of their stratum."""
    monkeypatch.setenv("COMMANDER_LAB_CACHE_CHECK", "1")
    games = tmp_path / "games"
    fp_a, fp_b = _hash("pilot-a"), _hash("pilot-b")
    for fingerprint, count, base in ((fp_a, 6, 0), (fp_b, 4, 100), (None, 3, 200)):
        for n in range(count):
            _write_log(
                games,
                f"g{base + n}",
                _simple_frames(["Sol Ring"] if n % 2 == 0 else ["Forest"]),
                winners=(0,) if n % 3 == 0 else (1,),
                seed=base + n,
                fingerprint=fingerprint,
                bridge_jar="d" * 64,
            )
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "studio-card-outcomes-6"
    assert body["strata"] == 2 and body["status"] == "NOT_POOLED" and body["cards"] == []
    assert body["games_total"] == 10  # 6 + 4: "Pilot unbekannt" is never added
    pooling = body["pooling"]
    assert pooling["differing_axis"] == "pilot_fingerprint"
    assert pooling["differing_values"] == sorted([fp_a, fp_b])
    assert pooling["differing_axes"] == [
        {"field": "pilot_fingerprint", "values": sorted([fp_a, fp_b])}
    ]
    assert "pilot fingerprint (" in pooling["reason"] and "table size" not in pooling["reason"]
    stands = {s["pilot_fingerprint"]: s for s in body["stands"]}
    assert {k: v["games_total"] for k, v in stands.items()} == {fp_a: 6, fp_b: 4}
    assert {s["deck_hash"] for s in body["stands"]} == {_hash(DECK)}
    (apart,) = body["unknown_strata"]
    assert apart["pilot_fingerprint"] is None and apart["games_total"] == 3
    assert apart["deck_hash"] == _hash(DECK) and apart["table_size"] == 2
    # one section per fingerprint (cell of table size and pilot), each a single stratum
    assert [(c["pilot_fingerprint"], c["games_total"]) for c in body["cohorts"]] == sorted(
        [(fp_a, 6), (fp_b, 4)]
    )
    ids = [item["id"] for item in body["zahlen"]]
    assert len(ids) == len(set(ids))  # two fingerprints of one stand never share an id
    for fingerprint, stand in stands.items():
        mine = [
            z
            for z in body["zahlen"]
            if z["id"].startswith(f"outcome.stand.{_hash(DECK)}.t2.p{fingerprint}.")
        ]
        assert len(mine) == 3 * len(stand["cards"]) > 0
        for item in mine:
            assert item["pilot"] == f"Pilot-Fingerabdruck {fingerprint[:12]}"
            assert item["piloten"] == [f"fp:{fingerprint}"] and item["N"] == stand["games_total"]
            assert item["bezug"].endswith(
                f"Tisch mit 2 Sitzen, Pilot-Fingerabdruck {fingerprint[:12]}"
            )
            assert f"Pilot-Fingerabdruck {fingerprint[:12]}" in item["kohorte"]
            assert f"Pilot-Fingerabdruck: {fingerprint}" in item["hinweise"]
    old = [
        z
        for z in body["zahlen"]
        if z["id"].startswith(f"outcome.unknown.{_hash(DECK)}.t2.punbekannt.")
    ]
    assert len(old) == 3 * len(apart["cards"]) > 0
    for item in old:
        assert item["pilot"] == "Pilot unbekannt" and item["N"] == 3
        assert "Pilot unbekannt (Protokollkopf ohne Pilot-Fingerabdruck)" in item["hinweise"]
    assert not [i for i in ids if i.count(".") == 2]  # NOT_POOLED: no figure over two pilots


def test_table_size_and_pilot_cells_pool_only_inside_one_cell() -> None:
    """#1687 with #1694: strata of (table size x pilot fingerprint) cells. Deck states of one
    cell are combined stratified in their own table; two cells never; the reason names both
    axes when both differ."""
    fp_b = _hash("pilot-b")
    a2 = _stated(_block("A", 10, 6) + _block("F", 10, 4), STATE_A, prefix="a")
    b2 = _stated(_block("A", 10, 5) + _block("F", 10, 3), STATE_B, prefix="b")
    a2b = _with(
        _stated(_block("A", 6, 3) + _block("F", 6, 2), STATE_A, prefix="c"), pilot_fingerprint=fp_b
    )
    b2b = _with(
        _stated(_block("A", 6, 2) + _block("F", 6, 2), STATE_B, prefix="d"), pilot_fingerprint=fp_b
    )
    a3 = _with(_stated(_block("A", 4, 1) + _block("F", 4, 2), STATE_A, prefix="e"), table_size=3)
    table = card_outcomes.stand_tables([*a2, *b2, *a2b, *b2b, *a3], deck_id=DECK, min_exposed=1)
    assert table["strata"] == 5 and table["status"] == "NOT_POOLED" and table["cards"] == []
    assert [d["field"] for d in table["pooling"]["differing_axes"]] == [
        "table_size",
        "pilot_fingerprint",
    ]
    reason = str(table["pooling"]["reason"])
    assert "table size (2, 3) and pilot fingerprint (" in reason
    cells = {(c["table_size"], c["pilot_fingerprint"]): c for c in table["cohorts"]}
    assert set(cells) == {(2, PILOT_FP), (2, fp_b), (3, PILOT_FP)}
    own, other, three = cells[(2, PILOT_FP)], cells[(2, fp_b)], cells[(3, PILOT_FP)]
    assert own["pooling"]["status"] == "POOLED" and own["games_total"] == 40
    assert other["pooling"]["status"] == "POOLED" and other["games_total"] == 24
    assert three["pooling"]["status"] == "SINGLE_STAND" and three["games_total"] == 8
    # Mantel-Haenszel only inside a cell: weights 5/5 (own) and 3/3 (other), by hand
    own_row = {r["card"]: r for r in own["cards"]}["A"]
    other_row = {r["card"]: r for r in other["cards"]}["A"]
    assert own_row["strata"] == 2 and own_row["difference_pp"] == pytest.approx(20.0)
    assert other_row["strata"] == 2 and other_row["difference_pp"] == pytest.approx(8.333, abs=1e-3)
    assert (own_row["games_in_first_hand"], other_row["games_in_first_hand"]) == (20, 12)
    for cell in table["cohorts"]:
        assert {(s["table_size"], s["pilot_fingerprint"]) for s in cell["stands"]} == {
            (cell["table_size"], cell["pilot_fingerprint"])
        }
    assert sum(c["strata"] for c in table["cohorts"]) == table["strata"]
    text = format_table(table)
    assert "strata (deck state x table size x pilot fingerprint) 5" in text
    assert f"cohort 2 seats · pilot {fp_b[:12]}: strata 2 (POOLED)  games 24" in text


def test_logs_without_a_fingerprint_with_two_pilot_versions_still_refuse(tmp_path: Path) -> None:
    """#1687: the 409 stays only where games would really be counted together: logs without a
    fingerprint ("Pilot unbekannt") at one deck state that name two pilot versions."""
    games_dir = tmp_path / "studio" / "games"
    games_dir.mkdir(parents=True)
    frames = [_frame(1, 0, "mulligan", hand=["A"], chosen=["Keep hand"])]
    _write_log(games_dir, "g1", frames, seed=1, fingerprint=_hash("pilot-a"))
    _write_log(games_dir, "g2", frames, seed=2, fingerprint=None)
    path = _write_log(games_dir, "g3", frames, seed=3, fingerprint=None, gz=False)
    path.write_text(
        path.read_text(encoding="utf-8").replace("Pilot 1.0.0", "Pilot 0.9.0"), encoding="utf-8"
    )
    with pytest.raises(card_outcomes.MixedPilotError, match="mixed pilot versions"):
        outcomes_for_folder(games_dir, deck_id=DECK, min_exposed=1)
    with TestClient(create_app(tmp_path / "studio")) as client:
        response = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "Pilot-Fingerabdruck" in detail and "nie zusammengezählt" in detail
    assert "unbekannt, nicht 0" in detail and "mixed" not in detail
    assert "eigene Schicht" in detail and "folgt" not in detail
    # the whole answer is refused: no stratum is shown, the fingerprinted ones neither (P3-1)
    assert "gar keine Zahlen, auch nicht für die Schichten mit Fingerabdruck" in detail


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
        "table_size": 2,
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
    exposure, deck_ids, _cohort = card_outcomes._read_log(path)
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
    assert table["unknown_strata"] == []
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
    (unknown,) = table["unknown_strata"]
    assert unknown["deck_hash"] is None and unknown["table_size"] == 2
    assert unknown["games_total"] == 12
    assert {r["card"]: r for r in unknown["cards"]}["A"]["games_in_first_hand"] == 7
    assert {r["card"]: r for r in table["cards"]}["A"]["games_in_first_hand"] == 30
    assert any("Stand unbekannt" in w for w in table["warnings"])
    only_old = card_outcomes.stand_tables(old, deck_id=DECK, min_exposed=5)
    assert only_old["status"] == "NO_GAMES" and only_old["cards"] == []
    assert only_old["strata"] == 0
    assert only_old["pooling"]["status"] == "NO_KNOWN_STAND"
    assert [t["games_total"] for t in only_old["unknown_strata"]] == [12]


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
    assert table["strata"] == 1 and table["unknown_strata"] == []


def test_api_answers_per_deck_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMMANDER_LAB_CACHE_CHECK", "1")
    games = tmp_path / "games"
    _write_log(games, "g1", _simple_frames(["X"]), deck_hashes=(STATE_A, None))
    _write_log(games, "g2", _simple_frames(["Y"]), deck_hashes=(STATE_B, None))
    _write_log(games, "g3", _simple_frames(["Z"]), deck_hashes=None)
    with TestClient(create_app(tmp_path)) as client:
        body = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1}).json()
        decks = {r["deck_id"]: r for r in client.get("/api/outcomes/decks").json()["decks"]}
    assert body["schema"] == "studio-card-outcomes-6"
    assert body["strata"] == 2 and body["games_total"] == 2
    assert sorted(s["deck_hash"] for s in body["stands"]) == sorted([STATE_A, STATE_B])
    assert [t["games_total"] for t in body["unknown_strata"]] == [1]
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
    (unknown,) = table["unknown_strata"]
    assert unknown["pilots"] == [f"fp:{PILOT_FP}"] and unknown["engine_commits"] == [COMMIT]
    assert unknown["bridge_jar_sha256s"] == ["c" * 64]
    assert unknown["bridge_qualification_states"] == ["BRIDGE_AHEAD_OF_QUALIFICATION"]
    assert any(w.startswith("BRIDGE_AHEAD_OF_QUALIFICATION") for w in unknown["warnings"])
    # the top level (no known stand) repeats the unknown stand's warnings, named
    assert any(
        w.startswith(
            f"Stand unbekannt · 2 seats · pilot {PILOT_FP[:12]}: BRIDGE_AHEAD_OF_QUALIFICATION"
        )
        for w in table["warnings"]
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
    assert any(
        f"deck state {STATE_A[:12]} · 2 seats · pilot {PILOT_FP[:12]}:" in w
        for w in table["warnings"]
    )


@pytest.mark.parametrize(
    ("field", "other", "label"),
    [
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


# --- #1683: table size is a stratum; unknown table size apart; never pooled across sizes ---


def _seats(count: int, *, start: int = 2) -> list[dict[str, object]]:
    """Header seat rows of further opponents (seat ``start`` .. ``start + count - 1``)."""
    return [
        {"seat": i, "deck_id": f"deck/x{i}", "commanders": [f"Cmd {i}"]}
        for i in range(start, start + count)
    ]


def test_header_seats_give_the_table_size_and_never_a_guess(tmp_path: Path) -> None:
    cases: list[tuple[list[object], int | None]] = [
        ([], 2),
        (_seats(1), 3),
        (_seats(2), 4),
        (_seats(4), 6),  # read as written: 5/6 seats stay locked elsewhere, not here
        (_seats(1, start=3), None),  # a gap (0, 1, 3): incomplete seat list
        ([{"seat": 1, "deck_id": "deck/x"}], None),  # a repeated seat
        ([{"deck_id": "deck/x"}], None),  # a seat row without a seat number
    ]
    for index, (extra, size) in enumerate(cases):
        path = _write_log(tmp_path, f"g{index}", _simple_frames(["X"]), extra_seats=extra)
        game = game_exposures(path)
        assert game is not None and game.get("table_size") == size, (extra, size)
    # #1662: a seat row that is no mapping cannot say whether a human sat there: the log is of
    # unreadable cohort (fail-closed), stricter than "Tischgröße unbekannt", and never counted
    path = _write_log(tmp_path, "g-row", _simple_frames(["X"]), extra_seats=["not a row"])
    assert game_exposures(path) is None
    assert card_outcomes._table_size(None) is None and card_outcomes._table_size([]) is None


def test_two_three_and_four_seat_logs_of_one_stand_are_separate_strata(tmp_path: Path) -> None:
    """Acceptance #1683: one deck state at 2, 3 and 4 seats gives three strata, never one sum;
    logs without a table size sit only in "Tischgröße unbekannt" with their own n/N."""
    games = tmp_path / "games"
    for size, extra in ((2, []), (3, _seats(1)), (4, _seats(2))):
        for n in range(size):  # 2, 3 and 4 games: every stratum has its own n
            won = (0,) if n % 2 == 0 else (1,)
            hand = ["Sol Ring"] if n == 0 else ["Forest"]
            _write_log(
                games,
                f"t{size}-{n}",
                _simple_frames(hand),
                winners=won,
                seed=size * 10 + n,
                extra_seats=extra,
            )
    for n in range(5):  # a damaged seat list: the size is unknown, never 2 and never 0
        _write_log(
            games,
            f"u{n}",
            _simple_frames(["Sol Ring"]),
            seed=900 + n,
            extra_seats=[{"deck_id": "deck/x"}],
        )
    table = outcomes_for_folder(games, deck_id=DECK, min_exposed=1)
    assert table["strata"] == 3
    by_size = {s["table_size"]: s for s in table["stands"]}
    assert set(by_size) == {2, 3, 4}
    assert {k: v["games_total"] for k, v in by_size.items()} == {2: 2, 3: 3, 4: 4}
    assert all(s["deck_hash"] == _hash(DECK) for s in table["stands"])
    assert {k: len(v["pods"][0]["opponents"]) for k, v in by_size.items()} == {2: 1, 3: 2, 4: 3}
    # never combined across table sizes: no card row at the top, a reason that names the axis
    assert table["status"] == "NOT_POOLED" and table["cards"] == []
    assert table["pooling"]["status"] == "NOT_POOLED"
    assert "table size" in str(table["pooling"]["reason"])
    assert table["table_size"] is None
    (apart,) = table["unknown_strata"]
    assert apart["table_size"] is None and apart["deck_hash"] == _hash(DECK)
    assert apart["games_total"] == 5  # its own n/N
    assert table["games_total"] == 9  # 2 + 3 + 4: the unknown table size is never added
    assert any(
        "5 game(s) without a table size (Tischgröße unbekannt)" in w for w in table["warnings"]
    )
    text = format_table(table)
    assert "strata (deck state x table size x pilot fingerprint) 3" in text
    pilot = f"pilot {PILOT_FP[:12]}"
    assert f"deck state {_hash(DECK)[:12]} · Tischgröße unbekannt · {pilot}  games 5" in text
    for size in (2, 3, 4):
        assert f"deck state {_hash(DECK)[:12]} · {size} seats · {pilot}  games {size}" in text


def test_strata_of_another_table_size_are_never_pooled_even_with_equal_pods() -> None:
    """The size check stands on its own: equal pods and provenance, only the size differs."""
    a = _stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_A, prefix="a")
    b = _with(_stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_B, prefix="b"), table_size=3)
    table = card_outcomes.stand_tables([*a, *b], deck_id=DECK, min_exposed=1)
    assert table["strata"] == 2
    assert table["status"] == "NOT_POOLED" and table["cards"] == []
    assert "table size (2, 3)" in str(table["pooling"]["reason"])
    assert table["pooling"].get("differing_axis") == "table_size"
    assert table["pooling"].get("differing_values") == [2, 3]
    # sizes are listed numerically, never as text ("10, 2"); one seat is singular
    ten = _with(
        _stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_B, prefix="t"), table_size=10
    )
    tens = card_outcomes.stand_tables([*a, *ten], deck_id=DECK, min_exposed=1)
    assert "table size (2, 10)" in str(tens["pooling"]["reason"])
    assert tens["pooling"].get("differing_values") == [2, 10]
    one = _with(_stated(_block("A", 2, 1), STATE_B, prefix="o"), table_size=1)
    assert card_outcomes.stratum_label(card_outcomes.stand_tables(one, deck_id=DECK)).endswith(
        f"· 1 seat · pilot {PILOT_FP[:12]}"
    )
    same = _with(
        _stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_B, prefix="c"), table_size=2
    )
    pooled = card_outcomes.stand_tables([*a, *same], deck_id=DECK, min_exposed=1)
    assert pooled["pooling"]["status"] == "POOLED" and pooled["table_size"] == 2
    assert {r["card"]: r for r in pooled["cards"]}["A"]["strata"] == 2
    # a single known stratum names its size at the top
    single = card_outcomes.stand_tables(b, deck_id=DECK, min_exposed=1)
    assert single["pooling"]["status"] == "SINGLE_STAND" and single["table_size"] == 3


def test_unknown_table_size_is_not_equal_to_a_known_or_another_unknown_one() -> None:
    sized = _stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_A, prefix="a")
    unsized = _with(
        _stated(_block("A", 6, 6) + _block("F", 6, 0), STATE_A, prefix="u"), table_size=None
    )
    table = card_outcomes.stand_tables([*sized, *unsized], deck_id=DECK, min_exposed=1)
    assert table["strata"] == 1 and table["games_total"] == 20  # never 32
    assert [s["table_size"] for s in table["stands"]] == [2]
    assert {r["card"]: r for r in table["cards"]}["A"]["games_in_first_hand"] == 10
    (apart,) = table["unknown_strata"]
    assert (apart["deck_hash"], apart["table_size"], apart["games_total"]) == (STATE_A, None, 12)
    # two deck states, both without a table size: nothing is known, nothing is pooled
    other = _with(
        _stated(_block("A", 6, 3) + _block("F", 6, 3), STATE_B, prefix="o"), table_size=None
    )
    none_known = card_outcomes.stand_tables([*unsized, *other], deck_id=DECK, min_exposed=1)
    assert none_known["strata"] == 0 and none_known["cards"] == []
    assert none_known["pooling"]["status"] == "NO_KNOWN_STAND"
    assert sorted(str(t["deck_hash"]) for t in none_known["unknown_strata"]) == sorted(
        [STATE_A, STATE_B]
    )
    # and _not_poolable itself refuses a stratum without a size
    stands = [dict(t) for t in none_known["unknown_strata"]]
    reason = card_outcomes._not_poolable(stands)  # type: ignore[arg-type]
    assert reason is not None and "table size unknown" in reason


def test_cache_entry_of_before_table_sizes_is_read_again(tmp_path: Path) -> None:
    """An entry of cache version 4 (before #1683) knows no table size; it must not pass as
    "Tischgröße unbekannt" but be read again from its log."""
    path = _write_log(tmp_path, "g1", _simple_frames(["X"]), extra_seats=_seats(1))
    exposure = game_exposures(path)
    assert exposure is not None and exposure.get("table_size") == 3
    stat = path.stat()
    old = {
        "version": 4,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "exposure": {k: v for k, v in exposure.items() if k != "table_size"},
        "deck_ids": [DECK, OTHER, "deck/x2"],
    }
    card_outcomes._cache_file(path).write_text(json.dumps(old), encoding="utf-8")
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["strata"] == 1 and table["table_size"] == 3
    assert table["unknown_strata"] == []
    stored = json.loads(card_outcomes._cache_file(path).read_text(encoding="utf-8"))
    assert stored["version"] == card_outcomes.CACHE_VERSION == 6
    assert stored["exposure"]["table_size"] == 3


@pytest.mark.parametrize("damaged", [True, "3", 0, -2, 2.0])
def test_damaged_cached_table_size_is_rebuilt_from_the_log(tmp_path: Path, damaged: object) -> None:
    path = _write_log(tmp_path, "g1", _simple_frames(["X"]), extra_seats=_seats(1))
    exposure = game_exposures(path)
    assert exposure is not None
    cache = card_outcomes._cache_file(path)
    entry = json.loads(cache.read_text(encoding="utf-8"))
    entry["exposure"]["table_size"] = damaged
    cache.write_text(json.dumps(entry), encoding="utf-8")
    again = game_exposures(path)
    assert again is not None and again.get("table_size") == 3


# --- #1694: one combined table per table size ----------------------------------------------


def _acceptance_1694() -> list[GameExposure]:
    """A@2 (20 games), B@2 (20 games), A@3 (8 games) with equal pods and provenance: only the
    table size tells the third stratum apart."""
    a2 = _stated(_block("A", 10, 6) + _block("F", 10, 4), STATE_A, prefix="a")
    b2 = _stated(_block("A", 10, 5) + _block("F", 10, 3), STATE_B, prefix="b")
    a3 = _with(_stated(_block("A", 4, 1) + _block("F", 4, 2), STATE_A, prefix="c"), table_size=3)
    return [*a2, *b2, *a3]


def test_one_table_size_is_pooled_in_its_own_table_and_another_stands_apart() -> None:
    """Acceptance #1694: A@2 + B@2 + A@3 gives a stratified table for 2 seats AND a table of
    its own for 3 seats; the top level never combines the two table sizes."""
    table = card_outcomes.stand_tables(_acceptance_1694(), deck_id=DECK, min_exposed=1)
    # the top level: never across table sizes, the reason names the axis
    assert table["strata"] == 3
    assert table["status"] == "NOT_POOLED" and table["cards"] == []
    assert table["pooling"]["status"] == "NOT_POOLED"
    assert "table size (2, 3)" in str(table["pooling"]["reason"])
    assert table["pooling"].get("differing_axis") == "table_size"
    assert table["pooling"].get("differing_values") == [2, 3]
    assert table["table_size"] is None
    # one table per table size, each from its own strata only
    two, three = table["cohorts"]
    assert (two["table_size"], three["table_size"]) == (2, 3)
    assert two["pooling"]["status"] == "POOLED" and two["strata"] == 2
    assert two["pooling"]["method"] == card_outcomes.POOLING_METHOD
    assert two["games_total"] == 40 and two["status"] == "OK"
    assert sorted(str(s["deck_hash"]) for s in two["stands"]) == sorted([STATE_A, STATE_B])
    assert {s["table_size"] for s in two["stands"]} == {2}
    row = {r["card"]: r for r in two["cards"]}["A"]
    assert row["strata"] == 2
    assert (row["games_in_first_hand"], row["games_not_in_first_hand"]) == (20, 20)
    expected = card_outcomes.mantel_haenszel_difference([(10, 6, 10, 4), (10, 5, 10, 3)])
    assert expected is not None
    assert row["difference_pp"] == pytest.approx(round(expected[0] * 100, 3))
    assert row["rate_in"] is None  # rates per deck state only
    # the 3-seat table: its own stratum, its own n/N, never part of the 2-seat rows
    assert three["pooling"]["status"] == "SINGLE_STAND" and three["strata"] == 1
    assert three["games_total"] == 8 and three["deck_hash"] == STATE_A
    (alone,) = three["stands"]
    assert alone["table_size"] == 3 and alone["games_total"] == 8
    three_row = {r["card"]: r for r in three["cards"]}["A"]
    assert (three_row["games_in_first_hand"], three_row["games_not_in_first_hand"]) == (4, 4)
    assert three_row["difference_pp"] == pytest.approx(-25.0)
    # every known stratum sits in exactly one table size, never in two
    in_cohorts = sorted(
        (str(s["deck_hash"]), s["table_size"]) for c in table["cohorts"] for s in c["stands"]
    )
    assert in_cohorts == sorted((str(s["deck_hash"]), s["table_size"]) for s in table["stands"])
    # the text view prints both tables apart
    text = format_table(table)
    pilot = f"pilot {PILOT_FP[:12]}"
    assert f"cohort 2 seats · {pilot}: strata 2 (POOLED)  games 40" in text
    assert f"cohort 3 seats · {pilot}: strata 1 (SINGLE_STAND)  games 8" in text


def test_one_table_size_gives_no_cohorts_and_a_cohort_keeps_its_own_reason() -> None:
    """All strata of one table size: the answer is as before (``cohorts`` empty). A table size
    whose deck states were played against other pods stays NOT_POOLED inside its own table."""
    a, b = _simpson()
    same_size = card_outcomes.stand_tables([*a, *b], deck_id=DECK, min_exposed=5)
    assert same_size["pooling"]["status"] == "POOLED" and same_size["cohorts"] == []
    b_pod = _stated(_block("A", 10, 5) + _block("F", 10, 5), STATE_B, prefix="p", opponent="x")
    c3 = _with(_stated(_block("A", 4, 2) + _block("F", 4, 2), STATE_A, prefix="c"), table_size=3)
    table = card_outcomes.stand_tables([*a, *b_pod, *c3], deck_id=DECK, min_exposed=1)
    two, three = table["cohorts"]
    assert two["pooling"]["status"] == "NOT_POOLED" and two["cards"] == []
    assert "pod sets" in str(two["pooling"]["reason"])
    assert "differing_axis" not in two["pooling"]
    assert three["pooling"]["status"] == "SINGLE_STAND"
    # nothing known: the reason names every axis, derived from STRATUM_AXES
    old = _stated(_block("A", 3, 1), None, prefix="o")
    none_known = card_outcomes.stand_tables(old, deck_id=DECK, min_exposed=1)
    assert none_known["pooling"]["reason"] == (
        "no game names all of the deck state, the table size and the pilot fingerprint of this deck"
    )
    assert none_known["cohorts"] == []


def test_api_pools_each_table_size_on_its_own_from_real_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance #1694 over the route: real logs A@2, B@2 and A@3 give a stratified table for
    2 seats, a table of its own for 3 seats and figures that never span two table sizes."""
    monkeypatch.setenv("COMMANDER_LAB_CACHE_CHECK", "1")
    games = tmp_path / "games"
    jar = "d" * 64
    for state, size, count, extra in (
        (STATE_A, 2, 6, []),
        (STATE_B, 2, 6, []),
        (STATE_A, 3, 4, _seats(1)),
    ):
        for n in range(count):
            _write_log(
                games,
                f"{state[:4]}-t{size}-{n}",
                _simple_frames(["Sol Ring"] if n % 2 == 0 else ["Forest"]),
                winners=(0,) if n % 3 == 0 else (1,),
                seed=size * 1000 + n + (500 if state == STATE_B else 0),
                deck_hashes=(state, None),
                extra_seats=extra,
                bridge_jar=jar,
            )
    with TestClient(create_app(tmp_path)) as client:
        body = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1}).json()
    assert body["schema"] == "studio-card-outcomes-6"
    assert body["status"] == "NOT_POOLED" and body["cards"] == [] and body["strata"] == 3
    two, three = body["cohorts"]
    assert (two["table_size"], two["pooling"]["status"], two["games_total"]) == (2, "POOLED", 12)
    assert (three["table_size"], three["pooling"]["status"]) == (3, "SINGLE_STAND")
    assert three["games_total"] == 4
    assert {r["card"]: r for r in two["cards"]}["Sol Ring"]["strata"] == 2
    ids = [item["id"] for item in body["zahlen"]]
    p = f"p{PILOT_FP}"
    assert any(i.startswith(f"outcome.kohorte.t2.{p}.Sol Ring.") for i in ids)
    assert not any(i.startswith("outcome.kohorte.t3.") for i in ids)  # its stratum's figures
    assert any(i.startswith(f"outcome.stand.{STATE_A}.t3.{p}.Sol Ring.") for i in ids)
    assert not [i for i in ids if i.count(".") == 2]  # no figure over two table sizes
    for item in body["zahlen"]:
        if item["id"].startswith("outcome.kohorte.t2."):
            assert item["stand_hash"] is None
            assert item["bezug"].endswith(
                f"Tisch mit 2 Sitzen, Pilot-Fingerabdruck {PILOT_FP[:12]}"
            )
            assert "Tisch mit 2 Sitzen" in item["kohorte"]


def test_card_page_shows_one_section_per_table_size_never_one_table() -> None:
    """#1694 in the page: A@2 + B@2 + A@3 gives a section per table size; the 2-seat section
    has the stratified table and both deck states, the 3-seat section only its own stratum."""
    from tests.unit.test_studio_static_guards import _node_json

    table = card_outcomes.stand_tables(_acceptance_1694(), deck_id=DECK, min_exposed=1)
    fp_b = _hash("pilot-b")
    a = _stated(_block("A", 10, 6) + _block("F", 10, 4), STATE_A, prefix="a")
    b = _with(
        _stated(_block("A", 6, 3) + _block("F", 6, 2), STATE_A, prefix="c"), pilot_fingerprint=fp_b
    )
    old = _with(
        _stated(_block("A", 3, 1) + _block("F", 3, 2), STATE_A, prefix="o"), pilot_fingerprint=None
    )
    pilots = card_outcomes.stand_tables([*a, *b, *old], deck_id=DECK, min_exposed=1)
    script = f"""
global.StudioUI = {{
  num: (n, d = 0) => Number(n).toFixed(d).replace('.', ','),
  pct: (r) => `${{(Number(r) * 100).toFixed(1).replace('.', ',')}} %`,
  kids: (...a) => a.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false),
}};
const mod = require('./kartenauswertung.js');
const textOf = (node) => {{
  if (node === null || node === undefined) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  return (node.kids || []).map(textOf).join(' ');
}};
const count = (node, tag) => {{
  if (!node || typeof node !== 'object') return 0;
  if (Array.isArray(node)) return node.reduce((n, k) => n + count(k, tag), 0);
  return (node.tag === tag ? 1 : 0) + count(node.kids || [], tag);
}};
const h = (tag, attrs, ...kids) => ({{ tag, attrs: attrs || {{}}, kids: kids.flat(Infinity) }});
const slot = {{ children: [], replaceChildren(...kids) {{ this.children = kids; }} }};
const render = async (payload) => {{
  await mod.renderCardOutcomes(slot, {{
    h, deckId: 'deck/a', baseRevision: 'deck/a@aaaa', dirty: false,
    api: async (url) => (url === '/api/outcomes/decks' ? {{ decks: [] }} : payload),
  }});
  const sections = slot.children.filter((n) => n && n.tag === 'section');
  return {{
    text: textOf(slot.children),
    details: count(slot.children, 'details'),
    tables: count(slot.children, 'table'),
    sections: sections.map((s) => ({{
      text: textOf(s), details: count(s, 'details'), tables: count(s, 'table'),
    }})),
  }};
}};
(async () => {{
  const sizes = await render({json.dumps(table)});
  const pilots = await render({json.dumps(pilots)});
  const base = [2, 1, null].map((v) => mod.outcomesBaseRate(v));
  console.log(JSON.stringify({{ ...sizes, pilots, base }}));
}})();
"""
    r = _node_json(script)
    assert isinstance(r, dict)
    text = r["text"]
    pilot = f"Pilot-Fingerabdruck {PILOT_FP[:12]}…"
    assert (
        "Verschiedene Werte von Tischgröße und Pilot-Fingerabdruck werden nie zusammengeführt: "
        "Unten steht je Kombination ein eigener Abschnitt (2 Abschnitte)"
    ) in text
    assert "(bei 2 Sitzen 1/2, bei 3 Sitzen 1/3)" in text
    assert "diese Ansicht kommt als Folgepaket" not in text
    # #1662: the games with a human seat stand apart; built without a folder scan: unknown
    assert "Mensch-Partien (PLAYED_GAME): n = unbekannt" in text
    assert "Mensch-Partien (PLAYED_GAME): n = unbekannt" in r["pilots"]["text"]
    assert "Der Pilot-Fingerabdruck wechselte" not in text  # only the table size differs
    two, three = r["sections"]
    assert two["text"].startswith(
        f"Tischgröße: 2 Sitze · {pilot} · 2 Deck-Stände geschichtet (je Stand eigene Differenz"
    )
    assert (
        "Basis-Siegrate bei 2 Sitzen: 1/2, nie mit einer anderen Tischgröße oder einem anderen "
        "Pilot-Fingerabdruck gemischt"
    ) in two["text"]
    assert "geschichtet über 2 Deck-Stände" in two["text"]
    assert two["details"] == 2 and two["tables"] == 3  # stratified table and one per state
    assert f"Deck-Stand {STATE_A[:12]}… · Tischgröße: 2 Sitze · {pilot} · 20 Partien" in two["text"]
    assert f"Deck-Stand {STATE_B[:12]}… · Tischgröße: 2 Sitze · {pilot} · 20 Partien" in two["text"]
    assert "Tischgröße: 3 Sitze" not in two["text"]
    assert three["text"].startswith(f"Tischgröße: 3 Sitze · {pilot} · 1 Deck-Stand")
    assert three["details"] == 1 and three["tables"] == 1  # a single stratum is shown once
    assert (
        f"Deck-Stand {STATE_A[:12]}… · Tischgröße: 3 Sitze · {pilot} · 8 Partien" in three["text"]
    )
    assert "Tischgröße: 2 Sitze" not in three["text"] and STATE_B[:12] not in three["text"]
    # every stratum once in the page, each with its own provenance
    assert r["details"] == 3 and r["tables"] == 4
    assert text.count("Qualifizierung:") == 5  # top, 2-seat table, three strata
    assert r["base"] == [
        "Basis-Siegrate bei 2 Sitzen: 1/2",
        "Basis-Siegrate bei 1 Sitz: 1/1",
        "Basis-Siegrate unbekannt",
    ]
    # #1687: a pilot change at one deck state: what happened, each stratum with n/N and its
    # fingerprint (short hash), why it is not combined, and "Pilot unbekannt" apart
    pt = r["pilots"]["text"]
    fp_a, fp_b = PILOT_FP[:12], _hash("pilot-b")[:12]
    assert f"Nicht zusammengeführt: Der Pilot-Fingerabdruck wechselte ({fp_a}…, {fp_b}…)" in pt
    assert "Partien verschiedener Piloten nie zusammengezählt" in pt
    assert "steht jeder Pilot-Fingerabdruck als eigene Schicht da" in pt
    assert "Jede Schicht steht unten einzeln mit n/N und Herkunft" in pt
    assert "verschiedenen Tischgrößen" not in pt  # only the pilot differs
    for short, games in ((fp_a, 20), (fp_b, 12)):
        line = f"Deck-Stand {STATE_A[:12]}… · Tischgröße: 2 Sitze · Pilot-Fingerabdruck {short}… · {games} Partien"
        assert line in pt
    assert (
        f"Deck-Stand {STATE_A[:12]}… · Tischgröße: 2 Sitze · Pilot unbekannt: 6 Partien "
        "(getrennt gezählt, nie addiert)"
    ) in pt
    assert "Pilot unbekannt (Protokollkopf ohne Pilot-Fingerabdruck" in pt
    assert "Unbekannt ist nicht gleich" in pt
    assert f"Piloten: Pilot-Fingerabdruck {fp_b}…" in pt and "fp:" not in pt
    assert "Schichten (Deck-Stand, Tischgröße und Pilot-Fingerabdruck): 2" in pt
    assert len(r["pilots"]["sections"]) == 2 and r["pilots"]["details"] == 3
    assert pt.count("Qualifizierung:") == 4  # top and each of the three strata


def test_a_deck_with_only_logs_before_the_fingerprint_explains_what_to_do() -> None:
    """Review #1705 P2-1 (the Owner-PC case): a deck whose logs all carry a deck hash but no
    pilot fingerprint has no known stratum. The page says in German what happened, why its
    numbers are not combined any more, and what to do; no raw English reason is left."""
    from tests.unit.test_studio_static_guards import _node_json

    a = _stated(_block("A", 10, 6) + _block("F", 10, 4), STATE_A, prefix="a")
    b = _stated(_block("A", 10, 5) + _block("F", 10, 3), STATE_B, prefix="b")
    old = _with([*a, *b], pilot_fingerprint=None)
    table = card_outcomes.stand_tables(old, deck_id=DECK, min_exposed=1)
    assert table["pooling"]["status"] == "NO_KNOWN_STAND" and table["cards"] == []
    assert [t["games_total"] for t in table["unknown_strata"]] == [20, 20]
    script = f"""
global.StudioUI = {{
  num: (n, d = 0) => Number(n).toFixed(d).replace('.', ','),
  pct: (r) => `${{(Number(r) * 100).toFixed(1).replace('.', ',')}} %`,
  kids: (...a) => a.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false),
}};
const mod = require('./kartenauswertung.js');
const textOf = (node) => {{
  if (node === null || node === undefined) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  return (node.kids || []).map(textOf).join(' ');
}};
const count = (node, tag) => {{
  if (!node || typeof node !== 'object') return 0;
  if (Array.isArray(node)) return node.reduce((n, k) => n + count(k, tag), 0);
  return (node.tag === tag ? 1 : 0) + count(node.kids || [], tag);
}};
const h = (tag, attrs, ...kids) => ({{ tag, attrs: attrs || {{}}, kids: kids.flat(Infinity) }});
const slot = {{ children: [], replaceChildren(...kids) {{ this.children = kids; }} }};
(async () => {{
  await mod.renderCardOutcomes(slot, {{
    h, deckId: 'deck/a', baseRevision: 'deck/a@aaaa', dirty: false,
    api: async (url) => (url === '/api/outcomes/decks' ? {{ decks: [] }} : {json.dumps(table)}),
  }});
  const note = slot.children.filter((n) => n && n.tag === 'p').map(textOf).join(' || ');
  console.log(JSON.stringify({{
    text: textOf(slot.children), note, details: count(slot.children, 'details'),
    other: mod.outcomesReasonText('something new'),
  }}));
}})();
"""
    r = _node_json(script)
    assert isinstance(r, dict)
    note = r["note"]
    # what happened
    assert "Diese Partien wurden vor dem Pilot-Fingerabdruck aufgezeichnet" in note
    assert "Die alte Pilot-Version blieb immer „1.0.0“, auch wenn sich der Pilot änderte" in note
    # why it is more honest than before
    assert "Ihre Zahlen bleiben je Stand unten sichtbar (eigene n/N)" in note
    assert "weil dabei verschiedene Piloten gemischt worden sein könnten" in note
    # what to do
    assert "Was tun: mit dem aktuellen Piloten neu spielen" in note
    assert "die geschichtete Zeile erscheint wieder" in note
    # the reason of NO_KNOWN_STAND in German, never the raw English one in the explanation
    assert (
        "Nicht zusammengeführt: Keine Partie nennt Deck-Stand, Tischgröße und "
        "Pilot-Fingerabdruck zugleich" in note
    )
    assert "Nicht zusammengeführt: no game names" not in note
    assert r["details"] == 2  # each deck state keeps its own section with n/N
    for state in (STATE_A, STATE_B):
        assert f"Deck-Stand {state[:12]}… · Tischgröße: 2 Sitze · Pilot unbekannt" in r["text"]
    assert r["other"] == "Nicht zusammengeführt: something new"  # unforeseen: shown as it is


def test_the_axes_of_page_and_number_contract_follow_stratum_axes() -> None:
    """#1687: the page (``OUTCOMES_AXES``) and the number contract (``_STRATUM_PARTS``) name the
    strata axes of ``STRATUM_AXES`` in its order, with the same unknown label and pooling; a
    further axis that one of them does not know turns this red."""
    from commander_lab.studio import number_contract
    from tests.unit.test_studio_static_guards import _node_json

    axes = [(a.field, a.unknown, a.pooled) for a in card_outcomes.STRATUM_AXES]
    assert axes == [
        ("deck_hash", "Stand unbekannt", True),
        ("table_size", "Tischgröße unbekannt", False),
        ("pilot_fingerprint", "Pilot unbekannt", False),
    ]
    parts = [(field, pooled) for field, pooled, *_rest in number_contract._STRATUM_PARTS]
    assert parts == [(field, pooled) for field, _unknown, pooled in axes]
    script = """
global.StudioUI = { num: (n) => String(n), pct: (r) => String(r), kids: (...a) => a.flat() };
const mod = require('./kartenauswertung.js');
console.log(JSON.stringify(mod.OUTCOMES_AXES.map((a) => [a.field, a.unknown, a.pooled])));
"""
    assert [tuple(a) for a in _node_json(script)] == axes


# --- #1662: games with a human seat are their own cohort (PLAYED_GAME) ---------------------

PLAYED_NEW = {"data_class": "PLAYED_GAME", "human_seats": [0]}
# Logs written before #1662: the header still says SIMULATED_RESULT (or nothing) but names the
# human seat; no backfill, recognised by ``human_seats`` or a seat pilot "Mensch".
PLAYED_OLD = {"data_class": "SIMULATED_RESULT", "human_seats": [0]}
PLAYED_OLD_NO_CLASS = {"human_seats": [1]}


def _cohort_folder(folder: Path, *played: dict[str, object]) -> None:
    """One simulated game of DECK plus one game per header in ``played``, all finished."""
    _write_log(folder, "sim", _simple_frames(["X"]), seed=1)
    for index, extra in enumerate(played):
        _write_log(
            folder, f"human-{index}", _simple_frames(["X"]), seed=10 + index, header_extra=extra
        )


@pytest.mark.parametrize(
    ("header", "cohort"),
    [
        ({"data_class": "SIMULATED_RESULT", "seats": []}, "SIMULATED_RESULT"),
        ({"seats": []}, "SIMULATED_RESULT"),  # older logs without data_class
        ({"human_seats": [], "seats": []}, "SIMULATED_RESULT"),  # timeout only, no human
        (PLAYED_NEW, "PLAYED_GAME"),
        (PLAYED_OLD, "PLAYED_GAME"),
        (PLAYED_OLD_NO_CLASS, "PLAYED_GAME"),
        ({"data_class": "PLAYED_GAME"}, "PLAYED_GAME"),
        ({"seats": [{"seat": 0, "pilot": "Mensch"}, {"seat": 1, "pilot": "KI"}]}, "PLAYED_GAME"),
        ({"human_seats": "0"}, "UNKNOWN"),
        ({"human_seats": [True]}, "UNKNOWN"),
        ({"human_seats": None, "seats": "x"}, "UNKNOWN"),
        ({"seats": [{"seat": 0, "pilot": "KI"}, "not a row"]}, "UNKNOWN"),
        ({"seats": ["not a row", {"seat": 1, "pilot": "Mensch"}]}, "PLAYED_GAME"),
        ({"data_class": "SOMETHING_ELSE"}, "UNKNOWN"),
        ("not a header", "UNKNOWN"),
    ],
)
def test_game_cohort_reads_the_header_fail_closed(header: object, cohort: str) -> None:
    from commander_lab.studio.games import game_cohort

    assert game_cohort(header) == cohort


def test_played_games_never_count_in_card_outcomes_and_are_named_apart(tmp_path: Path) -> None:
    """M1/M3: a game with a human seat is no exposure, no skipped game and no part of any n."""
    _cohort_folder(tmp_path, PLAYED_NEW)
    report = load_exposures(tmp_path)
    assert [g["game_id"] for g in report["exposures"]] == ["sim"]
    assert report["skipped_with_deck"] == {} and report["skipped_unreadable"] == 0
    assert report["played_with_deck"] == {DECK: 1, OTHER: 1} and report["played_logs"] == 1
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["games_total"] == 1 and table["games_skipped"] == 0
    assert table["seeds"] == 1
    assert all(card["games_total"] == 1 for card in table["cards"])
    assert table["played_cohort"] == {
        "data_class": "PLAYED_GAME",
        "games": 1,
        "games_cohort_unknown": 0,
        "source": card_outcomes.PLAYED_SOURCE,
        "counted_in_simulation": False,
    }
    assert any("human seat (PLAYED_GAME)" in w for w in table["warnings"])
    assert "PLAYED_GAME (human seat) logs 1" in format_table(table)


def test_legacy_played_logs_are_recognised_by_their_human_seats(tmp_path: Path) -> None:
    """M4: logs of before #1662 (data_class SIMULATED_RESULT or none) with a human seat."""
    _cohort_folder(tmp_path, PLAYED_OLD, PLAYED_OLD_NO_CLASS)
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["games_total"] == 1 and table["games_skipped"] == 0
    assert table.get("played_cohort", {}).get("games") == 2


def test_unreadable_cohort_is_counted_in_neither_cohort(tmp_path: Path) -> None:
    """M5: a header whose cohort fields cannot be read is never a simulated game; a log without
    a readable header stays an unreadable skipped log (the path of before #1662)."""
    _cohort_folder(tmp_path, {"human_seats": "0"}, {"data_class": "SOMETHING_ELSE"})
    (tmp_path / "broken.jsonl.gz").write_bytes(gzip.compress(b"{not json\n"))
    table = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    assert table["games_total"] == 1 and table["games_skipped"] == 0
    assert table["games_skipped_unreadable"] == 1
    played = table.get("played_cohort", {})
    assert played.get("games") == 0 and played.get("games_cohort_unknown") == 2
    assert any("unreadable cohort" in w for w in table["warnings"])


def test_played_cohort_without_a_folder_scan_is_unknown_never_zero() -> None:
    table = card_outcomes.stand_tables(_synthetic(_block("A", 4, 2)), deck_id=DECK, min_exposed=1)
    assert table["played_cohort"]["games"] is None
    assert table["played_cohort"]["games_cohort_unknown"] is None
    assert "logs unknown  cohort unknown unknown" in format_table(table)


def test_api_outcomes_and_decks_keep_played_games_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through the routes with the cache check on: the played game is in no simulation n."""
    from commander_lab.studio import cache

    monkeypatch.setattr(cache, "CHECK", True)
    games = tmp_path / "games"
    _cohort_folder(games, PLAYED_OLD)
    _write_log(
        games,
        "only-human",
        _simple_frames(["X"]),
        seed=30,
        decks=("deck/h", OTHER),
        header_extra=PLAYED_NEW,
    )
    _write_log(games, "unknown", _simple_frames(["X"]), seed=40, header_extra={"human_seats": "0"})
    with TestClient(create_app(tmp_path)) as client:
        body = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1}).json()
        decks = {row["deck_id"]: row for row in client.get("/api/outcomes/decks").json()["decks"]}
        human = client.get("/api/outcomes", params={"deck_id": "deck/h"}).json()
    assert body["games_total"] == 1 and body["played_cohort"]["games"] == 1
    assert all(z["N"] == 1 for z in body["zahlen"] if z["id"].startswith("outcome."))
    assert decks[DECK]["games"] == 1 and decks[DECK]["games_skipped"] == 0
    assert decks[DECK]["played_games"] == 1 and decks[DECK]["games_cohort_unknown"] == 1
    assert decks[OTHER]["games"] == 1 and decks[OTHER]["played_games"] == 2
    assert (
        decks[OTHER]["games_cohort_unknown"] == 1 and decks["deck/h"]["games_cohort_unknown"] == 0
    )
    # a deck named only by a game with a human seat: listed, no simulated game, n apart
    assert decks["deck/h"]["games"] == 0 and decks["deck/h"]["games_skipped"] == 0
    assert decks["deck/h"]["played_games"] == 1
    assert human["status"] == "NO_GAMES" and human["games_total"] == 0
    assert human["played_cohort"]["games"] == 1 and human["zahlen"] == []
    assert body["played_cohort"]["games_cohort_unknown"] == 1
    # the same counts on the all-decks path (CLI ``card-outcomes`` without a deck)
    every = card_outcomes.outcomes_for_all_decks(games, min_exposed=1)
    assert {d: t["played_cohort"]["games"] for d, t in every.items()} == {
        DECK: 1,
        OTHER: 2,
        "deck/h": 1,
    }
    assert {d: t["played_cohort"]["games_cohort_unknown"] for d, t in every.items()} == {
        DECK: 1,
        OTHER: 1,
        "deck/h": 0,
    }
    assert every[DECK]["games_total"] == 1 and every["deck/h"]["games_total"] == 0


def test_cache_entry_of_before_the_cohort_is_read_again(tmp_path: Path) -> None:
    """A version-5 entry may hold the exposure of a game with a human seat (cached before
    #1662); it is never served, and no entry without ``data_class`` is."""
    path = _write_log(tmp_path, "h", _simple_frames(["X"]), header_extra=PLAYED_OLD)
    twin = _write_log(tmp_path / "twin", "h", _simple_frames(["X"]))
    exposure = game_exposures(twin)
    assert exposure is not None and game_exposures(path) is None
    stat = path.stat()
    for payload in (
        {"version": 5, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        {
            "version": card_outcomes.CACHE_VERSION,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        },
    ):
        payload.update({"exposure": exposure, "deck_ids": [DECK, OTHER]})
        card_outcomes._cache_file(path).parent.mkdir(exist_ok=True)
        card_outcomes._cache_file(path).write_text(json.dumps(payload), encoding="utf-8")
        report = load_exposures(tmp_path)
        assert report["exposures"] == [] and report["played_with_deck"][DECK] == 1


def test_the_recorder_writes_played_game_for_a_human_seat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writer and reader agree: a log written by GameRecorder with a human seat is PLAYED_GAME,
    even when the caller's header says SIMULATED_RESULT, and the routes do not count it."""
    from commander_lab.studio import cache
    from commander_lab.studio.games import GameRecorder

    monkeypatch.setattr(cache, "CHECK", True)
    seats = [
        {"seat": 0, "deck_id": DECK, "deck_hash": _hash(DECK), "commanders": ["Cmd A"]},
        {"seat": 1, "deck_id": OTHER, "deck_hash": _hash(OTHER), "commanders": ["Cmd B"]},
    ]
    base = {"seed": 1, "engine_commit": COMMIT, "pilot": "Pilot 1.0.0", "seats": seats}
    written: dict[str, str] = {}
    for game_id, extra in (
        ("ai", {}),
        ("human", {"human_seats": [0], "data_class": "SIMULATED_RESULT"}),
    ):
        recorder = GameRecorder(tmp_path, game_id, {**base, **extra})
        packed = recorder.close({"status": "finished", "winner_seats": [0]})
        with gzip.open(packed, "rt", encoding="utf-8") as handle:
            written[game_id] = json.loads(handle.readline())["data_class"]
    assert written == {"ai": "SIMULATED_RESULT", "human": "PLAYED_GAME"}
    with TestClient(create_app(tmp_path)) as client:
        decks = {row["deck_id"]: row for row in client.get("/api/outcomes/decks").json()["decks"]}
    assert decks[DECK]["games"] == 1 and decks[DECK]["played_games"] == 1


def test_simulation_telemetry_never_reads_a_played_game(tmp_path: Path) -> None:
    """M2: the batch read path (``simulations.extract_game_log_telemetry``, which feeds batch
    summaries and the stored ``simulation_run``/``simulation_card``) refuses a game with a human
    seat and one of unreadable cohort instead of scoring it."""
    from commander_lab.studio.simulations import extract_game_log_telemetry

    games = tmp_path / "games"
    _write_log(games, "batch-x-s1", _simple_frames(["X"]))
    _write_log(games, "batch-x-s2", _simple_frames(["X"]), header_extra=PLAYED_OLD)
    _write_log(games, "batch-x-s3", _simple_frames(["X"]), header_extra={"human_seats": "0"})
    sim = extract_game_log_telemetry(tmp_path, "batch-x-s1")
    human = extract_game_log_telemetry(tmp_path, "batch-x-s2")
    unknown = extract_game_log_telemetry(tmp_path, "batch-x-s3")
    assert sim.status == "finished" and sim.candidate_won and sim.observed_cards
    assert human.status == "failed" and human.failure_class == "PlayedGameExcluded"
    assert not human.candidate_won and not human.observed_cards
    assert unknown.status == "failed" and unknown.failure_class == "CohortUnknown"


def test_card_page_names_played_games_apart_and_unknown_never_zero() -> None:
    from tests.unit.test_studio_static_guards import _node_json

    script = """
global.StudioUI = { num: (n, d = 0) => Number(n).toFixed(d) };
const mod = require('./kartenauswertung.js');
const h = (tag, attrs, ...kids) => ({ tag, kids: kids.flat(Infinity) });
const text = (data) => mod.outcomesPlayedNote(h, data).kids.join('');
console.log(JSON.stringify([
  text({ played_cohort: { data_class: 'PLAYED_GAME', games: 3, games_cohort_unknown: 2,
    source: 'Quelle X', counted_in_simulation: false } }),
  text({ played_cohort: { data_class: 'PLAYED_GAME', games: null, games_cohort_unknown: null } }),
  text({}),
]));
"""
    known, unknown, missing = _node_json(script)  # type: ignore[misc]
    assert known == (
        "Mensch-Partien (PLAYED_GAME): n = 3 · Herkunft: Quelle X · eigene Kohorte, in keiner "
        "Zahl oben enthalten · Partien mit unlesbarer Kohorte: 2 (in keiner Kohorte gezählt)"
    )
    assert "n = unbekannt" in unknown and "unlesbarer Kohorte: unbekannt" in unknown
    assert "n = 0" not in unknown
    assert missing.startswith("Mensch-Partien (PLAYED_GAME): unbekannt")


def test_card_page_shows_played_games_in_the_ok_and_no_games_answers(tmp_path: Path) -> None:
    """The line stands in every answer the page renders: OK (cards measured) and NO_GAMES (a
    deck named only by games with a human seat), not only in NOT_POOLED."""
    from tests.unit.test_studio_static_guards import _node_json

    _cohort_folder(tmp_path, PLAYED_NEW)
    _write_log(
        tmp_path,
        "only-human",
        _simple_frames(["X"]),
        seed=30,
        decks=("deck/h", OTHER),
        header_extra=PLAYED_OLD,
    )
    ok = outcomes_for_folder(tmp_path, deck_id=DECK, min_exposed=1)
    none = outcomes_for_folder(tmp_path, deck_id="deck/h", min_exposed=1)
    assert ok["status"] == "OK" and ok["cards"] and none["status"] == "NO_GAMES"
    script = f"""
global.StudioUI = {{
  num: (n, d = 0) => Number(n).toFixed(d),
  pct: (r) => `${{(Number(r) * 100).toFixed(1)}} %`,
  kids: (...a) => a.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false),
}};
const mod = require('./kartenauswertung.js');
const textOf = (node) => {{
  if (node === null || node === undefined) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  return (node.kids || []).map(textOf).join(' ');
}};
const h = (tag, attrs, ...kids) => ({{ tag, attrs: attrs || {{}}, kids: kids.flat(Infinity) }});
const render = async (deckId, payload) => {{
  const slot = {{ children: [], replaceChildren(...kids) {{ this.children = kids; }} }};
  await mod.renderCardOutcomes(slot, {{
    h, deckId, baseRevision: null, dirty: false,
    api: async (url) => (url === '/api/outcomes/decks' ? {{ decks: [] }} : payload),
  }});
  return textOf(slot.children);
}};
(async () => {{
  console.log(JSON.stringify([
    await render('deck/a', {json.dumps(ok)}),
    await render('deck/h', {json.dumps(none)}),
  ]));
}})();
"""
    ok_text, none_text = _node_json(script)  # type: ignore[misc]
    line = "Mensch-Partien (PLAYED_GAME): n = 1 · Herkunft: " + card_outcomes.PLAYED_SOURCE
    assert line in ok_text and "Karten-Auswertung aus simulierten Partien" in ok_text
    assert line in none_text and "liegen noch keine abgeschlossenen Partien" in none_text
