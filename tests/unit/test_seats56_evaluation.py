"""Five- and six-seat results evaluated for the deck builder like two to four seats (#1661).

Owner 2026-11-22 (#1656): simulations at five and six seats are evaluated as sensibly as two to
four seats and used for the deck builder. The seat lock stays on ``main``
(``launch.MAX_RELEASED_SEATS`` = 4); every test that plays five or six seats lifts it in memory
only (``monkeypatch``), and one test per path holds that the shipped lock still refuses them.
The bridge is a test bridge (synthetic N-seat exposures), no real engine ran: NOT_RUN.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from commander_lab.engine.rules.full_game_comparison import difference_quantiles
from commander_lab.studio import (
    card_outcomes,
    deck_series,
    games,
    launch,
    maturity,
    number_contract,
    paired_series,
    table_spec,
)
from tests.unit.test_seats_5_6_simulate_1702 import HEADERS, _finished, lab  # noqa: F401
from tests.unit.test_studio_maturity import _assess, _finding

STATIC = Path(paired_series.__file__).resolve().parent / "static"


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the page check is NOT_RUN, not a pass")
    return node


def _run_node(script: str) -> dict[str, object]:
    done = subprocess.run(
        [_node(), "-e", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
        cwd=STATIC,
    )
    out: dict[str, object] = json.loads(done.stdout)
    return out


_UI = (
    "globalThis.StudioUI = { num: (v, d = 0) => Number(v).toLocaleString('de-DE', "
    "{ minimumFractionDigits: d, maximumFractionDigits: d }) };\n"
    "const vm = require('vm'); const fs = require('fs');\n"
    "const load = (name) => vm.runInThisContext(fs.readFileSync(name, 'utf8'));\n"
    "function h(tag, attrs, ...kids) { return { tag, attrs: attrs || {}, "
    "kids: kids.flat(9).filter((k) => k !== null && k !== undefined && k !== false) }; }\n"
    "const text = (n) => typeof n === 'string' ? n : (n.kids || []).map(text).join('');\n"
)


def _independent_wilson_half_width(p: float, n: int) -> float:
    """The 95 % Wilson half width written out here, not taken from the code under test."""
    z = 1.959963984540054
    centre_spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return centre_spread / (1 + z * z / n)


# -- the lock stays: the shipped lock still refuses five and six seats ------------------------


def test_the_shipped_lock_still_refuses_five_and_six_seats_and_is_unchanged(
    lab: dict[str, object],  # noqa: F811
) -> None:
    assert launch.MAX_RELEASED_SEATS == 4
    for opponents in (4, 5):
        with pytest.raises(ValueError, match="locked"):
            launch.validate_released_seat_count(opponents)
    client = lab["client"]
    assert isinstance(client, TestClient)
    for seats in (5, 6):
        plan = client.get(
            f"/api/simulations/paired-plan?budget_pairs={seats * seats}&table_size={seats}",
            headers=HEADERS,
        ).json()
        # planning (with the base win rate 1/N) is allowed, starting is not
        assert plan["table"]["released"] is False
        assert plan["baseline"]["table_size"] == seats
    js = (STATIC / "paired.js").read_text(encoding="utf-8")
    assert "const PAIRED_RELEASED_SEATS = 4;" in js
    assert "const OPPONENT_COUNTS = [1, 2, 3];" in (STATIC / "partie.js").read_text("utf-8")


# -- planner: base win rate 1/N and the Wilson games at five and six seats --------------------


def test_the_pair_sd_follows_the_base_win_rate_at_five_and_six_and_stays_at_four() -> None:
    assert paired_series.planning_pair_sd(4) == 0.63
    assert paired_series.planning_pair_sd(2) == paired_series.planning_pair_sd(3) == 0.63
    # 0.63 / sqrt(2 * 1/4 * 3/4) * sqrt(2 * p * (1 - p)), hand-computed
    assert paired_series.planning_pair_sd(5) == 0.582
    assert paired_series.planning_pair_sd(6) == 0.5422
    assert paired_series.planning_pair_sd(6) < paired_series.planning_pair_sd(5) < 0.63


@pytest.mark.parametrize(
    ("seats", "pct", "half", "games"), [(5, 20.0, 4.0, 383), (6, 16.7, 3.33, 480)]
)
def test_the_wilson_games_give_plus_minus_twenty_percent_of_one_over_n(
    seats: int, pct: float, half: float, games: int
) -> None:
    base = paired_series.planning_baseline(seats)
    assert base["win_rate_pct"] == pct and base["half_width_pp"] == half
    assert base["relative_precision"] == 0.2 and base["applies_to_plan"] is True
    assert base["games_needed_wilson"] == games
    p = 1.0 / seats
    # the fewest games: the independent Wilson half width holds at n and not at n - 1
    assert _independent_wilson_half_width(p, games) <= 0.2 * p
    assert _independent_wilson_half_width(p, games - 1) > 0.2 * p
    # close to the normal approximation 1.96^2 * p(1-p) / (0.2 p)^2 (384.2 at 5, 480.2 at 6)
    assert abs(games - 1.96**2 * p * (1 - p) / (0.2 * p) ** 2) < 3
    assert f"Zufallsbasis 1/{seats}" in str(base["basis"])


def test_four_seats_keep_their_plan_and_their_reference_untouched() -> None:
    four = paired_series.planned_detectable_difference_pp(40, 4)
    assert four == paired_series.planned_detectable_difference_pp(40, 4, 4)
    assert (four["detectable_pp_low"], four["detectable_pp_high"]) == (31.3, 41.5)
    assert (four["pairs_needed_low"], four["pairs_needed_high"]) == (1254, 2195)
    assert four["assumptions"]["pair_sd"] == 0.63  # type: ignore[index]
    assert four["baseline"]["applies_to_plan"] is False  # type: ignore[index]
    assert paired_series.planning_baseline(4)["win_rate_pct"] == 25.0


@pytest.mark.parametrize(("seats", "sd"), [(5, 0.582), (6, 0.5422)])
def test_the_plan_at_five_and_six_seats_is_built_on_one_over_n(seats: int, sd: float) -> None:
    pairs = seats * seats
    plan = paired_series.planned_detectable_difference_pp(pairs, seats, seats)
    t95, t80 = difference_quantiles(seats - 1)
    expected = (t95 + t80) * sd / math.sqrt(pairs) * 100
    assert plan["detectable_pp_low"] == round(expected, 1)
    assumptions = plan["assumptions"]
    assert isinstance(assumptions, dict)
    assert assumptions["pair_sd"] == sd
    assert assumptions["pair_sd_win_rate_pct"] == round(100 / seats, 1)
    assert assumptions["pair_sd_independent_exact"] == round(
        math.sqrt(2 * (1 / seats) * (1 - 1 / seats)), 4
    )
    assert f"1/{seats}" in str(assumptions["pair_sd_basis"])
    # a smaller sd needs fewer pairs for the same 5 pp than the 25 % plan of four seats
    four = paired_series.planned_detectable_difference_pp(pairs, seats, 4)
    assert int(str(plan["pairs_needed_low"])) < int(str(four["pairs_needed_low"]))
    # the table size never comes from the seats per seed: one tested seat, still 1/N
    fixed = paired_series.planned_detectable_difference_pp(10, 1, seats)
    assert fixed["assumptions"]["pair_sd"] == sd  # type: ignore[index]


# -- duration: derived from the measured wall ratio, never a floor; 2/3 stay UNKNOWN ---------


@pytest.mark.parametrize(
    ("seats", "pairs", "ratio", "seconds", "minutes", "pool"),
    [(5, 25, 1.56, 519, 8.7, (607.3, 50, 50)), (6, 36, 2.22, 1063, 17.7, (379.2, 72, 72))],
)
def test_the_duration_at_five_and_six_seats_is_a_derived_estimate_with_n_of_n(
    seats: int,
    pairs: int,
    ratio: float,
    seconds: int,
    minutes: float,
    pool: tuple[float, int, int],
) -> None:
    est = paired_series.estimate_series_duration(pairs, seats_per_seed=seats, table_size=seats)
    assert est["duration_known"] is True and est["duration_kind"] == "derived_estimate"
    assert est["wall_ratio_vs_four_seats"] == ratio and est["wall_ratio_games"] == [10, 10]
    # 2 * pairs games at 541.2 / ratio games per hour, hand-computed
    assert est["estimated_seconds"] == seconds and est["estimated_minutes"] == minutes
    assert est["games_per_hour_used"] == round(541.2 / ratio, 1)
    for key in ("minimum_seconds", "minimum_minutes"):
        assert est[key] is None, key  # a median ratio is no floor
    assert est["minimum_is_lower_bound"] is False
    ref = est["pool_reference_part_b"]
    assert isinstance(ref, dict)
    assert (ref["games_per_hour"], ref["games"], ref["planned"]) == pool
    basis = str(est["basis"])
    minutes_de = str(minutes).replace(".", ",")
    assert basis.startswith(f"geschätzt ~{minutes_de} min (abgeleitet, keine Untergrenze)")
    assert "mindestens" not in basis and "n = 10/10" in basis
    assert f"n = {pool[1]}/{pool[2]} Partien" in basis
    planning = est["planning"]
    assert isinstance(planning, dict)
    assert planning["baseline"]["table_size"] == seats  # type: ignore[index]


def test_two_and_three_seats_stay_unknown_and_four_stays_the_floor() -> None:
    for seats in (2, 3):
        est = paired_series.estimate_series_duration(10, table_size=seats)
        assert est["duration_known"] is False and est["duration_kind"] == "unknown"
        assert est["estimated_minutes"] is None and est["wall_ratio_vs_four_seats"] is None
        assert est["pool_reference_part_b"] is None
    four = paired_series.estimate_series_duration(40, table_size=4)
    assert four["duration_kind"] == "floor" and four["minimum_minutes"] == 8.9
    assert four["minimum_is_lower_bound"] is True and four["wall_ratio_vs_four_seats"] is None


def test_the_page_constants_equal_the_server_figures() -> None:
    js = (STATIC / "paired.js").read_text(encoding="utf-8")
    ratios = re.search(
        r"const PAIRED_WALL_RATIO_VS_FOUR_SEATS = \{ 5: ([\d.]+), 6: ([\d.]+) \};", js
    )
    assert ratios is not None
    assert {5: float(ratios.group(1)), 6: float(ratios.group(2))} == (
        paired_series.WALL_RATIO_VS_FOUR_SEATS
    )
    pool = re.search(
        r"const PAIRED_POOL_REFERENCE_PART_B = \{ 5: \[([\d.]+), (\d+), (\d+)\], "
        r"6: \[([\d.]+), (\d+), (\d+)\] \};",
        js,
    )
    assert pool is not None
    for seats, at in ((5, 1), (6, 4)):
        ref = paired_series.POOL_REFERENCE_PART_B[seats]
        assert (float(pool.group(at)), int(pool.group(at + 1)), int(pool.group(at + 2))) == (
            ref["games_per_hour"],
            ref["games"],
            ref["planned"],
        )


# -- pool wall limit: the 1,800 s every part-B pool game finished under ------------------------


def test_every_seat_count_the_engine_seats_has_a_pool_wall_limit() -> None:
    limits = [
        table_spec.game_wall_limit_seconds(n) for n in range(launch.MIN_SEATS, launch.MAX_SEATS + 1)
    ]
    assert limits == [1800.0] * 5
    with pytest.raises(ValueError, match="keine Wandzeit-Grenze"):
        table_spec.game_wall_limit_seconds(launch.MAX_SEATS + 1)


# -- the cohort carries the table size ---------------------------------------------------------


def _header(seats: list[object]) -> dict[str, object]:
    return {"seats": [{"seat": s, "pilot": "GenericCommanderPilot"} for s in seats]}


@pytest.mark.parametrize("seats", [4, 5, 6])
def test_cohort_fields_name_the_table_size_of_a_complete_seat_list(seats: int) -> None:
    fields = games.cohort_fields(_header(list(range(seats))))
    assert fields == {"cohort": "SIMULATED_RESULT", "played_seats": [], "table_size": seats}


def test_the_header_size_rule_equals_the_card_evaluation_rule() -> None:
    cases: list[object] = [
        _header([0, 1, 2, 3, 4]),
        _header([0, 1, 2, 3, 4, 5]),
        _header([0, 1, 2, 4, 5]),  # a gap
        _header([0, 1, 1, 2, 3]),  # a repeat
        _header([0, 1, "2", 3, 4]),  # a seat that is no integer
        _header([0, 1, True, 3, 4]),  # a bool is no seat number
        {"seats": []},
        {"seats": "five"},
        {"seats": [{"seat": 0}, "row"]},
        {},
        "no header",
    ]
    for case in cases:
        rows = case.get("seats") if isinstance(case, dict) else None
        assert games.header_table_size(case) == card_outcomes._table_size(rows), case
    assert games.header_table_size(_header([0, 1, 2, 4, 5])) is None


def test_the_pill_names_five_and_six_seats_and_nothing_for_an_unknown_size() -> None:
    out = _run_node(
        _UI
        + """
