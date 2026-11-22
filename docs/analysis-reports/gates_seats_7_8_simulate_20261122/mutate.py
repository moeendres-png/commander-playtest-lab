"""Mutation run for #1672: each mutation must make the named tests fail; the file is restored after."""
import pathlib, subprocess, sys, json, os
ROOT = pathlib.Path("/home/user/s78mut")
T78 = "tests/unit/test_seats_7_8_simulate_1672.py"
T56 = "tests/unit/test_seats_5_6_simulate_1702.py"
CAP = "tests/unit/test_owner_player_cap.py"
WS = "tests/unit/test_ws223_cardinality_regression.py"
SG = "tests/unit/test_studio_static_guards.py"
EV = "tests/unit/test_seats56_evaluation.py"
M = [
 ("M01 SIMULATE lock 8->6", "src/commander_lab/studio/launch.py", "MAX_RELEASED_SEATS = 8\n", "MAX_RELEASED_SEATS = 6\n", [T78]),
 ("M02 SIMULATE lock 8->7", "src/commander_lab/studio/launch.py", "MAX_RELEASED_SEATS = 8\n", "MAX_RELEASED_SEATS = 7\n", [T78]),
 ("M03 code ceiling 8->6", "src/commander_lab/studio/launch.py", "MIN_SEATS, MAX_SEATS = 2, 8", "MIN_SEATS, MAX_SEATS = 2, 6", [T78]),
 ("M04 PLAY lock 6->8", "src/commander_lab/studio/launch.py", "MAX_RELEASED_PLAY_SEATS = 6\n", "MAX_RELEASED_PLAY_SEATS = 8\n", [T78, CAP]),
 ("M05 Partie cap 6->8", "src/commander_lab/studio/launch.py", "MAX_PARTIE_SEATS = 6\n", "MAX_PARTIE_SEATS = 8\n", [T78, CAP, SG]),
 ("M06 Partie check removed", "src/commander_lab/studio/launch.py", "    if others + 1 > MAX_PARTIE_SEATS:", "    if False:", [T78]),
 ("M07 runner MAX_PLAYERS 8->6", "src/commander_lab/engine/rules/full_game.py", "    MAX_PLAYERS = 8\n", "    MAX_PLAYERS = 6\n", [T78, CAP, WS]),
 ("M08 handshake accepts only 8", "src/commander_lab/engine/rules/full_game.py", "ACCEPTED_LANE_MAX_PLAYERS = (6, 8)", "ACCEPTED_LANE_MAX_PLAYERS = (8,)", [T78]),
 ("M09 handshake accepts 7 too", "src/commander_lab/engine/rules/full_game.py", "ACCEPTED_LANE_MAX_PLAYERS = (6, 8)", "ACCEPTED_LANE_MAX_PLAYERS = (6, 7, 8)", [T78]),
 ("M10 policy state bound 8->9", "src/commander_lab/engine/rules/full_game_pilot/state.py", "len(runtime_pilots) > 8:", "len(runtime_pilots) > 9:", [T78]),
 ("M11 pilot binding le=8->9", "src/commander_lab/engine/rules/full_game_pilot/common.py", "seat: int = Field(ge=1, le=8)", "seat: int = Field(ge=1, le=9)", [T78, WS]),
 ("M12 scenario model le=8->6", "src/commander_lab/candidates/models.py", "player_count: int = Field(ge=2, le=8)", "player_count: int = Field(ge=2, le=6)", [T78, CAP]),
 ("M13 deck_series back to 2..6", "src/commander_lab/studio/deck_series.py", "    planned = count if type(count) is int and MIN_SEATS <= count <= MAX_SEATS else None\n    seen", "    planned = count if type(count) is int and 2 <= count <= 6 else None\n    seen", [T78]),
 ("M14 baseline plan without 7/8", "src/commander_lab/studio/paired_series.py", "BASELINE_PLAN_SEATS = (5, 6, 7, 8)", "BASELINE_PLAN_SEATS = (5, 6)", [T78]),
 ("M15 page lock drifts to 6", "src/commander_lab/studio/static/paired.js", "const PAIRED_RELEASED_SEATS = 8;", "const PAIRED_RELEASED_SEATS = 6;", [T78, T56]),
 ("M16 preset shortened", "src/commander_lab/studio/launch.py", '        "precon/2023/divine_convocation",\n        "precon/2025/temur_roar",\n    ),\n    "mixed"', '        "precon/2023/divine_convocation",\n    ),\n    "mixed"', [T78]),
 ("M17 wall limit for 7 (pool opens)", "src/commander_lab/studio/table_spec.py", "{2: 1800.0, 3: 1800.0, 4: 1800.0}", "{2: 1800.0, 3: 1800.0, 4: 1800.0, 7: 1800.0}", [T78]),
 ("M18 Java MAX_PLAYERS 8->6", "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java", "static final int MAX_PLAYERS = 8;", "static final int MAX_PLAYERS = 6;", [T78]),
 ("M19 page reference drifts", "src/commander_lab/studio/static/paired.js", "8: [98.8, 65.7, 121.9,", "8: [98.7, 65.7, 121.9,", [T78]),
 ("M20 load_decks bound 8->9", "src/commander_lab/studio/play.py", "if not 2 <= len(paths) <= 8:", "if not 2 <= len(paths) <= 9:", [T78]),
 ("M21 comparison opponents 7->8", "src/commander_lab/engine/rules/full_game_comparison.py", "max_length=7)", "max_length=8)", [T78]),
 ("M22 duration warning dropped", "src/commander_lab/studio/paired_series.py", "        basis += \" \" + single_game_reference_text(size)\n", "        pass\n", [T78]),
]
env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
rows = []
for name, rel, old, new, tests in M:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (name, text.count(old))
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    try:
        run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                             cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
        killed = run.returncode != 0
        tail = (run.stdout.strip().splitlines() or [""])[-1]
    finally:
        path.write_text(text, encoding="utf-8")
    rows.append({"mutation": name, "file": rel, "killed": killed, "tail": tail})
    print(("KILLED  " if killed else "SURVIVED"), name, "|", tail, flush=True)
print(json.dumps({"killed": sum(r["killed"] for r in rows), "total": len(rows)}))
