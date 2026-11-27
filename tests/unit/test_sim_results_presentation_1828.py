"""Tests for #1828 Pakete 2, 3, 5 + Paket-1 P3 follow-ups:
- MODELED per-seat placements derived from winner_seats + players[].lost
- Draws explicit reporting, resumed-batch ETA (run_seeds_planned), cancelled badge/notes
- Paired series live interim A/B metrics, Delta-CI, 'echt vs. Zufall' verdict, Seed-Pair drilldown
- Strict separation from tierlist (simulation weight stays 0)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from commander_lab.models import RulesDeckInput
from commander_lab.studio import paired_comparison, paired_series, simulations

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "commander_lab" / "studio" / "static"


def _run_node(script: str) -> dict:
    proc = subprocess.run(
        ["node", "-"],
        input=script,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"node failed ({proc.returncode}):\n{proc.stderr}"
    return json.loads(proc.stdout)


def _write_sim_game(
    data_dir: Path,
    game_id: str,
    *,
    seed: int = 1,
    winner_seats: list[int] = (0,),
    frames: list[dict[str, object]] | None = None,
) -> None:
    games_dir = data_dir / "games"
    games_dir.mkdir(parents=True, exist_ok=True)
    header = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "game_id": game_id,
        "data_class": "SIMULATED_RESULT",
        "rules_authority": "xmage",
        "started_at": "2026-11-26T22:00:00Z",
        "seed": seed,
        "engine_commit": "1.4.62",
        "seats": [
            {"seat": s, "deck_id": f"deck_{s}", "commanders": [f"Cmd {s + 1}"]} for s in range(4)
        ],
    }
    lines = [json.dumps(header)]
    for idx, f in enumerate(frames or [], start=1):
        lines.append(json.dumps({"kind": "frame", "n": idx, **f}))
    lines.append(
        json.dumps(
            {
                "kind": "result",
                "status": "finished",
                "winner_seats": list(winner_seats),
                "decision_count": len(frames or []),
            }
        )
    )
    (games_dir / f"{game_id}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_modeled_placements_and_draws_in_telemetry_and_summary(tmp_path: Path) -> None:
    # Game 1: Seat 2 dies frame 1, Seat 3 dies frame 2, Seat 1 dies frame 3 -> Seat 0 wins (1, 2, 3, 4)
    _write_sim_game(
        tmp_path,
        "sim-p-1",
        seed=1,
        winner_seats=[0],
        frames=[
            {
                "turn": 3,
                "players": [
                    {"seat": 0, "lost": False},
                    {"seat": 1, "lost": False},
                    {"seat": 2, "lost": True},
                    {"seat": 3, "lost": False},
                ],
            },
            {
                "turn": 4,
                "players": [
                    {"seat": 0, "lost": False},
                    {"seat": 1, "lost": False},
                    {"seat": 2, "lost": True},
                    {"seat": 3, "lost": True},
                ],
            },
            {
                "turn": 5,
                "players": [
                    {"seat": 0, "lost": False},
                    {"seat": 1, "lost": True},
                    {"seat": 2, "lost": True},
                    {"seat": 3, "lost": True},
                ],
            },
        ],
    )
    # Game 2: simultaneous elimination of seats 2 & 3 -> ranks 1, 2, 2, 4? Seat 1 dies earlier (frame 1) -> rank 4; seats 2&3 tie at frame 2 -> both rank 2!
    _write_sim_game(
        tmp_path,
        "sim-p-2",
        seed=2,
        winner_seats=[0],
        frames=[
            {
                "turn": 2,
                "players": [
                    {"seat": 0, "lost": False},
                    {"seat": 1, "lost": True},
                    {"seat": 2, "lost": False},
                    {"seat": 3, "lost": False},
                ],
            },
            {
                "turn": 3,
                "players": [
                    {"seat": 0, "lost": False},
                    {"seat": 1, "lost": True},
                    {"seat": 2, "lost": True},
                    {"seat": 3, "lost": True},
                ],
            },
        ],
    )
    # Game 3: Draw (no winner_seats) & seat 3 never recorded lost=True -> only seat 1/2 lost recorded, seat 3 remains unknown
    _write_sim_game(
        tmp_path,
        "sim-p-3",
        seed=3,
        winner_seats=[],
        frames=[
            {
                "turn": 4,
                "players": [
                    {"seat": 0, "lost": False},
                    {"seat": 1, "lost": True},
                    {"seat": 2, "lost": False},
                    {"seat": 3, "lost": False},
                ],
            },
        ],
    )

    g1 = simulations.extract_game_log_telemetry(tmp_path, "sim-p-1")
    g2 = simulations.extract_game_log_telemetry(tmp_path, "sim-p-2")
    g3 = simulations.extract_game_log_telemetry(tmp_path, "sim-p-3")

    assert g1.seat_placements == {0: 1, 1: 2, 3: 3, 2: 4}
    assert g2.seat_placements == {0: 1, 2: 2, 3: 2, 1: 4}
    # Game 3 was a 4-seat draw where only seat 1 lost -> seats 0, 2, 3 outlived seat 1 (rank 4) and stay unknown
    assert g3.seat_placements == {1: 4}

    agg = simulations.aggregate_batch_results(
        [g1, g2, g3],
        table_size=4,
        seat_labels=["chulane", "opp1", "opp2", "opp3"],
    )
    assert agg["draws"] == 1
    pm = agg["placements_modeled"]
    assert isinstance(pm, dict)
    assert pm["data_class"] == "MODELED"
    assert "players[].lost" in str(pm["provenance"])
    assert pm["games"] == 3
    by_seat = pm["by_seat"]
    assert isinstance(by_seat, list) and len(by_seat) == 4
    assert by_seat[0]["label"] == "chulane"
    # Seat 1 (index 0): 1st twice, unknown once (in draw)
    assert by_seat[0]["ranks"]["1"] == 2
    assert by_seat[0]["unknown"] == 1

    interim = simulations.interim_batch_summary([g1, g2, g3], games_planned=10, table_size=4)
    assert interim["draws"] == 1
    assert isinstance(interim["placements_modeled"], dict)
    assert interim["placements_modeled"]["data_class"] == "MODELED"


def test_resumed_batch_exposes_run_seeds_planned_for_accurate_eta(tmp_path: Path) -> None:
    initial = [
        simulations.GameSummary("b1-s1", 1, "finished", winner_seats=[0]),
        simulations.GameSummary("b1-s2", 2, "finished", winner_seats=[1]),
    ]
    batch = simulations.BatchSimulation(
        batch_id="b1",
        data_folder=tmp_path,
        deck_id="chulane",
        revision_id="r1",
        pod_name="precon",
        opponent_paths=[],
        seeds=[1, 2, 3, 4, 5, 6],
        initial_games=initial,
    )
    live_dict = batch.to_dict(live=True)
    saved_dict = batch.to_dict(live=False)
    assert live_dict["run_seeds_planned"] == 4
    assert "run_seeds_planned" not in saved_dict


def test_paired_series_live_interim_ab_delta_and_seed_pairs(tmp_path: Path) -> None:
    def _deck(deck_id: str) -> RulesDeckInput:
        return RulesDeckInput(
            deck_id=deck_id,
            name=deck_id,
            commander_names=("Chulane, Teller of Tales",),
            mainboard=("Forest",) * 99,
        )

    preloaded: dict[tuple[str, int, int], paired_comparison.PlayedGame] = {
        ("base", 10, 0): {
            "exposure": {
                "game_id": "g-b-10",
                "seed": 10,
                "winner_seats": [1],
                "seats": [],
                "table_size": 4,
                "pilot": "p",
                "decision_policy": "d",
                "engine_commit": "e",
                "bridge_jar_sha256": "abc",
                "bridge_qualification_state": "BRIDGE_ALIGNED",
                "covered_by_sealed_epoch": True,
                "pilot_fingerprint": "fp",
            },
            "failure_class": None,
        },
        ("variant", 10, 0): {
            "exposure": {
                "game_id": "g-v-10",
                "seed": 10,
                "winner_seats": [0],
                "seats": [],
                "table_size": 4,
                "pilot": "p",
                "decision_policy": "d",
                "engine_commit": "e",
                "bridge_jar_sha256": "abc",
                "bridge_qualification_state": "BRIDGE_ALIGNED",
                "covered_by_sealed_epoch": True,
                "pilot_fingerprint": "fp",
            },
            "failure_class": None,
        },
        ("base", 11, 0): {
            "exposure": {
                "game_id": "g-b-11",
                "seed": 11,
                "winner_seats": [2],
                "seats": [],
                "table_size": 4,
                "pilot": "p",
                "decision_policy": "d",
                "engine_commit": "e",
                "bridge_jar_sha256": "abc",
                "bridge_qualification_state": "BRIDGE_ALIGNED",
                "covered_by_sealed_epoch": True,
                "pilot_fingerprint": "fp",
            },
            "failure_class": None,
        },
        ("variant", 11, 0): {
            "exposure": {
                "game_id": "g-v-11",
                "seed": 11,
                "winner_seats": [0],
                "seats": [],
                "table_size": 4,
                "pilot": "p",
                "decision_policy": "d",
                "engine_commit": "e",
                "bridge_jar_sha256": "abc",
                "bridge_qualification_state": "BRIDGE_ALIGNED",
                "covered_by_sealed_epoch": True,
                "pilot_fingerprint": "fp",
            },
            "failure_class": None,
        },
    }

    job = paired_series.PairedSeriesJob(
        series_id="p-live-test",
        data_folder=tmp_path,
        base_ref="repo:main",
        variant_ref="rev@chulane",
        base_deck=_deck("chulane--base"),
        variant_deck=_deck("chulane--variant"),
        opponents=[_deck("opp1"), _deck("opp2"), _deck("opp3")],
        paths_by_deck_id={},
        pod_name="precon",
        seeds=[10, 11, 12, 13],
        tested_seats=[0],
        budget_pairs=4,
        look_every_pairs=4,
        threshold_pp=0.0,
        significance_level=0.05,
        preloaded_games=preloaded,
    )
    job.status = "running"
    job.run_started_at = "2026-11-26T22:00:00Z"

    live = job.to_dict(live=True)
    saved = job.to_dict(live=False)

    assert live["summary_partial"] is True
    assert "summary_partial" not in saved
    assert "interim_comparison" not in saved
    assert "seed_pairs" not in saved

    ic = live["interim_comparison"]
    assert isinstance(ic, dict)
    assert ic["data_class"] == "SIMULATED_RESULT"
    assert ic["pairs_completed"] == 2
    assert ic["base_rate"] == 0.0 and ic["variant_rate"] == 1.0
    assert ic["difference_pp"] == 100.0
    assert ic["variant_only_wins"] == 2 and ic["baseline_only_wins"] == 0

    pairs = live["seed_pairs"]
    assert isinstance(pairs, list) and len(pairs) == 2
    assert pairs[0]["base_game_id"] == "g-b-10" and pairs[0]["variant_game_id"] == "g-v-10"
    assert pairs[0]["difference"] == 1.0


def test_paired_and_app_js_render_ab_card_seed_table_and_placements() -> None:
    paired_js = (STATIC / "paired.js").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    app_src = app_js[app_js.index("// BEGIN batch-interim") : app_js.index("// END batch-interim")]

    # Keep tierlist simulation weight strictly 0 (verified in queries/tierlist)
    tierlist_js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert "interim_summary" not in tierlist_js and "placements_modeled" not in tierlist_js

    # Node test for paired.js A/B Decision card + Seed-Pair table & app.js resumed ETA
    out = _run_node(
        f"""
