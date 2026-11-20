"""The number contract EXAKT / GEZÄHLT / SIMULIERT / URTEIL (B3, #1659).

``number_contract.py`` (Python) and ``static/zahl.js`` (the UI component) apply the same rules;
the builder routes Diff-Wirkung, ``/api/outcomes``, deck series and castability send their
figures additionally as ``zahlen``, the old fields stay unchanged.

A new file rather than an extension of ``test_studio_static_guards.py``: that file is changed by
two open pull requests (#1671, #1669). The JavaScript cases run with ``node --test`` against the
real ``zahl.js`` and the real de-DE helpers of ``ui.js``; without node they are skipped, which is
NOT_RUN, not a pass.
"""

from __future__ import annotations

import ast
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, card_outcomes, castability, deck_diff, deck_series
from commander_lab.studio import number_contract as nc
from commander_lab.studio.decks import RevisionCard, create_revision, list_rows
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_card_outcomes import DECK, _simple_frames, _write_log
from tests.unit.test_studio_db_c_paired_readiness import (
    _make_store,
    _stored_series,
    _write_series,
)

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "commander_lab" / "studio" / "static"
MODULE = ROOT / "src" / "commander_lab" / "studio" / "number_contract.py"


def _exakt(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "x",
        "bezeichnung": "Spielbare Starthand",
        "wert": 0.25,
        "einheit": "Anteil",
        "n": None,
        "N": None,
        "intervall": None,
        "klasse": "EXAKT",
        "kohorte": None,
        "quelle": "Hypergeometrie",
        "stand_datum": None,
    }
    base.update(extra)
    return base


def _counted(**extra: object) -> dict[str, object]:
    values: dict[str, object] = {
        "klasse": "GEZÄHLT",
        "n": 3,
        "N": 10,
        "bezug": "Quelldecks (mit der Karte / Kohorte)",
        "wert": 0.3,
        "kohorte": "all",
    }
    values.update(extra)
    return _exakt(**values)


def _simulated(**extra: object) -> dict[str, object]:
    base = _exakt(
        klasse="SIMULIERT",
        n=12,
        N=40,
        bezug="Paare (abgeschlossen / geplant)",
        wert=2.5,
        einheit="pp",
        stand_hash="a" * 64,
        pilot="Konstante",
        data_class="SIMULATED_RESULT",
    )
    base.update(extra)
    return base


# Python and JavaScript judge every case alike (validity); ``True`` = a valid contract.
CASES: list[tuple[str, dict[str, object], bool]] = [
    ("exakt", _exakt(), True),
    ("exakt unknown value", _exakt(wert=None), True),
    ("no class", {k: v for k, v in _exakt().items() if k != "klasse"}, False),
    ("foreign class", _exakt(klasse="SCORE"), False),
    ("VORSCHLAG", _exakt(klasse="VORSCHLAG"), False),
    ("n without N", _exakt(n=3), False),
    ("N without bezug", _counted(bezug=None), False),
    ("share above 1", _exakt(wert=1.5), False),
    ("share interval below 0", _exakt(intervall=[-0.1, 0.4]), False),
    ("points may be negative", _simulated(wert=-3.0, intervall=[-9.0, 2.0]), True),
    ("notes are texts", _simulated(hinweise=["Status MEASURED"]), True),
    ("notes not a list", _simulated(hinweise="Status MEASURED"), False),
    ("n above N", _counted(n=11), False),
    ("counted", _counted(), True),
    ("counted without N", _counted(N=None), False),
    ("counted value without n", _counted(n=None), False),
    ("counted unknown value, N known", _counted(n=None, wert=None), True),
    ("counted without cohort", _counted(kohorte=None), False),
    ("simulated", _simulated(), True),
    ("simulated unknown state", _simulated(stand_hash=None), True),
    ("simulated without N", _simulated(N=None, n=None), False),
    ("simulated without data class", _simulated(data_class=None), False),
    ("simulated without pilot", _simulated(pilot=None), False),
    ("judgement", _exakt(klasse="URTEIL", einheit="Anzahl", wert=71), True),
    ("judgement in points", _exakt(klasse="URTEIL", einheit="Punkte", wert=71.5), True),
    ("judgement with data class", _exakt(klasse="URTEIL", data_class="SIMULATED_RESULT"), False),
    ("value is a bool", _exakt(wert=True), False),
    ("value is text", _exakt(wert="0"), False),
    ("huge integer", _exakt(einheit="Anzahl", wert=10**400), False),
    ("interval reversed", _exakt(intervall=[0.5, 0.1]), False),
    ("unknown key", _exakt(score=1), False),
    ("no source", _exakt(quelle=""), False),
    ("no unit", _exakt(einheit="Meter"), False),
    ("unit missing", {k: v for k, v in _exakt().items() if k != "einheit"}, False),
    ("unit spelled lower case", _exakt(einheit="punkte"), False),
]


@pytest.mark.parametrize(("name", "zahl", "valid"), CASES, ids=[case[0] for case in CASES])
def test_python_contract_rules(name: str, zahl: dict[str, object], valid: bool) -> None:
    assert (nc.check(zahl) == []) is valid, (name, nc.check(zahl))