const C = require('./cohort.js');
const pill = (r) => C.pill(r).text;
process.stdout.write(JSON.stringify({
  five: pill({ cohort: 'SIMULATED_RESULT', played_seats: [], table_size: 5 }),
  six: pill({ cohort: 'SIMULATED_RESULT', played_seats: [], table_size: 6 }),
  sixTitle: C.pill({ cohort: 'SIMULATED_RESULT', table_size: 6 }).title,
  played: pill({ cohort: 'PLAYED_GAME', played_seats: [0], table_size: 5 }),
  none: pill({ cohort: 'SIMULATED_RESULT', played_seats: [] }),
  bad: [pill({ cohort: 'SIMULATED_RESULT', table_size: '5' }), pill({ cohort: 'SIMULATED_RESULT', table_size: 1 })],
  unknown: pill({ cohort: 'UNKNOWN', table_size: 5 }),
}));
"""
    )
    assert out["five"] == "simuliert (KI auf allen Plätzen, 5 Sitze)"
    assert out["six"] == "simuliert (KI auf allen Plätzen, 6 Sitze)"
    assert "Tisch mit 6 Sitzen (eigene Kohorte" in str(out["sixTitle"])
    assert out["played"] == "gespielt (Mensch an Sitz 1, 5 Sitze), zählt in keiner Simulationszahl"
    assert out["none"] == "simuliert (KI auf allen Plätzen)"
    assert out["bad"] == ["simuliert (KI auf allen Plätzen)"] * 2
    assert out["unknown"] == "Herkunft unbekannt, nicht als Simulation gewertet"


# -- stored series: the table size from the seed plan, the cohort of its figure ----------------


def _raw_series(**over: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "series_id": "paired-x",
        "base_ref": "deck@a",
        "variant_ref": "deck@b",
        "pod": "precon",
        "status": "completed",
        "budget_pairs": 25,
        "tested_seats": [0],
        "seed_plan": {"player_count": 5},
        "result": {"pairs_completed": 25, "pairs_played": 25, "tested_seats": [0]},
    }
    raw.update(over)
    return raw


def test_a_stored_series_names_its_table_size_from_the_seed_plan_not_the_tested_seats() -> None:
    for seats in (5, 6):
        entry = deck_series._entry(_raw_series(seed_plan={"player_count": seats}), "completed")
        assert entry["table_size"] == seats and entry["tested_seats"] == [0]
    for plan in (None, {}, {"player_count": "5"}, {"player_count": 7}, {"player_count": True}):
        raw = _raw_series(seed_plan=plan)
        assert deck_series._entry(raw, "completed")["table_size"] is None, plan


def test_the_series_figure_carries_its_table_size_and_two_sizes_never_share_a_cohort() -> None:
    series = []
    for sid, seats in (("s5", 5), ("s6", 6), ("s0", None)):
        entry = deck_series._entry(
            _raw_series(series_id=sid, seed_plan={"player_count": seats}), "completed"
        )
        entry["difference_pp"] = 4.0
        series.append(entry)
    figures = {
        str(z["id"]).split(".")[1]: z for z in number_contract.series_zahlen({"series": series}, {})
    }
    assert figures["s5"]["kohorte"] == "Tisch precon · Tisch mit 5 Sitzen"
    assert figures["s6"]["kohorte"] == "Tisch precon · Tisch mit 6 Sitzen"
    assert figures["s0"]["kohorte"] == "Tisch precon · Tischgröße unbekannt"
    assert len({str(z["kohorte"]) for z in figures.values()}) == 3


# -- maturity: the finding names its table; Holm per table; at most R1 -------------------------


def test_findings_name_their_table_and_holm_never_crosses_table_sizes() -> None:
    five = _finding("c5", table_hash="t5")
    six = _finding("c6", table_hash="t6", first_seed=600)
    five.entry["table_size"] = 5
    six.entry["table_size"] = 6
    got = _assess(five, six)
    assert got["c5"]["tisch_sitze"] == 5 and got["c6"]["tisch_sitze"] == 6
    assert got["c5"]["tisch_text"] == "Tisch mit 5 Sitzen (Zufallsbasis 1/5)"
    assert got["c6"]["tisch_text"] == "Tisch mit 6 Sitzen (Zufallsbasis 1/6)"
    for sid in ("c5", "c6"):
        notes = got[sid]["hinweise"]
        assert isinstance(notes, list)
        # one family per table: each confirmation is alone in its family
        assert any(str(n).startswith("Holm-Familie: 1 Bestätigung(en)") for n in notes), notes
        assert got[sid]["stufe"] in (None, "R0", "R1")  # R2/R3 are not reachable
    # the same table (one table_hash) is one family of two
    a, b = _finding("a", table_hash="t5"), _finding("b", table_hash="t5", first_seed=600)
    same = _assess(a, b)
    assert any("Holm-Familie: 2 Bestätigung(en)" in str(n) for n in same["a"]["hinweise"])  # type: ignore[union-attr]


def test_an_unknown_table_size_stays_unknown_never_four() -> None:
    for value in (None, "5", 1, True):
        assert maturity.table_fields(value) == {
            "tisch_sitze": None,
            "tisch_text": "Tischgröße unbekannt",
        }, value


# -- the deck builder pages name the table size ------------------------------------------------


def test_the_history_row_the_diff_and_the_experiment_name_five_and_six_seats() -> None:
    out = _run_node(
        _UI
        + """