const StudioUI = {{
  num: (v, d = 0) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)))
    ? "unbekannt" : Number(v).toLocaleString("de-DE", {{minimumFractionDigits: d, maximumFractionDigits: d}}),
  numFlex: (v, d = 2) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)))
    ? "unbekannt" : Number(v).toLocaleString("de-DE", {{maximumFractionDigits: d}}),
  renderErrorCard: () => ({{ tag: "div", children: [] }}),
  classifyError: () => ({{ title: "E", sentence: "S", actions: [] }})
}};
const makeNode = (tag, props, ...kids) => ({{
  tag, props: props || {{}},
  children: kids.flat().filter(Boolean),
  get textContent() {{
    return this.children.map(c => typeof c === "string" || typeof c === "number" ? String(c) : c.textContent).join(" ");
  }},
  append(...more) {{ this.children.push(...more.flat().filter(Boolean)); }}
}});
const document = {{ getElementById: () => null }};

{app_src}
{paired_js}

// Check resumed ETA accuracy with run_seeds_planned=12 (2 done of 12 left -> 10 left = 50 min at 12/h)
const eta = batchPaceEta({{
  run_started_at: "2026-11-26T22:00:00Z",
  observed_at: "2026-11-26T22:10:00Z",
  games_played: 10,
  games_played_at_run_start: 8,
  games_planned: 20,
  run_seeds_planned: 12,
  interim_summary: {{ games_failed: 0 }},
  games_failed: 4
}});