def test_simulated_without_state_key_and_builder_refusals() -> None:
    missing = {k: v for k, v in _simulated().items() if k != "stand_hash"}
    assert "SIMULIERT ohne Stand-Hash (leer = unbekannt)" in nc.check(missing)
    with pytest.raises(ValueError, match="n ohne N"):
        nc.zahl("x", "X", 1, klasse=nc.EXAKT, einheit="Anzahl", quelle="Liste", n=1)
    with pytest.raises(ValueError, match="VORSCHLAG"):
        nc.zahl("x", "X", 1, klasse="VORSCHLAG", einheit="Anzahl", quelle="Liste")
    built = nc.zahl(
        "s",
        "S",
        None,
        klasse=nc.SIMULIERT,
        einheit="pp",
        quelle="Serie",
        N=4,
        bezug="Paare",
        pilot="Konstante",
    )
    assert built["wert"] is None and built["stand_hash"] is None
    assert built["data_class"] == "SIMULATED_RESULT"


def test_number_contract_module_has_no_store_or_sqlite_import() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
    assert imported <= {"__future__", "math", "collections.abc"}, imported


# --- routes: every figure sent as ``zahlen`` is a valid contract; old fields unchanged -------


def _assert_all_valid(zahlen: object) -> list[dict[str, object]]:
    assert isinstance(zahlen, list) and zahlen
    for item in zahlen:
        assert nc.check(item) == [], (item, nc.check(item))
    ids = [item["id"] for item in zahlen]
    assert len(ids) == len(set(ids)), "ids are unique within an answer"
    return zahlen


def _diff_fixture(tmp_path: Path) -> tuple[str, list[dict[str, object]], dict[str, str]]:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    ids = {
        str(row["oracle_name"]): str(row["card_id"])
        for row in store.connection.execute("SELECT card_id, oracle_name FROM card_fact")
    }
    cmd = RevisionCard("card:project:0001", 1, "commander")
    revision = create_revision(
        store, deck_id="d", name="D", cards=[cmd, RevisionCard(ids["Filler 01"])]
    )
    store.close()
    cards: list[dict[str, object]] = [
        {"card_id": "card:project:0001", "quantity": 1, "zone": "commander"},
        {"card_id": ids["Swarm Rat"], "quantity": 1, "zone": "main"},
    ]
    return revision, cards, ids


def test_diff_route_sends_valid_contracts_for_the_covered_figures(tmp_path: Path) -> None:
    revision, cards, ids = _diff_fixture(tmp_path)
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    body = client.post(
        "/api/diff", json={"base_revision_id": revision, "cards": cards, "cohort": "picked"}
    ).json()
    zahlen = {item["id"]: item for item in _assert_all_valid(body["zahlen"])}
    # covered paths: overlap (3), curve base/target per mana value (16), every colour row (4
    # each), the two combo counts and the source-deck share of every card with a known cohort
    assert {f"overlap.{k}" for k in ("shared_slots", "base_slots", "target_slots")} <= set(zahlen)
    assert sum(1 for key in zahlen if key.startswith("curve.")) == 16
    colour_rows = len(body["colour_deltas"])
    assert sum(1 for key in zahlen if key.startswith("colour.")) == 4 * colour_rows
    assert {"combos.base_complete", "combos.target_complete"} <= set(zahlen)
    for key in ("overlap.shared_slots", "curve.0.base", "combos.target_complete"):
        assert zahlen[key]["klasse"] == "EXAKT"
    freq = zahlen[f"freq.added.{ids['Swarm Rat']}"]
    assert freq["klasse"] == "GEZÄHLT" and str(freq["kohorte"]).startswith("picked · ")
    assert (freq["n"], freq["N"], freq["wert"]) == (1, 1, 1.0)
    for group in ("added", "removed", "changed"):
        for item in body[group]:
            if item["of"] is not None:
                assert f"freq.{group}.{item['card_id']}" in zahlen
    # the old fields are byte-for-byte what diff_impact gives: the answer only gained `zahlen`
    store = StudioStore.open(tmp_path / "studio")
    try:
        base = [
            RevisionCard(str(r["card_id"]), int(r["quantity"]), str(r["zone"]))
            for r in store.connection.execute(
                "SELECT card_id, quantity, zone FROM deck_revision_card WHERE revision_id = ?",
                (revision,),
            )
        ]
        target = [
            RevisionCard(str(c["card_id"]), int(str(c["quantity"])), str(c["zone"])) for c in cards
        ]
        direct = deck_diff.diff_impact(store, base, target, cohort="picked")
    finally:
        store.close()
    old = dict(body)
    del old["zahlen"]
    assert json.dumps(old, sort_keys=True) == json.dumps(direct, sort_keys=True, default=list)