load('deckseries.js');
const E = require('./experiments.js');
const befund = (seats) => ({ stufe: 'R0', stufe_text: 'R0 Erkundung', urteil_text: 'nicht auswertbar', n: 25, N: 25,
  bezug: 'Paare (abgeschlossen / geplant)', stand: { bezug: 'aktuell', text: 'Befund zum aktuellen Stand' },
  empfehlungsfaehig: false, empfehlungsfaehig_gruende: ['Reifegrad unter R2'], hinweise: [],
  tisch_sitze: seats, tisch_text: seats ? `Tisch mit ${seats} Sitzen (Zufallsbasis 1/${seats})` : 'Tischgröße unbekannt' });
const item = (id, seats) => ({ series_id: id, base_ref: 'rev-a', variant_ref: 'rev-b', created_at: '2026-11-22T10:00:00', pod: 'precon',
  table_size: seats, status: 'completed', status_text: 'abgeschlossen', counts_as_result: true, pairs_planned: 25, pairs_completed: 25,
  pairs_attempted: 25, difference_pp: 4, difference_ci95_pp: null, decision_ci_pp: null, decision_level_pct: null, seeds: [1],
  tested_seats: [0, 1, 2, 3, 4], seats_planned: false, bridge_jar_sha256s: [], bridge_qualification_states: [], covered_by_sealed_epoch: null,
  pilots: [], slot_alignment_state: 'aligned', stop_reason: null });