const mon = renderPairedMonitor(makeNode, {{
  series_id: "p1",
  status: "cancelled",
  pod: "precon",
  base_ref: "repo:main",
  variant_ref: "rev@b",
  budget_pairs: 20,
  pairs_attempted: 5,
  games_played: 10,
  games_planned_max: 40,
  interim_comparison: {{
    pairs_completed: 5,
    pairs_budget: 20,
    pairs_censored: 0,
    base_rate: 0.2,
    variant_rate: 0.6,
    base_ci95_pp: [3.6, 62.4],
    variant_ci95_pp: [23.1, 88.2],
    difference_pp: 40.0,
    difference_ci95_pp: [-5.0, 85.0],
    variant_only_wins: 2,
    baseline_only_wins: 0,
    tied_pairs: 3
  }},
  seed_pairs: [
    {{ seed: 100, seat: 1, base_game_id: "g-a-100", variant_game_id: "g-b-100", base_credit: 0, variant_credit: 1, difference: 1, status: "paired" }}
  ]
}}, {{ api: async () => ({{}}), fail: () => {{}}, setActivePaired: () => {{}}, pollPaired: () => {{}} }});

const notDecidedFlag = pairedTruthBadge({{ status: "NOT_DECIDED" }}, false);
const decidedAboveFlag = pairedTruthBadge({{ status: "DECIDED", answer: "ABOVE" }}, false);
const decidedNotAboveFlag = pairedTruthBadge({{ status: "DECIDED", answer: "NOT_ABOVE" }}, false);
const decidedNotAboveThresholdFlag = pairedTruthBadge({{ status: "DECIDED", answer: "NOT_ABOVE", question: {{ threshold_pp: 20 }} }}, false);
const noPairsFlag = pairedTruthBadge({{ status: "NO_PAIRS" }}, false);