def test_diff_unknown_frequency_is_unknown_never_zero() -> None:
    diff = {
        "cohort": {"key": "all"},
        "added": [
            {"card_id": "c:1", "name": "Known", "decks": 4, "of": 10},
            {"card_id": "c:2", "name": "Unnamed", "decks": None, "of": 10},
            {"card_id": "c:3", "name": "No cohort", "decks": None, "of": None},
        ],
    }
    zahlen = {item["id"]: item for item in nc.diff_zahlen(diff)}
    assert zahlen["freq.added.c:1"]["wert"] == 0.4
    unknown = zahlen["freq.added.c:2"]
    assert unknown["wert"] is None and unknown["n"] is None and unknown["N"] == 10
    assert "freq.added.c:3" not in zahlen  # no cohort size: no number exists, none is made up


def test_diff_commander_change_names_side_and_commander_in_cohort_and_source() -> None:
    diff = {
        "cohort": {"key": "all"},
        "commanders": {"base": ["Old Cmd"], "target": ["New Cmd"], "same": False},
        "added": [{"card_id": "c:1", "name": "In", "decks": 4, "of": 10}],
        "removed": [{"card_id": "c:2", "name": "Out", "decks": 7, "of": 50}],
        "changed": [],
    }
    zahlen = {item["id"]: item for item in nc.diff_zahlen(diff)}
    added, removed = zahlen["freq.added.c:1"], zahlen["freq.removed.c:2"]
    assert added["kohorte"] == "all · New Cmd" and "aktuell (New Cmd)" in str(added["quelle"])
    assert removed["kohorte"] == "all · Old Cmd" and "der Basis (Old Cmd)" in str(removed["quelle"])
    assert added["kohorte"] != removed["kohorte"] and added["quelle"] != removed["quelle"]
    assert added["bezug"] == removed["bezug"] == "Quelldecks (mit der Karte / Kohorte)"


def test_inconsistent_source_data_leave_the_figure_out_instead_of_failing() -> None:
    diff = {
        "cohort": {"key": "all"},
        "added": [
            {"card_id": "c:1", "name": "Too many", "decks": 12, "of": 10},
            {"card_id": "c:2", "name": "Fine", "decks": 2, "of": 10},
        ],
    }
    ids = [item["id"] for item in nc.diff_zahlen(diff)]
    assert ids == ["freq.added.c:2"]
    table = {
        "deck_id": "d",
        "cards": [
            {"card": "Odd", "games_total": 3, "games_in_first_hand": 5, "rate_in": 0.5},
            {"card": "Rate", "games_total": 3, "games_in_first_hand": 1, "rate_in": 1.7},
        ],
    }
    kept = [item["id"] for item in nc.outcomes_zahlen(table)]
    assert "outcome.Odd.rate_in" not in kept and "outcome.Rate.rate_in" not in kept
    assert "outcome.Odd.rate_not" in kept  # the other figures of the card stay


def test_pooled_outcomes_carry_no_single_state_but_the_strata() -> None:
    card = {"card": "X", "status": "MEASURED", "reason": None, "games_total": 10}
    card |= {"games_in_first_hand": 4, "rate_in": 0.5, "games_not_in_first_hand": 6}
    stand = {"deck_id": "d", "cards": [card], "pilots": ["P"], "warnings": [], "table_size": 4}
    table = {
        **stand,
        "pooling": {"status": "POOLED", "method": "mantel_haenszel"},
        "strata": 2,
        "deck_hash": "h1",  # even a stray hash at the top never names a combined answer
        "stands": [{**stand, "deck_hash": "h1"}, {**stand, "deck_hash": "h2"}],
        "unknown_strata": [],
    }
    zahlen = {item["id"]: item for item in nc.outcomes_zahlen(table)}
    pooled = zahlen["outcome.X.rate_in"]
    assert pooled["stand_hash"] is None
    assert (
        "geschichtet über 2 Schichten (Deck-Stände einer Tischgröße; mantel_haenszel)"
        in pooled["hinweise"]
    )
    assert zahlen["outcome.stand.h1.t4.X.rate_in"]["stand_hash"] == "h1"
    assert zahlen["outcome.stand.h2.t4.X.rate_in"]["stand_hash"] == "h2"