const data = { series: [item('s5', 5), item('s6', 6), item('s0', null)], reifegrad: { befunde: { s5: befund(5), s6: befund(6), s0: befund(null) } } };
const diff = deckSeriesDiffEvidence(h, data, 'rev-a', 'rev-b');
const cells = deckSeriesCells(h, item('s6', 6), 'base', { open: () => {} }, new Map(), null, befund(6)).map(text);
process.stdout.write(JSON.stringify({
  ev5: text(deckSeriesEvidence(h, befund(5))), ev0: text(deckSeriesEvidence(h, befund(null))),
  diff: text(diff), cells,
  exp: [E.experimentTableText({ table: { seats: 5 } }), E.experimentTableText({ table: { seats: 6 } }), E.experimentTableText({ table: null })],
}));
"""
    )
    assert (
        "n/N 25 / 25 Paare (abgeschlossen / geplant) · Tisch mit 5 Sitzen (Zufallsbasis 1/5)"
        in str(out["ev5"])
    )
    assert "· Tischgröße unbekannt" in str(out["ev0"])
    diff = str(out["diff"])
    assert "Tisch precon · Tisch mit 5 Sitzen: A = Vergleichsbasis" in diff
    assert "Tisch precon · Tisch mit 6 Sitzen: A = Vergleichsbasis" in diff
    assert "Tisch precon · Tischgröße unbekannt: A = Vergleichsbasis" in diff
    cells = out["cells"]
    assert isinstance(cells, list)
    assert any("Tisch mit 6 Sitzen" in str(c) and "Sitze: 1, 2, 3, 4, 5" in str(c) for c in cells)
    assert out["exp"] == [
        "Tisch: 5 Sitze (Zufallsbasis 1/5, eigene Kohorte)",
        "Tisch: 6 Sitze (Zufallsbasis 1/6, eigene Kohorte)",
        "Tisch: Tischgröße unbekannt",
    ]


def test_the_card_evaluation_says_what_it_counted_for() -> None:
    out = _run_node(
        _UI
        + """