console.log(JSON.stringify({{
  etaSeconds: Math.round(eta.etaSeconds),
  perHour: Math.round(eta.perHour),
  monText: mon.textContent,
  notDecidedFlag,
  decidedAboveFlag,
  decidedNotAboveFlag,
  decidedNotAboveThresholdFlag,
  noPairsFlag
}}));
"""
    )

    assert out["perHour"] == 12
    # 10 remaining of 12 at 2 games per 10 min -> 50 min = 3000s (previously was 2400s if subtracting prior failures)
    assert out["etaSeconds"] == 3000
    # a stop before the first look has no Teilergebnis (it means the last look, #1872 review):
    # the pairs played up to the stop are shown as a separate descriptive block
    assert "Kein Teilergebnis (vor dem ersten Look gestoppt" in out["monText"]
    assert (
        "Beschreibend, alle bis zum Stopp gespielten Paare (ungeplant): 5 / 20 Paare"
        in out["monText"]
    )
    assert "Paar-Teilergebnis" not in out["monText"]
    assert "ungeplanter Stopp" in out["monText"]
    assert "Seed-Paartabelle" in out["monText"]
    assert "Replay A" in out["monText"] and "Replay B" in out["monText"]
    assert "Zufall nicht ausgeschlossen" in out["notDecidedFlag"][1]
    assert "Hinweis auf echten Unterschied" in out["decidedAboveFlag"][1]
    assert "Kein ausreichender Vorteil" in out["decidedNotAboveFlag"][1]
    assert "B nicht über A" in out["decidedNotAboveFlag"][1]
    # NOT_ABOVE at a non-zero threshold names the question it answers, like ABOVE does
    assert "Kein ausreichender Vorteil" in out["decidedNotAboveThresholdFlag"][1]
    assert "Frage „größer als" in out["decidedNotAboveThresholdFlag"][1]
    assert "mit nein beantwortet" in out["decidedNotAboveThresholdFlag"][1]
    assert "Keine auswertbaren Paare" in out["noPairsFlag"][1]


def test_simulation_tierlist_weight_remains_zero() -> None:
    store_py = (ROOT / "src" / "commander_lab" / "studio" / "queries.py").read_text(
        encoding="utf-8"
    )
    # Also confirm AGENTS rule/regression check on tierliste never reads simulation results
    tierlist_js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    partie_js = (STATIC / "partie.js").read_text(encoding="utf-8")
    assert "placements_modeled" not in store_py
    assert "placements_modeled" not in tierlist_js
    assert "function renderReplayTimeline()" in partie_js