def test_outcome_figures_name_the_table_size_of_their_stratum() -> None:
    """#1683: two strata of one deck state at 2 and 4 seats give two figure sets, each naming
    its table size in bezug, kohorte and hinweise; a stratum without a size says so."""
    card = {"card": "X", "status": "MEASURED", "reason": None, "games_total": 10}
    card |= {"games_in_first_hand": 4, "rate_in": 0.5, "games_not_in_first_hand": 6}
    card |= {"difference_pp": 5.0, "difference_ci95_pp": [-10.0, 20.0]}
    base = {"deck_id": "d", "cards": [card], "pilots": ["P"], "warnings": []}
    table = {
        **base,
        "cards": [],
        "pooling": {"status": "NOT_POOLED", "reason": "table size"},
        "strata": 2,
        "stands": [
            {**base, "deck_hash": "h1", "table_size": 2},
            {**base, "deck_hash": "h1", "table_size": 4},
        ],
        "unknown_strata": [
            {**base, "deck_hash": "h1", "table_size": None},
            {**base, "deck_hash": None, "table_size": 3},
        ],
    }
    zahlen = {item["id"]: item for item in nc.outcomes_zahlen(table)}
    two, four = zahlen["outcome.stand.h1.t2.X.rate_in"], zahlen["outcome.stand.h1.t4.X.rate_in"]
    assert two["bezug"].endswith("Tisch mit 2 Sitzen")
    assert four["bezug"].endswith("Tisch mit 4 Sitzen")
    assert two["kohorte"] != four["kohorte"] and "Tisch mit 4 Sitzen" in four["kohorte"]
    assert "Tischgröße: Tisch mit 2 Sitzen" in two["hinweise"]
    diff_two = zahlen["outcome.stand.h1.t2.X.difference_pp"]
    assert diff_two["bezug"] == "Partien (verglichen / alle), Tisch mit 2 Sitzen"
    assert zahlen["outcome.stand.h1.t4.X.difference_pp"]["bezug"].endswith("Tisch mit 4 Sitzen")
    no_size = zahlen["outcome.unknown.h1.tunbekannt.X.rate_in"]
    assert no_size["stand_hash"] == "h1" and no_size["N"] == 10
    assert no_size["bezug"].endswith("Tischgröße unbekannt")
    assert any(h.startswith("Tischgröße unbekannt (") for h in no_size["hinweise"])
    assert not any(h.startswith("Tischgröße: ") for h in no_size["hinweise"])  # named once
    assert zahlen["outcome.unknown.h1.tunbekannt.X.difference_pp"]["bezug"].endswith(
        "Tischgröße unbekannt"
    )
    no_hash = zahlen["outcome.unknown.ohne-hash.t3.X.rate_in"]
    assert no_hash["stand_hash"] is None
    assert "Stand unbekannt (Protokoll ohne Deck-Hash)" in no_hash["hinweise"]
    assert not any(i.startswith("outcome.X.") for i in zahlen)  # NOT_POOLED: no top figures
    _assert_all_valid(list(zahlen.values()))


def test_series_without_planned_pairs_or_result_gets_no_contract() -> None:
    base = {"series_id": "s", "counts_as_result": True, "pairs_completed": 4, "pilots": []}
    payload = {
        "series": [
            {**base, "series_id": "unplanned", "pairs_planned": None, "difference_pp": 1.0},
            {
                **base,
                "series_id": "unplanned-empty",
                "pairs_planned": None,
                "pairs_completed": None,
                "difference_pp": None,
            },
            {**base, "series_id": "nores", "pairs_planned": 8, "counts_as_result": False},
            {**base, "series_id": "ok", "pairs_planned": 8, "difference_pp": -1.5},
            {**base, "series_id": "over", "pairs_planned": 2, "difference_pp": 1.0},
        ]
    }
    zahlen = nc.series_zahlen(payload, {})
    assert [item["id"] for item in zahlen] == ["series.ok.difference_pp"]
    assert zahlen[0]["N"] == 8 and zahlen[0]["bezug"] == "Paare (abgeschlossen / geplant)"


def test_what_if_route_only_gains_zahlen(tmp_path: Path) -> None:
    revision, _cards, ids = _diff_fixture(tmp_path)
    del revision
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cmd = "card:project:0001"
    cards = [{"card_id": cmd, "quantity": 1, "zone": "commander"}]
    cards += [{"card_id": ids[f"Filler {i:02d}"], "quantity": 1, "zone": "main"} for i in (1, 2)]
    body = client.post(
        "/api/cut-lab/what-if",
        json={"cards": cards, "cut": ids["Filler 01"], "add": ids["Filler 05"]},
    ).json()
    _assert_all_valid(body["zahlen"])
    base = [RevisionCard(str(c["card_id"]), 1, str(c["zone"])) for c in cards]
    target = [base[0], RevisionCard(ids["Filler 02"]), RevisionCard(ids["Filler 05"])]
    store = StudioStore.open(tmp_path / "studio")
    try:
        direct = deck_diff.diff_impact(store, base, target)
    finally:
        store.close()
    old = dict(body)
    del old["zahlen"]
    assert json.dumps(old, sort_keys=True) == json.dumps(direct, sort_keys=True, default=list)


