"""The batching qualification: its plan, its instruments and, above all, its verdict.

A qualification that cannot fail proves nothing, so most tests here are negative controls: a
report in which one hash differs, one batch is missing, one game timed out, memory grows or a
fault never fired must not be a PASS, and only a hash that differs may be a FAIL.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "qualify_game_batching", ROOT / "scripts/qualify_game_batching.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


Q = _load()


# --- a synthetic report -------------------------------------------------------------------------


def _hash(game: str) -> str:
    return hashlib.sha256(game.removesuffix(Q.BAD_DECK_SUFFIX).encode()).hexdigest()


def _samples(games: int, live_mib: float = 600.0, growth: float = 0.0, rss_gib: float = 1.2):
    rows = []
    for index in range(1, games + 1):
        jitter = (index * 7 % 5 - 2) * 3.0  # +-6 MiB: the noise of a real run is of this size
        live = (live_mib + growth * index + jitter) * 1024
        for when in ("start", "end"):
            rows.append(
                {
                    "game": index,
                    "when": when,
                    "live_kib": int(live + (200 * 1024 if when == "end" else 0)),
                    "rss_kib": int(rss_gib * 1024 * 1024),
                    "hwm_kib": int(rss_gib * 1024 * 1024),
                }
            )
    return rows


def _record(spec: Any, **memory: Any) -> dict[str, Any]:
    fault = asdict(spec.fault) if spec.fault else None
    rows = []
    for position, game in enumerate(spec.games):
        failed = Q.is_bad_deck(game) or (fault is not None and position == fault["position"])
        row: dict[str, Any] = {"position": position, "game": game}
        if failed:
            row |= {"status": "failed", "error": "BridgeError: planned"}
        else:
            row |= {"status": "ok", "semantic": _hash(game), "decisions": 100, "winners": [0]}
        rows.append(row)
    record: dict[str, Any] = {
        "name": spec.name,
        "phase": spec.phase,
        "games": list(spec.games),
        "rows": rows,
        "fault": fault,
        "wall_s": 1.0,
    }
    if spec.fault:
        record["fault_fired"] = True
    if spec.sample_memory:
        record["memory"] = _samples(len(spec.games), **memory)
    return record


def _report(**memory: Any) -> dict[str, Any]:
    plan = Q.build_plan()
    return {
        "schema": Q.SCHEMA,
        "pool": list(Q.POOL),
        "plan": [asdict(spec) | {"games": list(spec.games)} for spec in plan],
        "batches": {spec.name: _record(spec, **memory) for spec in plan},
    }


def _verdict(report: dict[str, Any]) -> dict[str, Any]:
    return Q.evaluate(copy.deepcopy(report))


def test_a_complete_clean_report_passes_every_property() -> None:
    result = _verdict(_report())
    assert {name: result[name]["status"] for name in ("reference", *Q.PROPERTIES)} == dict.fromkeys(
        ("reference", *Q.PROPERTIES), Q.PASS
    )
    assert result["overall"] == Q.PASS


# --- negative controls: the verdict ------------------------------------------------------------


@pytest.mark.parametrize(
    ("batch", "prop"),
    [
        ("rotation-3", "positions"),
        ("reverse", "permutations"),
        ("chunk5-1", "permutations"),
        ("memory", "memory"),
    ],
)
def test_one_hash_that_differs_fails_its_property(batch: str, prop: str) -> None:
    report = _report()
    report["batches"][batch]["rows"][-1]["semantic"] = "0" * 64
    result = _verdict(report)
    assert result[prop]["status"] == Q.FAIL
    assert result["overall"] == Q.FAIL


def test_a_game_that_took_another_games_place_is_seen() -> None:
    """Two games swapping results is a difference, not a pass by count."""
    report = _report()
    rows = report["batches"]["rotation-0"]["rows"]
    rows[0]["semantic"], rows[1]["semantic"] = rows[1]["semantic"], rows[0]["semantic"]
    assert _verdict(report)["positions"]["status"] == Q.FAIL


def test_a_missing_batch_is_inconclusive_never_a_pass() -> None:
    report = _report()
    del report["batches"]["rotation-5"]
    result = _verdict(report)
    assert result["positions"]["status"] == Q.INCONCLUSIVE
    assert "rotation-5" in result["positions"]["unplayed"]
    assert result["overall"] == Q.INCONCLUSIVE


def test_a_game_that_failed_by_infrastructure_is_inconclusive_not_a_difference() -> None:
    report = _report()
    row = report["batches"]["shuffle-1"]["rows"][2]
    row.clear()
    row |= {"position": 2, "game": "x", "status": "failed", "error": "DECISION_ADVANCE_TIMEOUT"}
    result = _verdict(report)
    assert result["permutations"]["status"] == Q.INCONCLUSIVE
    assert result["overall"] == Q.INCONCLUSIVE


def test_a_position_nobody_compared_is_inconclusive() -> None:
    report = _report()
    for name in ("rotation-1", "rotation-2"):  # every game loses two of its eight positions
        report["batches"][name]["rows"] = report["batches"][name]["rows"][:0]
    result = _verdict(report)
    assert result["positions"]["status"] == Q.INCONCLUSIVE
    assert any("never compared at position" in line for line in result["positions"]["open"])


def test_a_reference_that_differs_from_itself_fails_before_any_comparison() -> None:
    report = _report()
    report["batches"]["ref-b-real:2"]["rows"][0]["semantic"] = "f" * 64
    result = _verdict(report)
    assert result["reference"]["status"] == Q.FAIL
    assert result["overall"] == Q.FAIL


def test_a_reference_game_that_was_not_played_twice_is_inconclusive() -> None:
    report = _report()
    del report["batches"]["ref-b-real:1"]
    result = _verdict(report)
    assert result["reference"]["status"] == Q.INCONCLUSIVE
    assert result["overall"] == Q.INCONCLUSIVE


def test_two_pool_games_with_one_hash_would_hide_a_swap_and_are_refused() -> None:
    report = _report()
    for twin in ("a", "b"):
        report["batches"][f"ref-{twin}-real:2"]["rows"][0]["semantic"] = _hash("real:1")
    assert _verdict(report)["reference"]["status"] == Q.INCONCLUSIVE


# memory


def test_a_flat_live_set_with_noise_passes() -> None:
    assert _verdict(_report(growth=0.0))["memory"]["status"] == Q.PASS


def test_a_live_set_that_grows_two_mib_per_game_fails() -> None:
    result = _verdict(_report(growth=2.0))["memory"]
    assert result["status"] == Q.FAIL
    assert result["grows"]


def test_a_leak_of_a_whole_finished_game_per_game_fails_loudly() -> None:
    result = _verdict(_report(growth=40.0))["memory"]
    assert result["status"] == Q.FAIL
    assert result["live_slope_mib_per_game"] > 30


def test_growth_just_under_the_slope_limit_passes() -> None:
    assert _verdict(_report(growth=0.8, live_mib=2000.0))["memory"]["status"] == Q.PASS


def test_a_jvm_that_ends_above_the_rss_ceiling_fails() -> None:
    assert _verdict(_report(rss_gib=3.5))["memory"]["status"] == Q.FAIL


def test_unsampled_memory_is_inconclusive() -> None:
    report = _report()
    for sample in report["batches"]["memory"]["memory"]:
        sample.pop("live_kib")
    assert _verdict(report)["memory"]["status"] == Q.INCONCLUSIVE


def test_fewer_than_fifty_games_in_one_jvm_is_not_the_claim() -> None:
    report = _report()
    batch = report["batches"]["memory"]
    for key in ("games", "rows", "memory"):
        batch[key] = batch[key][: 2 * 40 if key == "memory" else 40]
    result = _verdict(report)["memory"]
    assert result["status"] == Q.INCONCLUSIVE
    assert any("at least 50" in line for line in result["open"])


# isolation


@pytest.mark.parametrize("batch", ["isolation-bad-deck-0", "isolation-kill-1", "isolation-stop-2"])
def test_a_neighbour_that_changed_after_a_failure_fails_isolation(batch: str) -> None:
    report = _report()
    rows = report["batches"][batch]["rows"]
    neighbour = next(row for row in rows if row["status"] == "ok")
    neighbour["semantic"] = "0" * 64
    assert _verdict(report)["isolation"]["status"] == Q.FAIL


def test_a_broken_game_that_still_played_fails_isolation() -> None:
    report = _report()
    row = report["batches"]["isolation-bad-deck-1"]["rows"][1]
    row |= {"status": "ok", "semantic": "1" * 64}
    assert _verdict(report)["isolation"]["status"] == Q.FAIL


def test_a_fault_that_never_fired_proves_nothing() -> None:
    report = _report()
    report["batches"]["isolation-kill-2"]["fault_fired"] = False
    result = _verdict(report)["isolation"]
    assert result["status"] == Q.INCONCLUSIVE
    assert any("never fired" in line for line in result["open"])


def test_a_neighbour_lost_to_infrastructure_is_inconclusive() -> None:
    report = _report()
    report["batches"]["isolation-kill-0"]["rows"][2] |= {"status": "failed", "error": "TIMEOUT"}
    assert _verdict(report)["isolation"]["status"] == Q.INCONCLUSIVE


def test_the_verdict_command_reads_a_report_file(tmp_path: Path, capsys) -> None:
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(_report()), encoding="utf-8")
    broken = _report()
    broken["batches"]["reverse"]["rows"][0]["semantic"] = "0" * 64
    bad.write_text(json.dumps(broken), encoding="utf-8")
    assert Q.main(["verdict", str(good)]) == 0
    assert "BATCHING QUALIFICATION PASS" in capsys.readouterr().out
    assert Q.main(["verdict", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "BATCHING QUALIFICATION FAIL" in out and "reverse[0]" in out


# --- the plan ----------------------------------------------------------------------------------


def test_every_game_stands_at_every_position_once_in_the_rotations() -> None:
    orders = Q.rotations(Q.POOL)
    assert len(orders) == len(Q.POOL)
    for game in Q.POOL:
        assert sorted(order.index(game) for order in orders) == list(range(len(Q.POOL)))


def test_shuffles_are_reproducible_and_differ_from_forward_and_reverse() -> None:
    first = Q.shuffled(Q.POOL, "shuffle-1")
    assert first == Q.shuffled(Q.POOL, "shuffle-1")
    assert sorted(first) == sorted(Q.POOL)
    assert len({first, Q.shuffled(Q.POOL, "shuffle-2"), Q.POOL, tuple(reversed(Q.POOL))}) == 4


def test_the_memory_batch_plays_every_game_once_per_pass_in_one_jvm() -> None:
    sequence = Q.memory_sequence(Q.POOL, Q.MEMORY_PASSES)
    assert len(sequence) == Q.MEMORY_PASSES * len(Q.POOL) >= 50
    size = len(Q.POOL)
    passes = [sequence[i : i + size] for i in range(0, len(sequence), size)]
    assert all(sorted(p) == sorted(Q.POOL) for p in passes)
    assert len(set(passes)) == len(passes), "every pass has a different order"
    memory = next(spec for spec in Q.build_plan() if spec.name == "memory")
    assert memory.games == sequence and memory.games_per_jvm == len(sequence)
    assert memory.sample_memory


def test_the_reference_is_the_evidence_lane_launch_played_twice() -> None:
    plan = Q.build_plan()
    reference = [spec for spec in plan if spec.phase == "reference"]
    assert len(reference) == 2 * len(Q.POOL)
    assert {spec.games for spec in reference} == {(game,) for game in Q.POOL}
    assert all(
        spec.games_per_jvm == 1 and not spec.fast and spec.fault is None for spec in reference
    )
    others = [spec for spec in plan if spec.phase != "reference"]
    assert all(spec.games_per_jvm == len(spec.games) and spec.fast for spec in others)


def test_the_plan_names_are_unique_and_every_phase_is_planned() -> None:
    plan = Q.build_plan()
    assert len({spec.name for spec in plan}) == len(plan)
    assert {spec.phase for spec in plan} == {
        "reference",
        "positions",
        "permutations",
        "memory",
        "isolation",
    }


def test_a_failure_is_planned_at_the_first_middle_and_last_position_of_every_kind() -> None:
    isolation = [spec for spec in Q.build_plan() if spec.phase == "isolation"]
    kinds: dict[str, set[int]] = {}
    for spec in isolation:
        assert len(spec.games) == 3
        if spec.fault:
            kinds.setdefault(spec.fault.kind, set()).add(spec.fault.position)
        else:
            broken = [i for i, game in enumerate(spec.games) if Q.is_bad_deck(game)]
            assert len(broken) == 1
            kinds.setdefault("bad-deck", set()).add(broken[0])
    assert kinds == {"bad-deck": {0, 1, 2}, "kill": {0, 1, 2}, "stop": {0, 1, 2}}


def test_the_chunk_batches_cover_the_pool_in_order() -> None:
    plan = {spec.name: spec for spec in Q.build_plan()}
    for size, count in ((3, 3), (5, 2)):
        joined = tuple(g for n in range(count) for g in plan[f"chunk{size}-{n}"].games)
        assert joined == Q.POOL


def test_a_game_name_round_trips() -> None:
    assert Q.game_key("coverage-2:1") == ("coverage-2", 1)
    assert Q.game_key("real:3" + Q.BAD_DECK_SUFFIX) == ("real", 3)
    assert Q.is_bad_deck("real:3" + Q.BAD_DECK_SUFFIX) and not Q.is_bad_deck("real:3")


# --- the launch command ---------------------------------------------------------------------------


def test_only_batches_set_the_property_and_only_when_asked_the_fast_flags(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"")
    plan = {spec.name: spec for spec in Q.build_plan()}
    env = Q.Environment(jar=jar, setups={}, fast=True)
    prop = f"-D{Q.bench.GAMES_PER_JVM_PROPERTY}"
    reference = Q._command(env, plan["ref-a-real:1"])
    assert reference == ("java", "-jar", str(jar), "full-game")
    batched = Q._command(env, plan["rotation-2"])
    assert "-XX:+UseSerialGC" in batched and f"{prop}=8" in batched
    assert f"{prop}=56" in Q._command(env, plan["memory"])
    slow = Q.Environment(jar=jar, setups={}, fast=False)
    assert "-XX:+UseSerialGC" not in Q._command(slow, plan["rotation-2"])


# --- the instruments ---------------------------------------------------------------------------


_SERIAL = """\
 def new generation   total 78656K, used 21K [0x1, 0x2, 0x3)
  eden space 69952K,   0% used [0x1, 0x2, 0x3)
 tenured generation   total 174784K, used 3201K [0x4, 0x5, 0x6)
   the space 174784K,   1% used [0x4, 0x5, 0x6)
 Metaspace       used 3190K, committed 3328K, reserved 1056768K
