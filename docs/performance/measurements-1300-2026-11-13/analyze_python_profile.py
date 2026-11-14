"""Issue #1300 (E5) step 1 analysis: bucket decomposition of the cProfile run.

Bucket rules (fixed before counting; every function in exactly one bucket):
  (1) Audit:    cumtime of engine/rules/full_game.py audit_actor_scoped_frame
                (armed per decision in _drive; subtree contains no pilot or
                recorder calls).
  (2) Pilot:    cumtime of engine/rules/full_game_pilot/policy.py decide
                (the pilot entry point; subtree = all pilot modules incl.
                the choices.py state SHA-256 via json.dumps+hashlib).
  (3) Recorder: cumtime of studio/games.py GameRecorder.record (subtree incl.
                frame_of + _write with json.dumps + flush per frame) plus
                GameRecorder.close and save_event_log (disjoint from record).
  (4) JSON read: cumtime of json.loads *only* where the direct caller is
                _RawFullGameClient.request in engine/rules/full_game.py
                (the bridge answers), taken from the pstats caller table.
  (5) Rest:     python process CPU (process_time of the run) minus (1)-(4).
Memo items (not buckets): json.dumps called from client.request (request
serialization), request cumtime minus its JSON parts (waiting on the bridge
inside queue.get), flush calls inside the recorder subtree.
"""

from __future__ import annotations

import csv
import json
import pstats
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find(stats: dict, *, suffix: str, name: str, line: int | None = None):
    out = []
    for (fn, ln, nm), val in stats.items():
        if fn.endswith(suffix) and nm == name and (line is None or ln == line):
            out.append(((fn, ln, nm), val))
    return out


def ct_of(entries) -> float:
    return sum(v[3] for _, v in entries)


def caller_ct(
    stats: dict, *, callee_suffix: str, callee_name: str, caller_suffix: str, caller_name: str
) -> float:
    total = 0.0
    for (fn, _ln, nm), val in stats.items():
        if fn.endswith(callee_suffix) and nm == callee_name:
            for (cfn, _cln, cnm), (_cc, _nc, _tt, ct) in val[4].items():
                if cfn.endswith(caller_suffix) and cnm == caller_name:
                    total += ct
    return total


def main() -> int:
    st = pstats.Stats(str(HERE / "full.pstats"))
    stats = st.stats
    total_tt = sum(v[2] for v in stats.values())

    result = json.loads((HERE / "full_result.json").read_text(encoding="utf-8"))
    games = result["games"]
    n_games = len(games)
    decisions = sum(g["decisions"] for g in games)
    py_cpu = result["python_process_cpu_s"]
    wall = result["total_wall_s"]
    children_cpu = result["children_cpu_s"]

    audit = ct_of(find(stats, suffix="engine/rules/full_game.py", name="audit_actor_scoped_frame"))
    pilot = ct_of(find(stats, suffix="full_game_pilot/policy.py", name="decide"))
    rec_record = ct_of(find(stats, suffix="studio/games.py", name="record"))
    rec_close = ct_of(find(stats, suffix="studio/games.py", name="close"))
    rec_events = ct_of(find(stats, suffix="studio/games.py", name="save_event_log"))
    recorder = rec_record + rec_close + rec_events
    frame_of = ct_of(find(stats, suffix="studio/games.py", name="frame_of"))
    rec_write = ct_of(find(stats, suffix="studio/games.py", name="_write"))

    json_read = caller_ct(
        stats,
        callee_suffix="json/__init__.py",
        callee_name="loads",
        caller_suffix="engine/rules/full_game.py",
        caller_name="request",
    )
    json_loads_total = ct_of(find(stats, suffix="json/__init__.py", name="loads"))
    dumps_from_request = caller_ct(
        stats,
        callee_suffix="json/__init__.py",
        callee_name="dumps",
        caller_suffix="engine/rules/full_game.py",
        caller_name="request",
    )
    dumps_from_choices = caller_ct(
        stats,
        callee_suffix="json/__init__.py",
        callee_name="dumps",
        caller_suffix="full_game_pilot/choices.py",
        caller_name="_decide_boolean",
    )
    request_ct = ct_of(find(stats, suffix="engine/rules/full_game.py", name="request"))
    request_tt = sum(
        v[2] for _, v in find(stats, suffix="engine/rules/full_game.py", name="request")
    )
    wait_in_request = request_ct - request_tt - json_read - dumps_from_request

    buckets = {
        "audit": audit,
        "pilot": pilot,
        "recorder": recorder,
        "json_read_bridge": json_read,
    }
    rest = py_cpu - sum(buckets.values())

    out = {
        "games": n_games,
        "decisions": decisions,
        "wall_s": wall,
        "python_process_cpu_s": py_cpu,
        "children_cpu_s": children_cpu,
        "cprofile_total_tottime_s": round(total_tt, 3),
        "buckets_s": {k: round(v, 3) for k, v in buckets.items()},
        "rest_s": round(rest, 3),
        "shares_of_python_cpu_pct": {k: round(100.0 * v / py_cpu, 2) for k, v in buckets.items()}
        | {"rest": round(100.0 * rest / py_cpu, 2)},
        "per_game_s": {k: round(v / n_games, 3) for k, v in buckets.items()}
        | {"rest": round(rest / n_games, 3), "python_cpu": round(py_cpu / n_games, 3)},
        "recorder_parts_s": {
            "record_incl_frame_of_and_write": round(rec_record, 3),
            "frame_of": round(frame_of, 3),
            "write_dumps_flush": round(rec_write, 3),
            "close_gzip": round(rec_close, 3),
            "save_event_log": round(rec_events, 3),
        },
        "memo_s": {
            "client_request_cumtime": round(request_ct, 3),
            "waiting_inside_request_derived": round(wait_in_request, 3),
            "json_loads_total_all_callers": round(json_loads_total, 3),
            "json_dumps_from_client_request": round(dumps_from_request, 3),
            "json_dumps_from_pilot_choices_state_hash": round(dumps_from_choices, 3),
        },
    }
    (HERE / "buckets.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    with (HERE / "buckets.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["bucket", "seconds_total", "seconds_per_game", "share_of_python_cpu_pct"])
        for k, v in buckets.items():
            w.writerow([k, round(v, 3), round(v / n_games, 3), round(100.0 * v / py_cpu, 2)])
        w.writerow(
            ["rest", round(rest, 3), round(rest / n_games, 3), round(100.0 * rest / py_cpu, 2)]
        )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