def test_outcomes_route_sends_simulated_contracts_per_deck_state(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    assert store.path is not None
    folder = store.path.parent
    store.close()
    _write_log(folder / "games", "g1", _simple_frames(["Forest", "Spell"]))
    _write_log(folder / "games", "g2", _simple_frames(["Forest", "Other"]), winners=(1,), seed=2)
    old_log = _simple_frames(["Forest", "Spell"])
    _write_log(folder / "games", "g3", old_log, seed=3, deck_hashes=None)
    with TestClient(create_app(folder), headers={"X-Studio": "1"}) as client:
        body = client.get("/api/outcomes", params={"deck_id": DECK, "min_exposed": 1}).json()
    zahlen = _assert_all_valid(body["zahlen"])
    stand_hash = body["deck_hash"]
    assert body["pooling"]["status"] == "SINGLE_STAND" and stand_hash
    (unknown,) = body["unknown_strata"]
    top = [
        item for item in zahlen if item["id"].startswith("outcome.") and item["id"].count(".") == 2
    ]
    per_stand = [
        item for item in zahlen if item["id"].startswith(f"outcome.stand.{stand_hash}.t2.")
    ]
    apart = [item for item in zahlen if item["id"].startswith("outcome.unknown.ohne-hash.t2.")]
    assert len(top) == len(per_stand) == 3 * len(body["cards"])
    assert len(apart) == 3 * len(unknown["cards"]) > 0
    assert len(zahlen) == len(top) + len(per_stand) + len(apart)
    for item in zahlen:
        assert item["klasse"] == "SIMULIERT" and item["data_class"] == "SIMULATED_RESULT"
        assert item["pilot"] == "Konstante" and item["piloten"] == ["Pilot 1.0.0"]
        assert item["hinweise"][0].startswith("Status ")
        assert item["bezug"].startswith("Partien (")
    for item in [*top, *per_stand]:
        assert item["stand_hash"] == stand_hash and item["N"] == body["games_total"]
    for item in apart:  # logs before #1657: their own n/N, never added to the known stand
        assert item["stand_hash"] is None and item["N"] == unknown["games_total"]
        assert "Stand unbekannt (Protokoll ohne Deck-Hash)" in item["hinweise"]
    by_id = {item["id"]: item for item in zahlen}
    forest = next(card for card in body["cards"] if card["card"] == "Forest")
    assert by_id["outcome.Forest.rate_in"]["n"] == forest["games_in_first_hand"]
    assert by_id["outcome.Forest.rate_not"]["n"] == forest["games_not_in_first_hand"]
    old = dict(body)
    del old["zahlen"]
    direct = card_outcomes.outcomes_for_folder(folder / "games", deck_id=DECK, min_exposed=1)
    assert old == json.loads(json.dumps(direct))


def test_series_route_sends_simulated_contracts_with_both_deck_hashes(tmp_path: Path) -> None:
    store, folder = _make_store(tmp_path)
    try:
        cards = [RevisionCard("cid-chulane", 1, "commander"), RevisionCard("cid-forest", 99)]
        rev_a = create_revision(store, deck_id="chulane-s", name="Chulane S", cards=cards)
        rev_b = create_revision(
            store,
            deck_id="chulane-s",
            name="Chulane S",
            cards=[RevisionCard("cid-chulane", 1, "commander"), RevisionCard("cid-forest", 98)],
            parent_revision_id=rev_a,
        )
        hashes = deck_series.revision_hashes(store, [rev_a, rev_b, "repo:x"])
    finally:
        store.close()
    assert set(hashes) == {rev_a, rev_b}
    games = folder / "games"
    _write_series(games, _stored_series("paired-1-1-aaaaaaaa", rev_a, rev_b))
    _write_series(games, _stored_series("paired-2-1-bbbbbbbb", "repo:x", rev_b))
    running = _stored_series("paired-3-1-cccccccc", rev_a, rev_b, status="cancelled")
    _write_series(games, running)
    body = TestClient(create_app(folder)).get("/api/decks/chulane-s/series").json()
    zahlen = {item["id"]: item for item in _assert_all_valid(body["zahlen"])}
    counted = [item["series_id"] for item in body["series"] if item["counts_as_result"]]
    assert set(zahlen) == {f"series.{sid}.difference_pp" for sid in counted}
    assert "series.paired-3-1-cccccccc.difference_pp" not in zahlen  # no result, no number
    first = zahlen["series.paired-1-1-aaaaaaaa.difference_pp"]
    assert (first["stand_hash"], first["basis_hash"]) == (hashes[rev_b], hashes[rev_a])
    assert (first["n"], first["N"], first["wert"]) == (40, 40, 2.5)
    assert first["intervall"] == [-4.0, 9.0] and first["stand_datum"] == "2026-11-10"
    assert first["pilot"] == "Konstante" and first["data_class"] == "SIMULATED_RESULT"
    reference = zahlen["series.paired-2-1-bbbbbbbb.difference_pp"]
    assert reference["basis_hash"] is None  # a reference deck has no stored hash: unknown
    old = dict(body)
    del old["zahlen"]
    assert old == json.loads(json.dumps(deck_series.deck_series(folder, [rev_b, rev_a])))


def test_castability_route_sends_exact_contracts_for_every_probability(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    cards = [{"card_id": "card:project:0001", "quantity": 1, "zone": "commander"}]
    cards += [
        {"card_id": f"card:project:{100 + i:04d}", "quantity": 1, "zone": "main"} for i in range(70)
    ]
    cards.append({"card_id": "card:project:0002", "quantity": 29, "zone": "main"})
    body = client.post("/api/castability", json={"cards": cards}).json()
    zahlen = _assert_all_valid(body["zahlen"])
    assert all(item["klasse"] == "EXAKT" for item in zahlen)
    role_hands = sum(len(role["hands"]) for role in body["hand_roles"]["roles"])
    assert len(zahlen) == 2 * len(body["requirements"]) + 1 + 2 * role_hands
    keep = next(item for item in zahlen if item["id"] == "cast.opening_hand.p_keepable")
    assert keep["wert"] == body["opening_hand"]["p_keepable"]
    store = StudioStore.open(tmp_path / "studio")
    try:
        rows = [
            dict(row)
            for row in list_rows(
                store,
                [
                    RevisionCard(str(c["card_id"]), int(str(c["quantity"])), str(c["zone"]))
                    for c in cards
                ],
            )
        ]
    finally:
        store.close()
    old = dict(body)
    del old["zahlen"], old["hand_roles"]
    assert old == json.loads(json.dumps(castability.deck_castability(rows)))


# --- the UI component under node --test ---------------------------------------------------


def _ui_prelude() -> str:
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")
    part = ui[ui.index("function _formatDe(n, opts) {") : ui.index("// Simulator readiness codes")]
    return "globalThis.StudioUI = (() => {" + part + "return {num, pct, numFlex, numSig}; })();\n"


JS_TESTS = r"""
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
__PRELUDE__
const Z = require(__ZAHL__);
globalThis.StudioZahl = Z;
const h = (tag, props, ...kids) => ({ tag, props: props || {}, kids: kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== "") });
const text = (node) => (typeof node === "string" || typeof node === "number" ? String(node) : node.kids.map(text).join(""));
const find = (node, cls, out = []) => { if (node && typeof node === "object") { if (String(node.props.class || "").split(" ").includes(cls)) out.push(node); node.kids.forEach((kid) => find(kid, cls, out)); } return out; };
const CASES = __CASES__;
const exakt = CASES.find((c) => c[0] === "exakt")[1];
const counted = CASES.find((c) => c[0] === "counted")[1];
const simulated = CASES.find((c) => c[0] === "simulated")[1];
const judgement = CASES.find((c) => c[0] === "judgement")[1];

test("every number carries a class: no class or a foreign class is refused and shows no number", () => {
  for (const name of ["no class", "foreign class"]) {
    const zahl = CASES.find((c) => c[0] === name)[1];
    assert.ok(Z.pruefe(zahl).includes("Zahl ohne gültige Klasse"), name);
    const shown = text(Z.knoten(h, zahl));
    assert.equal(shown, "ungültige Zahl");
    assert.doesNotMatch(shown, /\d/);
  }
});
test("VORSCHLAG is no number class", () => {
  assert.ok(Z.pruefe({ ...exakt, klasse: "VORSCHLAG" }).includes("VORSCHLAG ist keine Zahl-Klasse"));
});
test("a missing value renders unbekannt, never 0", () => {
  for (const zahl of [{ ...exakt, wert: null }, { ...counted, wert: null, n: null }, { ...simulated, wert: null, n: null }]) {
    const m = Z.modell(zahl);
    assert.ok(m.ok, JSON.stringify(m.fehler));
    assert.equal(m.wert, "unbekannt");
    assert.equal(find(Z.knoten(h, zahl), "zahl-wert").map(text).join(""), "unbekannt");
  }
  assert.equal(Z.modell({ ...counted, wert: null, n: null }).nN, "unbekannt / 10 Quelldecks (mit der Karte / Kohorte)");
});
test("GEZÄHLT and SIMULIERT never without n/N", () => {
  assert.ok(Z.pruefe({ ...counted, N: null }).includes("GEZÄHLT ohne N"));
  assert.ok(Z.pruefe({ ...counted, n: null }).includes("GEZÄHLT ohne n"));
  assert.ok(Z.pruefe({ ...simulated, N: null, n: null }).includes("SIMULIERT ohne N"));
  assert.equal(Z.modell(counted).nN, "3 / 10 Quelldecks (mit der Karte / Kohorte)");
});
test("n without N is refused in every class", () => {
  for (const zahl of [{ ...exakt, n: 2 }, { ...judgement, n: 2 }]) assert.ok(Z.pruefe(zahl).includes("n ohne N"));
});
test("GEZÄHLT needs its cohort and shows it as origin", () => {
  assert.ok(Z.pruefe({ ...counted, kohorte: null }).includes("GEZÄHLT ohne Kohorte"));
  assert.match(Z.modell(counted).herkunft, /Kohorte: all/);
});
test("SIMULIERT shows the deck hash and the pilot origin", () => {
  const zahl = { ...simulated, basis_hash: "b".repeat(64), piloten: ["Pilot 1.0.0"] };
  const m = Z.modell(zahl);
  assert.equal(m.stand, `SIMULATED_RESULT · Stand ${"a".repeat(12)} gegen ${"b".repeat(12)} · Pilot: Konstante (Pilot 1.0.0)`);
  const node = Z.knoten(h, zahl);
  assert.equal(find(node, "zahl-stand").length, 1, "the state is visible, not only a tooltip");
});
test("SIMULIERT with an unknown state says so; without the state key or data class it is refused", () => {
  assert.match(Z.modell({ ...simulated, stand_hash: null }).stand, /^SIMULATED_RESULT · Stand unbekannt · Pilot: Konstante$/);
  const missing = { ...simulated };
  delete missing.stand_hash;
  assert.ok(Z.pruefe(missing).some((e) => e.startsWith("SIMULIERT ohne Stand-Hash")));
  assert.ok(Z.pruefe({ ...simulated, data_class: null }).includes("SIMULIERT ohne data_class SIMULATED_RESULT"));
});
test("URTEIL never in the same column as GEZÄHLT", () => {
  assert.equal(Z.spalte("GEZÄHLT", [counted, judgement]).ok, false);
  assert.equal(Z.spalte("GEZÄHLT", [counted, null, counted]).ok, true);
  const cell = Z.zelle(h, judgement, "GEZÄHLT", { class: "num" });
  assert.equal(text(cell), "Klasse passt nicht zur Spalte");
  assert.doesNotMatch(text(cell), /71/);
});
test("de-DE display through StudioUI: share, signed points, counts and the class badge", () => {
  assert.equal(Z.modell({ ...exakt, wert: 0.253 }).wert, "25,3 %");
  assert.equal(Z.modell({ ...simulated, wert: -2.5 }).wert, "\u22122,5 pp");
  assert.equal(Z.modell({ ...simulated, wert: 2.5, intervall: [-4, 9] }).intervall, "[\u22124,0; 9,0] pp");
  assert.equal(Z.modell(judgement).klasseText, "Modellurteil");
  const badge = find(Z.knoten(h, counted), "zahl-klasse")[0];
  assert.equal(text(badge), "gezählt");
  assert.ok(badge.props.class.includes("zahl-gezaehlt"));
});
test("origin, n/N reference and notes are visible text, not only a tooltip", () => {
  const zahl = { ...simulated, hinweise: ["Status INSUFFICIENT_SAMPLE", "zu wenige Partien"] };
  const node = Z.knoten(h, zahl);
  const visible = (cls) => find(node, cls).map(text).join("");
  assert.equal(visible("zahl-herkunft"), "Quelle: Hypergeometrie");
  assert.equal(visible("zahl-nn"), "n/N 12 / 40 Paare (abgeschlossen / geplant)");
  assert.equal(visible("zahl-hinweise"), "Hinweise: Status INSUFFICIENT_SAMPLE · zu wenige Partien");
  assert.match(visible("zahl-stand"), /^SIMULATED_RESULT · /);
  assert.ok(Z.pruefe({ ...counted, bezug: null }).includes("N ohne Bezug"));
  assert.ok(Z.pruefe({ ...exakt, wert: 1.5 }).includes("Anteil außerhalb 0..1"));
});
test("index keeps only valid contracts", () => {
  const found = Z.index([counted, { ...counted, id: "bad", kohorte: null }]);
  assert.deepEqual([...found.keys()], ["x"]);
});
test("diffimpact shows the source-deck share as a GEZÄHLT column from the contract", () => {
  vm.runInThisContext(fs.readFileSync(__DIFF__, "utf8"));
  const item = { card_id: "c:1", name: "Card", quantity: 1, mana_value: 2, roles: [], decks: 3, of: 10 };
  const diff = { added: [item], removed: [], changed: [], zahlen: [{ ...counted, id: "freq.added.c:1" }] };
  const nodes = diffImpactNodes(h, diff, { open() {}, roleName: (r) => r, cohortLabel: "alle" });
  const cells = nodes.flatMap((node) => find(node, "zahl"));
  assert.equal(cells.length, 1);
  assert.equal(text(cells[0]), "30,0 % gezähltn/N 3 / 10 Quelldecks (mit der Karte / Kohorte)Quelle: Hypergeometrie · Kohorte: all");
  // the column class is fixed GEZÄHLT: a judgement under the same id shows no number
  const judged = { ...diff, zahlen: [{ ...CASES.find((c) => c[0] === "judgement")[1], id: "freq.added.c:1" }] };
  const wrong = diffImpactNodes(h, judged, { open() {}, roleName: (r) => r, cohortLabel: "alle" });
  const bad = wrong.flatMap((node) => find(node, "zahl-ungueltig"));
  assert.equal(bad.length, 1);
  assert.equal(text(bad[0]), "Klasse passt nicht zur Spalte");
  const plain = diffImpactNodes(h, { ...diff, zahlen: undefined }, { open() {}, roleName: (r) => r, cohortLabel: "alle" });
  assert.equal(plain.flatMap((node) => find(node, "zahl")).length, 0, "without a contract the old text stays");
});
test("deck series show the difference as SIMULIERT with n/N, state and pilot", () => {
  vm.runInThisContext(fs.readFileSync(__SERIES__, "utf8"));
  const item = { series_id: "s1", base_ref: "r1", variant_ref: "r2", counts_as_result: true, pairs_planned: 40,
    pairs_completed: 12, pairs_attempted: 12, difference_pp: 2.5, difference_ci95_pp: [-4, 9], decision_ci_pp: null,
    decision_level_pct: null, seeds: [], tested_seats: [], bridge_jar_sha256s: [], bridge_qualification_states: [],
    covered_by_sealed_epoch: null, pilots: [], status: "completed", status_text: "abgeschlossen", created_at: null };
  const zahlen = Z.index([{ ...simulated, id: "series.s1.difference_pp", intervall: [-4, 9] }]);
  const cells = deckSeriesCells(h, item, "base", { open() {} }, new Map(), zahlen);
  const shown = cells.map(text).join(" | ");
  assert.match(shown, /Differenz \(B \u2212 A\): \+2,5 pp \[\u22124,0; 9,0\] pp simuliertn\/N 12 \/ 40 Paare \(abgeschlossen \/ geplant\)/);
  assert.match(shown, /SIMULATED_RESULT · Stand aaaaaaaaaaaa · Pilot: Konstante/);
});
"""


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: zahl.js tests NOT_RUN, not a pass")
    return node


def test_zahl_js_component_under_node_test(tmp_path: Path) -> None:
    node = _node()
    script = (
        JS_TESTS.replace("__PRELUDE__", _ui_prelude())
        .replace("__ZAHL__", json.dumps(str(STATIC / "zahl.js")))
        .replace("__DIFF__", json.dumps(str(STATIC / "diffimpact.js")))
        .replace("__SERIES__", json.dumps(str(STATIC / "deckseries.js")))
        .replace("__CASES__", json.dumps([[n, z, v] for n, z, v in CASES], ensure_ascii=False))
    )
    path = tmp_path / "zahl.test.js"
    path.write_text(script, encoding="utf-8")
    done = subprocess.run(
        [node, "--test", "--test-reporter=tap", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    counts = node_test_counts(done.stdout)
    assert counts["fail"] == 0 and counts["pass"] >= 10, done.stdout


def node_test_counts(output: str) -> dict[str, int]:
    """``pass``/``fail`` of a ``node --test`` run in either reporter: TAP (``# pass 13``) or spec
    (info sign + ``pass 13``, the default on a terminal and in some CI runners)."""
    output = re.sub(r"\x1b\[[0-9;]*m", "", output).replace("\r", "")  # colours of a terminal
    counts: dict[str, int] = {}
    for key in ("pass", "fail"):
        found = re.search(rf"^(?:#|\u2139) {key} (\d+)\s*$", output, re.MULTILINE)
        if found is None:
            raise AssertionError(f"no '{key}' count in the node --test output:\n{output}")
        counts[key] = int(found.group(1))
    return counts


def test_node_test_counts_reads_tap_and_spec() -> None:
    tap = "1..13\n# tests 13\n# pass 13\n# fail 0\n"
    spec = "\u2139 tests 13\n\u2139 pass 12\n\u2139 fail 1\n"
    assert node_test_counts(tap) == {"pass": 13, "fail": 0}
    assert node_test_counts(spec) == {"pass": 12, "fail": 1}
    coloured = "\x1b[34m\u2139 pass 14\x1b[39m\r\n\x1b[34m\u2139 fail 0\x1b[39m\r\n"
    assert node_test_counts(coloured) == {"pass": 14, "fail": 0}
    with pytest.raises(AssertionError):
        node_test_counts("nothing")


def test_python_and_javascript_judge_every_case_alike() -> None:
    node = _node()
    cases = copy.deepcopy([[name, zahl] for name, zahl, _valid in CASES])
    missing = {k: v for k, v in _simulated().items() if k != "stand_hash"}
    cases.append(["simulated without state key", missing])
    script = (
        f"const Z = require({json.dumps(str(STATIC / 'zahl.js'))});\n"
        f"const cases = {json.dumps(cases, ensure_ascii=False)};\n"
        "process.stdout.write(JSON.stringify(cases.map(([n, z]) => [n, Z.pruefe(z)])));\n"
    )
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=30, check=True
    )
    js = dict(json.loads(done.stdout))
    for name, zahl in cases:
        assert js[name] == nc.check(zahl), name


def test_zahl_js_static_contract() -> None:
    js = (STATIC / "zahl.js").read_text(encoding="utf-8")
    # The two twins know the same units in the same order (Q1-b5 added "Punkte" to both).
    units = re.search(r"const EINHEITEN = \[([^\]]*)\];", js)
    assert units is not None
    assert (
        tuple(json.loads(f"[{units.group(1)}]"))
        == nc.EINHEITEN
        == (
            "Anteil",
            "pp",
            "Anzahl",
            "Punkte",
        )
    )
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<script src="zahl.js"></script>' in index
    assert index.index("ui.js") < index.index("zahl.js") < index.index("diffimpact.js")
    for forbidden in (
        "innerHTML",
        "outerHTML",
        "style:",
        "style=",
        ".toFixed(",
        "toLocaleString",
        "eval(",
    ):
        assert forbidden not in js, forbidden
    for user in ("diffimpact.js", "castability.js", "deckseries.js"):
        assert "StudioZahl." in (STATIC / user).read_text(encoding="utf-8"), user


def test_a_one_seat_table_is_named_in_the_singular() -> None:
    assert nc._table_size_text({"table_size": 1}) == "Tisch mit 1 Sitz"
    assert nc._table_size_text({"table_size": 3}) == "Tisch mit 3 Sitzen"
    assert nc._table_size_text({}) == "Tischgröße unbekannt"