"""
_G1 = """\
 garbage-first heap   total 262144K, used 5424K [0x1, 0x2)
  region size 1024K, 3 young (3072K), 0 survivors (0K)
 Metaspace       used 3190K, committed 3328K, reserved 1056768K
"""


def test_heap_info_is_read_for_serial_and_g1_and_refused_otherwise() -> None:
    assert Q.parse_heap_info(_SERIAL) == {"live_kib": 21 + 3201, "metaspace_kib": 3190}
    assert Q.parse_heap_info(_G1) == {"live_kib": 5424, "metaspace_kib": 3190}
    assert Q.parse_heap_info("Unable to open socket file") is None
    assert Q.parse_heap_info(_G1.replace("Metaspace", "Meta")) is None


def test_process_memory_is_read_from_proc_and_a_missing_process_gives_nothing() -> None:
    status = Q.read_proc_status(os.getpid())
    assert status["rss_kib"] > 0 and status["hwm_kib"] >= status["rss_kib"]
    assert Q.read_proc_status(2**22 + 12345) == {}


class _Process:
    def __init__(self, pid: int) -> None:
        self.pid = pid


class _Client:
    def __init__(self, pid: int) -> None:
        self._process = _Process(pid)


def _sleeper() -> subprocess.Popen[bytes]:
    return subprocess.Popen(["sleep", "60"])


def _state(pid: int) -> str:
    text = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    return next(line.split()[1] for line in text.splitlines() if line.startswith("State:"))


def _decisions(hook: Any, client: _Client, count: int, *, create: bool = True) -> None:
    if create:
        hook.before(client, "create_full_game", {})
    for _ in range(count):
        hook.before(client, Q.DECISION_REQUEST, None)


def test_a_kill_fault_kills_the_jvm_of_the_chosen_game_at_the_chosen_decision() -> None:
    victim = _sleeper()
    try:
        hook = Q.FaultHook(Q.Fault("kill", position=1, after_decisions=3))
        client = _Client(victim.pid)
        _decisions(hook, client, 10)  # game 0: untouched
        assert victim.poll() is None and not hook.fired
        hook.before(client, "create_full_game", {})
        _decisions(hook, client, 2, create=False)
        assert victim.poll() is None, "not yet at decision 3 of game 1"
        _decisions(hook, client, 1, create=False)
        assert victim.wait(timeout=10) == -signal.SIGKILL and hook.fired
        _decisions(hook, client, 5, create=False)  # fires once only
    finally:
        victim.kill()


def test_a_stop_fault_hangs_the_jvm_and_cleanup_removes_it() -> None:
    victim = _sleeper()
    try:
        hook = Q.FaultHook(Q.Fault("stop", position=0, after_decisions=1))
        _decisions(hook, _Client(victim.pid), 1)
        for _ in range(100):
            if _state(victim.pid) == "T":
                break
            time.sleep(0.05)
        assert _state(victim.pid) == "T"
        hook.cleanup()
        assert victim.wait(timeout=10) == -signal.SIGKILL
        hook.cleanup()  # a process that is gone is not an error
    finally:
        victim.kill()


def test_the_memory_hook_samples_every_game_start_and_end() -> None:
    seen: list[int] = []

    def live_set(pid: int) -> dict[str, int]:
        seen.append(pid)
        return {"live_kib": 1000 + len(seen), "metaspace_kib": 5}

    hook = Q.MemoryHook(live_set)
    client = _Client(os.getpid())
    for _ in range(3):
        hook.after(client, "create_full_game", {})
        hook.after(client, Q.DECISION_REQUEST, {})
        hook.after(client, "shutdown_game", {})
    assert [(s["game"], s["when"]) for s in hook.samples] == [
        (1, "start"),
        (1, "end"),
        (2, "start"),
        (2, "end"),
        (3, "start"),
        (3, "end"),
    ]
    assert all(s["rss_kib"] > 0 and s["live_kib"] > 1000 for s in hook.samples)


def test_requests_pass_through_the_hook_of_their_thread_and_the_patch_is_undone(
    monkeypatch,
) -> None:
    class FakeClient:
        def request(self, message_type, payload=None):
            return {"echo": message_type}

    monkeypatch.setattr(Q.full_game, "_RawFullGameClient", FakeClient)
    original = FakeClient.request
    events: list[tuple[str, str]] = []

    class Spy(Q.Hook):
        def before(self, client, message_type, payload):
            events.append(("before", message_type))

        def after(self, client, message_type, response):
            events.append(("after", response["echo"]))

    with Q.instrumented_requests():
        assert FakeClient().request("a") == {"echo": "a"}  # no hook on this thread: untouched
        Q._HOOKS.current = Spy()
        try:
            assert FakeClient().request("b") == {"echo": "b"}
        finally:
            Q._HOOKS.current = None
    assert events == [("before", "b"), ("after", "b")]
    assert FakeClient.request is original


def test_the_patch_is_undone_when_the_run_raises(monkeypatch) -> None:
    class FakeClient:
        def request(self, message_type, payload=None):
            return {}

    monkeypatch.setattr(Q.full_game, "_RawFullGameClient", FakeClient)
    original = FakeClient.request
    with pytest.raises(RuntimeError), Q.instrumented_requests():
        raise RuntimeError("boom")
    assert FakeClient.request is original


# --- playing a batch (runner faked) -------------------------------------------------------------


class _Deck:
    def __init__(self, mainboard: tuple[str, ...], card_printings: tuple[str, ...] = ("p",)):
        self.mainboard = mainboard
        self.card_printings = card_printings

    def model_copy(self, update: dict[str, Any]) -> _Deck:
        return _Deck(
            update.get("mainboard", self.mainboard),
            update.get("card_printings", self.card_printings),
        )


class _Scenario:
    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def model_copy(self, update: dict[str, Any]) -> _Scenario:
        return _Scenario(update["seed"])


class _Result:
    def __init__(self, seed: int) -> None:
        self.semantic_transcript_sha256 = f"h{seed}"
        self.decision_count = 7
        self.winner_seats = (0,)


def _environment(tmp_path: Path) -> Any:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"")
    decks = tuple(_Deck(tuple(f"card{i}" for i in range(20))) for _ in range(4))
    pods = {Q.game_key(game)[0] for game in Q.POOL}
    setups = {pod: (_Scenario(), decks, "pilots") for pod in pods}
    return Q.Environment(jar=jar, setups=setups, fast=True)


def test_a_bad_deck_game_has_one_unknown_card_and_no_printing_for_it(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    scenario, decks, _ = Q._game_inputs(env, "real:2" + Q.BAD_DECK_SUFFIX)
    assert scenario.seed == 2 and decks[1].mainboard[10] == Q.BROKEN_CARD
    assert decks[1].card_printings == () and decks[0].mainboard[10] == "card10"
    assert env.setups["real"][1][1].mainboard[10] == "card10", "the pool's own deck is untouched"


def test_a_single_game_is_played_the_evidence_lane_way_and_a_batch_through_run_batch(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[tuple[str, tuple[str, ...], int]] = []

    class FakeRunner:
        def __init__(self, command, *, private_card_repository, request_timeout_seconds):
            self.command = command
            assert private_card_repository
            self.timeout = request_timeout_seconds

        def run(self, *, scenario, decks, pilots):
            calls.append(("run", self.command, scenario.seed))
            return _Result(scenario.seed)

        def run_batch(self, games):
            calls.append(("run_batch", self.command, len(games)))
            return [_Result(scenario.seed) for scenario, _, _ in games]

    monkeypatch.setattr(Q, "XmageFullGameRunner", FakeRunner)
    env = _environment(tmp_path)
    plan = {spec.name: spec for spec in Q.build_plan()}
    single = Q.execute(plan["ref-a-real:1"], env)
    assert [c[0] for c in calls] == ["run"] and calls[0][2] == 1
    assert single["rows"][0]["semantic"] == "h1" and single["rows"][0]["position"] == 0
    batch = Q.execute(plan["chunk3-0"], env)
    assert calls[1][0] == "run_batch" and calls[1][2] == 3
    assert [r["game"] for r in batch["rows"]] == list(plan["chunk3-0"].games)
    assert all(r["status"] == "ok" for r in batch["rows"]) and "fault_fired" not in batch


def test_a_batch_that_raises_as_a_whole_fails_every_game_of_it(tmp_path: Path, monkeypatch) -> None:
    class FakeRunner:
        def __init__(self, command, **kwargs):
            pass

        def run_batch(self, games):
            raise OSError("no java")

    monkeypatch.setattr(Q, "XmageFullGameRunner", FakeRunner)
    record = Q.execute(
        next(s for s in Q.build_plan() if s.name == "reverse"), _environment(tmp_path)
    )
    assert {row["status"] for row in record["rows"]} == {"failed"}


def test_a_fault_batch_reports_whether_the_fault_fired(tmp_path: Path, monkeypatch) -> None:
    class FakeRunner:
        def __init__(self, command, *, request_timeout_seconds, **kwargs):
            self.timeout = request_timeout_seconds

        def run_batch(self, games):
            return [_Result(1)] * len(games)

    monkeypatch.setattr(Q, "XmageFullGameRunner", FakeRunner)
    spec = next(s for s in Q.build_plan() if s.name == "isolation-stop-1")
    record = Q.execute(spec, _environment(tmp_path))
    assert record["fault_fired"] is False, "no decision was requested, so nothing was signalled"
    assert record["fault"]["kind"] == "stop"


def test_a_stopped_jvm_gets_a_short_request_timeout_and_other_runs_the_default(
    tmp_path: Path, monkeypatch
) -> None:
    timeouts: dict[str, float] = {}

    class FakeRunner:
        def __init__(self, command, *, request_timeout_seconds, **kwargs):
            timeouts[command[-1]] = request_timeout_seconds
            self.timeout = request_timeout_seconds

        def run_batch(self, games):
            timeouts["last"] = self.timeout
            return [_Result(1)] * len(games)

    monkeypatch.setattr(Q, "XmageFullGameRunner", FakeRunner)
    plan = {spec.name: spec for spec in Q.build_plan()}
    env = _environment(tmp_path)
    Q.execute(plan["isolation-stop-0"], env)
    assert timeouts["last"] == Q.STOPPED_REQUEST_TIMEOUT_SECONDS
    Q.execute(plan["isolation-kill-0"], env)
    assert timeouts["last"] == 120.0


# --- resuming ----------------------------------------------------------------------------------


def test_a_hash_that_differs_is_a_result_and_never_played_again() -> None:
    plan = {spec.name: spec for spec in Q.build_plan()}
    record = _record(plan["rotation-1"])
    assert Q.batch_is_done(plan["rotation-1"], record)
    record["rows"][3]["semantic"] = "0" * 64
    assert Q.batch_is_done(plan["rotation-1"], record), "a difference must not be rerun away"


def test_a_failure_nobody_planned_is_played_again_and_a_planned_one_is_not() -> None:
    plan = {spec.name: spec for spec in Q.build_plan()}
    record = _record(plan["isolation-kill-1"])
    assert Q.batch_is_done(plan["isolation-kill-1"], record)
    record["rows"][0] |= {"status": "failed", "error": "TIMEOUT"}
    assert not Q.batch_is_done(plan["isolation-kill-1"], record)
    assert not Q.batch_is_done(plan["isolation-kill-1"], None)


def test_a_fault_that_did_not_fire_is_played_again() -> None:
    plan = {spec.name: spec for spec in Q.build_plan()}
    record = _record(plan["isolation-stop-2"])
    record["fault_fired"] = False
    assert not Q.batch_is_done(plan["isolation-stop-2"], record)


def test_a_fault_is_counted_in_the_request_the_runner_really_sends_per_decision() -> None:
    """The first live run counted ``get_full_game_decision``, which the runner sends once per
    wait for the engine, not per answered decision, so no fault ever fired."""
    source = (ROOT / "src/commander_lab/engine/rules/full_game.py").read_text(encoding="utf-8")
    assert f'"{Q.DECISION_REQUEST}",' in source
    assert Q.DECISION_REQUEST != "get_full_game_decision"