const K = require('./kartenauswertung.js');
process.stdout.write(JSON.stringify({ v: [5, 6, null].map((s) => K.outcomesCountedFor(s)) }));
"""
    )
    assert out["v"] == [
        "Gezählt für 5 Sitze",
        "Gezählt für 6 Sitze",
        "Gezählt für unbekannte Tischgröße",
    ]


@pytest.mark.parametrize(
    ("seats", "games", "half", "pct"), [(5, "383", "4", "20"), (6, "480", "3,33", "16,7")]
)
def test_the_plan_dialog_names_one_over_n_and_the_wilson_games(
    seats: int, games: str, half: str, pct: str
) -> None:
    plan = json.dumps(paired_series.table_plan(seats, seats * seats))
    four = json.dumps(paired_series.table_plan(4, 40))
    out = _run_node(
        _UI
        + "load('paired.js');\n"
        + f"const plan = {plan}; const four = {four};\n"
        + f"""process.stdout.write(JSON.stringify({{
  lines: planPairedLines(plan, 0), four: planPairedLines(four, 0),
  est: estimatePairedText({seats * seats}, 3, {seats}),
}}));
"""
    )
    lines, four_lines = out["lines"], out["four"]
    assert isinstance(lines, list) and isinstance(four_lines, list)
    assert (
        f"Referenz: Zufallsbasis 1/{seats} = {pct} % bei {seats} gleich starken Plätzen; ein "
        f"einzelner Siegrate-Anteil braucht {games} Partien für ±{half} pp (±20 % relativ"
    ) in lines[1]
    assert "25 %" not in lines[1] and "25 %" not in lines[2]
    assert f"Siegrate = Zufallsbasis 1/{seats}" in lines[2]
    assert "rund 800 Partien für ±3 pp" in four_lines[1]  # four seats: as before
    est = str(out["est"])
    assert est.startswith("Dauer: geschätzt ~") and "keine Untergrenze" in est
    assert "mindestens" not in est and "n = 10/10" in est


# -- end to end: a five- and a six-seat experiment of one deck, behind the lifted lock --------


def test_five_and_six_seat_experiments_reach_the_deck_builder_as_two_cohorts(
    lab: dict[str, object],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = lab["client"]
    revs = lab["revs"]
    assert isinstance(client, TestClient) and isinstance(revs, dict)

    def plan(seats: int, first: int) -> dict[str, object]:
        return {
            "schema": "studio-experiment-plan-1",
            "question": f"38 statt 40 Wälder an {seats} Sitzen",
            "question_kind": "axis",
            "deck_id": "chulane-b2",
            "base": {"revision_id": revs["base"]},
            "variants": [{"revision_id": revs["variant"]}],
            "table": {
                "seats": seats,
                "opponents": list(launch.pod_opponent_ids("precon", seats - 1)),
            },
            "purpose": "confirmation",
            "budget_pairs": seats * seats,
            "look_every_pairs": 100,
            "first_seed": first,
        }

    refused = client.post("/api/experiments", headers=HEADERS, json={"plan": plan(5, 400)})
    assert refused.status_code == 422 and "locked" in refused.text  # the shipped lock holds
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    started: dict[int, dict[str, object]] = {}
    for seats, first in ((5, 400), (6, 500)):
        res = client.post("/api/experiments", headers=HEADERS, json={"plan": plan(seats, first)})
        assert res.status_code == 200, res.text
        started[seats] = res.json()
        job = _finished(lab, str(started[seats]["series_id"]))
        assert job["estimate"]["duration_kind"] == "derived_estimate"  # type: ignore[index]
    answer = client.get("/api/decks/chulane-b2/series", headers=HEADERS).json()
    by_id = {item["series_id"]: item for item in answer["series"]}
    befunde = answer["reifegrad"]["befunde"]
    zahlen = {z["id"]: z for z in answer["zahlen"]}
    for seats in (5, 6):
        sid = str(started[seats]["series_id"])
        assert by_id[sid]["table_size"] == seats
        assert befunde[sid]["tisch_sitze"] == seats
        assert befunde[sid]["stufe"] in (None, "R0", "R1")  # never above R1 today
        assert f"Tisch mit {seats} Sitzen" in zahlen[f"series.{sid}.difference_pp"]["kohorte"]
        detail = client.get(
            f"/api/experiments/{started[seats]['experiment_id']}", headers=HEADERS
        ).json()
        assert detail["table"]["seats"] == seats
        assert detail["reifegrad"]["tisch_sitze"] == seats
        # one Holm family per table: the 5- and 6-seat confirmations never correct each other
        notes = befunde[sid]["hinweise"]
        assert any(str(n).startswith("Holm-Familie: 1 Bestätigung(en)") for n in notes), notes
