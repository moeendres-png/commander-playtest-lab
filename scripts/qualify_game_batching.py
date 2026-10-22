"""Qualify batched play (``--games-per-jvm``) on a real bridge jar.

Batching plays several games one after the other in one bridge JVM (Owner decision
2026-10-15: measurement runs only, never PB-03, mid-game or evidence lanes). It is only worth
using if the games stay the games. This script checks four properties against the semantic
transcript SHA-256 of the same games played one per JVM, the way the evidence lanes play them:

    positions     a game does not depend on its place in the JVM: cyclic rotations of an 8-game
                  pool put every game at every position of an 8-game batch.
    permutations  nor on its neighbours or the chunking: the reverse order, two shuffles, chunks
                  of 3 and of 5, and a game played again right after itself.
    memory        a JVM that plays 56 games (the pool seven times, shuffled each pass) does not
                  grow: live set after a forced GC at every game start, RSS peak, and every
                  one of the 56 games still has its reference hash.
    isolation     a game that fails at the start, the middle or the end of a batch (a deck with
                  an unknown card, a killed JVM, a stopped JVM) leaves every other game as it
                  would have been played alone.

    python scripts/qualify_game_batching.py run --jar bridge.jar --out report.json --fast
    python scripts/qualify_game_batching.py verdict report.json

``run`` writes the raw rows to ``--out`` after every batch (``--resume`` plays only batches that
are still open) and ends with the verdict. ``verdict`` recomputes it from the file, so the
numbers can be re-checked without a JVM. A verdict is PASS, FAIL or INCONCLUSIVE; a missing,
unplayed or failed-by-infrastructure game is INCONCLUSIVE, never PASS, and a hash that differs is
FAIL and is never played again. Exit 0 only if all four properties PASS.

The reference is one game per JVM with the launch of the evidence lanes (no extra flags), played
twice. The batched runs use ``--fast`` (serial GC, AppCDS) when asked, which is how sweeps run,
so the claim covers batching and the launch flags together. Local runs are measurements, not
qualification evidence in the sealed sense.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import json
import os
import platform
import random
import re
import resource
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark_xmage_full_games as bench  # noqa: E402

from commander_lab.engine.rules import full_game  # noqa: E402
from commander_lab.engine.rules.full_game import XmageFullGameRunner  # noqa: E402

SCHEMA = 1
PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"
PROPERTIES = ("positions", "permutations", "memory", "isolation")

#: Games are named ``pod:seed``; a pod is a name of ``benchmark_xmage_full_games._pods``.
POOL = (
    "real:1",
    "coverage-0:1",
    "coverage-1:1",
    "real:2",
    "coverage-2:1",
    "coverage-3:1",
    "coverage-4:1",
    "real:3",
)
MEMORY_PASSES = 7  # 7 x 8 = 56 games in one JVM
MASTER = "batching-qualification-2026-10-22"
BAD_DECK_SUFFIX = "!bad-deck"
BROKEN_CARD = "Zzyzx Nonexistent Card"
FAULT_AFTER_DECISIONS = 400
#: The request that answers one decision (``XmageFullGameRunner._drive``); a fault is counted in these.
DECISION_REQUEST = "submit_full_game_decision"
#: How long a stopped JVM may stay silent before the runner gives up on it.
STOPPED_REQUEST_TIMEOUT_SECONDS = 60.0

# Memory criteria, fixed before the first measurement and kept (see the report in docs/performance).
WARMUP_GAMES = 8  # the first pass pays JIT and class loading; growth is judged after it
LIVE_SLOPE_MAX_MIB_PER_GAME = 1.0
LIVE_PASS_RATIO_MAX = 1.10  # last pass mean live set against the first judged pass
LIVE_PASS_TOLERANCE_MIB = 16.0  # ...plus this, so a tiny live set cannot fail on noise
RSS_PEAK_MAX_GIB = 3.0  # operational ceiling for one JVM on a 4-core, 16 GB machine


# --- the plan ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Fault:
    """Something done to the bridge JVM of the game at ``position`` of a batch."""

    kind: str  # "kill" (SIGKILL: lost transport) or "stop" (SIGSTOP: a hang the runner times out)
    position: int
    after_decisions: int = FAULT_AFTER_DECISIONS


@dataclass(frozen=True)
class BatchSpec:
    name: str
    phase: str  # reference | positions | permutations | memory | isolation
    games: tuple[str, ...]
    #: 1 plays the evidence-lane way (``run``, no property); more sets the bridge property.
    games_per_jvm: int
    fast: bool
    fault: Fault | None = None
    sample_memory: bool = False

    @property
    def weight(self) -> int:
        return len(self.games) + (2 if self.fault else 0)


def game_key(game: str) -> tuple[str, int]:
    pod, _, seed = game.removesuffix(BAD_DECK_SUFFIX).rpartition(":")
    return pod, int(seed)


def is_bad_deck(game: str) -> bool:
    return game.endswith(BAD_DECK_SUFFIX)


def rotations(pool: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Every cyclic rotation: each game stands once at every position."""
    return [pool[shift:] + pool[:shift] for shift in range(len(pool))]


def shuffled(pool: tuple[str, ...], label: str) -> tuple[str, ...]:
    """A reproducible permutation of ``pool`` that depends only on ``MASTER`` and ``label``."""
    seed = int.from_bytes(hashlib.sha256(f"{MASTER}:{label}".encode()).digest()[:8], "big")
    order = list(pool)
    random.Random(seed).shuffle(order)
    return tuple(order)


def memory_sequence(pool: tuple[str, ...], passes: int) -> tuple[str, ...]:
    """``passes`` shuffles of the pool one after the other: every game ``passes`` times."""
    return tuple(game for n in range(passes) for game in shuffled(pool, f"memory-pass-{n}"))


def _chunks(order: tuple[str, ...], size: int) -> list[tuple[str, ...]]:
    return [order[start : start + size] for start in range(0, len(order), size)]


def build_plan(pool: tuple[str, ...] = POOL, passes: int = MEMORY_PASSES) -> list[BatchSpec]:
    plan: list[BatchSpec] = []

    def add(name: str, phase: str, games: tuple[str, ...], **extra: Any) -> None:
        plan.append(BatchSpec(name, phase, games, len(games), True, **extra))

    for twin in ("a", "b"):  # the reference: one game per JVM, the evidence-lane launch
        for game in pool:
            plan.append(BatchSpec(f"ref-{twin}-{game}", "reference", (game,), 1, False))
    for shift, order in enumerate(rotations(pool)):
        add(f"rotation-{shift}", "positions", order)
    add("reverse", "permutations", tuple(reversed(pool)))
    for n in (1, 2):
        add(f"shuffle-{n}", "permutations", shuffled(pool, f"shuffle-{n}"))
    for size in (3, 5):
        for n, chunk in enumerate(_chunks(pool, size)):
            add(f"chunk{size}-{n}", "permutations", chunk)
    for game in (pool[0], pool[1]):
        add(f"repeat-{game}", "permutations", (game, game, game))
    add("memory", "memory", memory_sequence(pool, passes), sample_memory=True)
    for k, kind in enumerate(("bad-deck", "kill", "stop")):
        trio = tuple(pool[(3 * k + i) % len(pool)] for i in range(3))
        for position in range(3):
            if kind == "bad-deck":
                games = tuple(
                    g + BAD_DECK_SUFFIX if i == position else g for i, g in enumerate(trio)
                )
                add(f"isolation-{kind}-{position}", "isolation", games)
            else:
                fault = Fault(kind, position)
                add(f"isolation-{kind}-{position}", "isolation", trio, fault=fault)
    names = [spec.name for spec in plan]
    assert len(names) == len(set(names)), "batch names must be unique"
    return plan


# --- instrumentation of the requests the runner sends -------------------------------------------

_HOOKS = threading.local()


class Hook:
    """Sees the requests of one batch; the runner, the pilots and the bridge are not changed."""

    def before(self, client: Any, message_type: str, payload: dict[str, Any] | None) -> None:
        pass

    def after(self, client: Any, message_type: str, response: dict[str, Any]) -> None:
        pass


@contextlib.contextmanager
def instrumented_requests() -> Iterator[None]:
    """Route every ``_RawFullGameClient.request`` of a thread through that thread's hook."""
    client_class = full_game._RawFullGameClient
    original = client_class.request

    @functools.wraps(original)
    def request(self: Any, message_type: str, payload: dict[str, Any] | None = None) -> Any:
        hook: Hook | None = getattr(_HOOKS, "current", None)
        if hook is not None:
            hook.before(self, message_type, payload)
        response = original(self, message_type, payload)
        if hook is not None:
            hook.after(self, message_type, response)
        return response

    client_class.request = request  # type: ignore[method-assign]
    try:
        yield
    finally:
        client_class.request = original  # type: ignore[method-assign]


class FaultHook(Hook):
    """Signals the bridge JVM of one game of a batch once, a fixed number of decisions in."""

    def __init__(self, fault: Fault) -> None:
        self.fault = fault
        self.created = -1
        self.decisions = 0
        self.fired = False
        self.pids: list[int] = []

    def before(self, client: Any, message_type: str, payload: dict[str, Any] | None) -> None:
        if message_type == "create_full_game":
            self.created += 1
            self.decisions = 0
        elif (
            message_type == DECISION_REQUEST
            and not self.fired
            and self.created == self.fault.position
        ):
            self.decisions += 1
            if self.decisions >= self.fault.after_decisions:
                self.fired = True
                pid = client._process.pid
                self.pids.append(pid)
                os.kill(pid, signal.SIGKILL if self.fault.kind == "kill" else signal.SIGSTOP)

    def cleanup(self) -> None:
        """A stopped JVM must not outlive the batch."""
        for pid in self.pids:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)


def read_proc_status(pid: int) -> dict[str, int]:
    """``VmRSS`` and ``VmHWM`` (KiB) of a process; empty if it is gone or not on Linux."""
    try:
        text = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except OSError:
        return {}
    found = {
        m.group(1): int(m.group(2)) for m in re.finditer(r"^(VmRSS|VmHWM):\s+(\d+) kB", text, re.M)
    }
    return {"rss_kib": found["VmRSS"], "hwm_kib": found["VmHWM"]} if len(found) == 2 else {}


def parse_heap_info(text: str) -> dict[str, int] | None:
    """Heap and metaspace use (KiB) from ``jcmd <pid> GC.heap_info``; None if unrecognised.

    Serial GC prints a young and a tenured generation, G1 one heap line. After ``GC.run`` the
    young generation is nearly empty, so the sum is the live set.
    """
    heap = [
        int(m.group(1))
        for m in re.finditer(
            r"^\s*(?:def new generation|tenured generation|garbage-first heap|"
            r"PSYoungGen|ParOldGen)\s+total \d+K, used (\d+)K",
            text,
            re.M,
        )
    ]
    meta = re.search(r"^\s*Metaspace\s+used (\d+)K", text, re.M)
    if not heap or meta is None:
        return None
    return {"live_kib": sum(heap), "metaspace_kib": int(meta.group(1))}


def jcmd_live_set(pid: int) -> dict[str, int]:
    """Live set after a forced full GC; empty if ``jcmd`` cannot attach."""
    try:
        for command in ("GC.run", "GC.heap_info"):
            done = subprocess.run(
                ["jcmd", str(pid), command],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
        return parse_heap_info(done.stdout) or {}
    except (OSError, subprocess.SubprocessError):
        return {}


class MemoryHook(Hook):
    """Samples the JVM at every game start (previous game released) and every game end."""

    def __init__(self, live_set: Callable[[int], dict[str, int]] = jcmd_live_set) -> None:
        self.live_set = live_set
        self.created = 0
        self.samples: list[dict[str, Any]] = []

    def after(self, client: Any, message_type: str, response: dict[str, Any]) -> None:
        if message_type == "create_full_game":
            self.created += 1
            self._sample(client, "start")
        elif message_type == "shutdown_game":
            self._sample(client, "end")

    def _sample(self, client: Any, when: str) -> None:
        pid = client._process.pid
        self.samples.append(
            {"game": self.created, "when": when, **read_proc_status(pid), **self.live_set(pid)}
        )


# --- playing a batch ---------------------------------------------------------------------------


@dataclass
class Environment:
    jar: Path
    setups: dict[str, tuple[Any, Any, Any]]
    fast: bool


def load_environment(jar: Path, fast: bool, pool: tuple[str, ...]) -> Environment:
    setups = {pod: bench._setup(paths) for pod, paths in bench._pods(False) + bench._pods(True)}
    missing = sorted({game_key(g)[0] for g in pool} - set(setups))
    if missing:
        raise SystemExit(f"unknown pod(s) in the pool: {missing}")
    return Environment(jar=jar, setups=setups, fast=fast)


def _game_inputs(env: Environment, game: str) -> tuple[Any, Any, Any]:
    pod, seed = game_key(game)
    scenario, decks, pilots = env.setups[pod]
    if is_bad_deck(game):
        broken = list(decks)
        mainboard = list(broken[1].mainboard)
        mainboard[10] = BROKEN_CARD
        broken[1] = broken[1].model_copy(
            update={"mainboard": tuple(mainboard), "card_printings": ()}
        )
        decks = tuple(broken)
    return scenario.model_copy(update={"seed": seed}), decks, pilots


def _command(env: Environment, spec: BatchSpec) -> tuple[str, ...]:
    options = bench.fast_jvm_options(env.jar) if spec.fast and env.fast else []
    if spec.games_per_jvm > 1:
        options = [*options, f"-D{bench.GAMES_PER_JVM_PROPERTY}={spec.games_per_jvm}"]
    return bench.bridge_command(env.jar, options)


def _is_startup_collision(outcome: Exception) -> bool:
    return "XMAGE_CARD_REPOSITORY_INIT_FAILED" in str(outcome) or any(
        "XMAGE_CARD_REPOSITORY_INIT_FAILED" in str(item)
        for item in getattr(outcome, "diagnostics", ()) or ()
    )


def _play_single(runner: XmageFullGameRunner, inputs: tuple[Any, Any, Any]) -> Any:
    """One game the evidence-lane way (``run``); a card repository start-up collision is retried."""
    scenario, decks, pilots = inputs
    for attempt in range(1, 5):
        try:
            return runner.run(scenario=scenario, decks=decks, pilots=pilots)
        except Exception as exc:
            if attempt == 4 or not _is_startup_collision(exc):
                return exc
            time.sleep(3.0 * attempt)
    raise AssertionError("unreachable")  # pragma: no cover


def execute(spec: BatchSpec, env: Environment) -> dict[str, Any]:
    """Play one batch and return its record (rows, memory samples, whether a fault fired).

    Call it inside :func:`instrumented_requests`; the hook of the batch is per thread.
    """
    inputs = [_game_inputs(env, game) for game in spec.games]
    timeout = STOPPED_REQUEST_TIMEOUT_SECONDS if spec.fault and spec.fault.kind == "stop" else 120.0
    runner = XmageFullGameRunner(
        _command(env, spec), private_card_repository=True, request_timeout_seconds=timeout
    )
    hook: Hook | None = None
    if spec.fault:
        hook = FaultHook(spec.fault)
    elif spec.sample_memory:
        hook = MemoryHook()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    _HOOKS.current = hook
    try:
        if spec.games_per_jvm == 1:
            outcomes: list[Any] = [_play_single(runner, inputs[0])]
        else:
            try:
                outcomes = runner.run_batch(inputs)
            except Exception as exc:  # the batch as a whole failed: every game of it did
                outcomes = [exc] * len(spec.games)
    finally:
        _HOOKS.current = None
        if isinstance(hook, FaultHook):
            hook.cleanup()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    record: dict[str, Any] = {
        **asdict(spec),
        "games": list(spec.games),
        "rows": [
            {"position": i, "game": game} | bench._row_of(outcome)
            for i, (game, outcome) in enumerate(zip(spec.games, outcomes, strict=True))
        ],
        "wall_s": round(time.monotonic() - started, 1),
        "child_cpu_s": round(
            (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime), 1
        ),
    }
    if isinstance(hook, FaultHook):
        record["fault_fired"] = hook.fired
    if isinstance(hook, MemoryHook):
        record["memory"] = hook.samples
    return record


# --- the verdict ------------------------------------------------------------------------------


def _rows(report: dict[str, Any], phase: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (name, row)
        for name, batch in sorted(report["batches"].items())
        if batch["phase"] == phase
        for row in batch["rows"]
    ]


def reference_hashes(report: dict[str, Any]) -> tuple[dict[str, str], list[str], list[str]]:
    """Hashes of the pool games played twice alone with the same result, the games whose two
    runs differ, and other problems."""
    hashes: dict[str, str] = {}
    differing: list[str] = []
    problems: list[str] = []
    for game in report["pool"]:
        twins = []
        for twin in ("a", "b"):
            batch = report["batches"].get(f"ref-{twin}-{game}")
            if batch and batch["rows"] and batch["rows"][0]["status"] == "ok":
                twins.append(batch["rows"][0]["semantic"])
        if len(twins) < 2:
            problems.append(f"{game}: not played twice to the end")
        elif twins[0] != twins[1]:
            differing.append(game)
        else:
            hashes[game] = twins[0]
    if len(set(hashes.values())) != len(hashes):
        problems.append("two pool games have the same hash: a swapped game could not be seen")
    return hashes, differing, problems


def _verdict(status: str, **details: Any) -> dict[str, Any]:
    return {"status": status, **details}


def _compare(
    reference: dict[str, str], rows: list[tuple[str, dict[str, Any]]]
) -> tuple[list[str], list[str], int]:
    """Mismatches, rows that could not be compared, and the number of identical rows."""
    different: list[str] = []
    open_: list[str] = []
    same = 0
    for batch, row in rows:
        label = f"{batch}[{row['position']}] {row['game']}"
        if row["status"] != "ok":
            open_.append(f"{label}: {row.get('error', row['status'])[:120]}")
        elif row["game"] not in reference:
            open_.append(f"{label}: no reference")
        elif row["semantic"] != reference[row["game"]]:
            different.append(label)
        else:
            same += 1
    return different, open_, same


def _planned_batches(report: dict[str, Any], phase: str) -> list[str]:
    return [spec["name"] for spec in report["plan"] if spec["phase"] == phase]


def _unplayed(report: dict[str, Any], phase: str) -> list[str]:
    return [name for name in _planned_batches(report, phase) if name not in report["batches"]]


def check_comparison(
    report: dict[str, Any], reference: dict[str, str], phase: str, *, every_position: bool
) -> dict[str, Any]:
    rows = _rows(report, phase)
    different, open_, same = _compare(reference, rows)
    missing = _unplayed(report, phase)
    if every_position:
        seen = {(row["game"], row["position"]) for _, row in rows if row["status"] == "ok"}
        width = len(report["pool"])
        for game in report["pool"]:
            gaps = [p for p in range(width) if (game, p) not in seen]
            if gaps:
                open_.append(f"{game}: never compared at position(s) {gaps}")
    detail = {"identical": same, "different": different, "open": open_, "unplayed": missing}
    if different:
        return _verdict(FAIL, **detail)
    return _verdict(PASS if not open_ and not missing and same else INCONCLUSIVE, **detail)


def _slope(values: list[float]) -> float:
    n = len(values)
    mean_x, mean_y = (n - 1) / 2, sum(values) / n
    spread = sum((i - mean_x) ** 2 for i in range(n))
    return sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values)) / spread


def check_memory(report: dict[str, Any], reference: dict[str, str]) -> dict[str, Any]:
    batch = report["batches"].get("memory")
    if batch is None:
        return _verdict(INCONCLUSIVE, open=["memory batch not played"])
    different, open_, same = _compare(reference, _rows(report, "memory"))
    samples = batch.get("memory", [])
    games = len(batch["games"])
    size = len(report["pool"])
    live = [s["live_kib"] / 1024 for s in samples if s["when"] == "start" and "live_kib" in s]
    peaks = [s["hwm_kib"] / 1024 for s in samples if "hwm_kib" in s]
    detail: dict[str, Any] = {"games": games, "identical": same}
    grows: list[str] = []
    if games < 50:
        open_.append(f"only {games} games in one JVM (at least 50 are required)")
    judged = live[WARMUP_GAMES:]
    if len(live) != games or not peaks:
        open_.append("live set and RSS not sampled at every game start")
    elif len(judged) < 2 * size:
        open_.append("too few sampled games after the warm-up pass")
    else:
        first = sum(judged[:size]) / size
        last = sum(judged[-size:]) / size
        slope = _slope(judged)
        limit = first * LIVE_PASS_RATIO_MAX + LIVE_PASS_TOLERANCE_MIB
        detail |= {
            "live_slope_mib_per_game": round(slope, 3),
            "live_first_pass_mean_mib": round(first, 1),
            "live_last_pass_mean_mib": round(last, 1),
            "live_max_mib": round(max(live), 1),
            "rss_peak_gib": round(max(peaks) / 1024, 2),
        }
        if slope > LIVE_SLOPE_MAX_MIB_PER_GAME:
            grows.append(
                f"live set grows {slope:.2f} MiB/game (limit {LIVE_SLOPE_MAX_MIB_PER_GAME})"
            )
        if last > limit:
            grows.append(f"last pass holds {last:.0f} MiB, first {first:.0f} (limit {limit:.0f})")
        if max(peaks) / 1024 > RSS_PEAK_MAX_GIB:
            grows.append(f"RSS peak {max(peaks) / 1024:.2f} GiB (limit {RSS_PEAK_MAX_GIB})")
    detail |= {"different": different, "grows": grows, "open": open_}
    if different or grows:
        return _verdict(FAIL, **detail)
    return _verdict(PASS if not open_ else INCONCLUSIVE, **detail)


def check_isolation(report: dict[str, Any], reference: dict[str, str]) -> dict[str, Any]:
    different: list[str] = []
    open_: list[str] = []
    same = failed_as_planned = 0
    for name in _unplayed(report, "isolation"):
        open_.append(f"{name}: not played")
    for name, batch in sorted(report["batches"].items()):
        if batch["phase"] != "isolation":
            continue
        fault = batch.get("fault")
        if fault and not batch.get("fault_fired"):
            open_.append(f"{name}: the fault never fired (the game ended first)")
            continue
        for row in batch["rows"]:
            label = f"{name}[{row['position']}] {row['game']}"
            planned_failure = is_bad_deck(row["game"]) or (
                fault is not None and row["position"] == fault["position"]
            )
            if planned_failure:
                if row["status"] == "ok":
                    different.append(f"{label}: played although it was broken")
                else:
                    failed_as_planned += 1
            elif row["status"] != "ok":
                open_.append(f"{label}: {row.get('error', row['status'])[:120]}")
            elif row["game"] not in reference:
                open_.append(f"{label}: no reference")
            elif row["semantic"] != reference[row["game"]]:
                different.append(f"{label}: differs from its single-game hash")
            else:
                same += 1
    detail = {
        "identical": same,
        "failed_as_planned": failed_as_planned,
        "different": different,
        "open": open_,
    }
    if different:
        return _verdict(FAIL, **detail)
    return _verdict(PASS if not open_ and same and failed_as_planned else INCONCLUSIVE, **detail)


def evaluate(report: dict[str, Any]) -> dict[str, Any]:
    reference, differing, problems = reference_hashes(report)
    result: dict[str, Any] = {
        "reference": _verdict(
            FAIL if differing else (INCONCLUSIVE if problems else PASS),
            stable_games=len(reference),
            different=[f"{game}: the two single-game runs differ" for game in differing],
            open=problems,
        ),
        "positions": check_comparison(report, reference, "positions", every_position=True),
        "permutations": check_comparison(report, reference, "permutations", every_position=False),
        "memory": check_memory(report, reference),
        "isolation": check_isolation(report, reference),
    }
    statuses = {result[name]["status"] for name in ("reference", *PROPERTIES)}
    result["overall"] = FAIL if FAIL in statuses else PASS if statuses == {PASS} else INCONCLUSIVE
    return result


def print_verdict(result: dict[str, Any]) -> None:
    for name in ("reference", *PROPERTIES):
        entry = result[name]
        summary = ", ".join(
            f"{key} {value if not isinstance(value, list) else len(value)}"
            for key, value in entry.items()
            if key != "status" and not isinstance(value, (dict, type(None)))
        )
        print(f"{name:13} {entry['status']:12} {summary}")
        for key in ("different", "grows", "open", "unplayed"):
            for line in entry.get(key, [])[:8]:
                print(f"    {key}: {line}")
    print("BATCHING QUALIFICATION", result["overall"])


# --- the run ---------------------------------------------------------------------------------


def batch_is_done(spec: BatchSpec, record: dict[str, Any] | None) -> bool:
    """A batch is done unless infrastructure got in the way; a differing hash is a result."""
    if record is None or len(record["rows"]) != len(spec.games):
        return False
    if spec.fault and not record.get("fault_fired"):
        return False
    for row in record["rows"]:
        planned = is_bad_deck(row["game"]) or (
            spec.fault is not None and row["position"] == spec.fault.position
        )
        if row["status"] != "ok" and not planned:
            return False
    return True


def _identity(env: Environment) -> dict[str, Any]:
    java = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return {
        "jar": env.jar.name,
        "jar_sha256": hashlib.sha256(env.jar.read_bytes()).hexdigest(),
        "archive": env.jar.with_suffix(".jsa").is_file(),
        "fast_options": bench.fast_jvm_options(env.jar) if env.fast else [],
        "java": next(
            (
                line
                for line in java.stderr.splitlines()
                if "version" in line and "Picked" not in line
            ),
            "",
        ),
        "cpus": os.cpu_count(),
        "python": platform.python_version(),
        "lab_head": head.stdout.strip(),
    }


def run(args: argparse.Namespace) -> int:
    pool = POOL
    plan = build_plan(pool)
    env = load_environment(args.jar, args.fast, pool)
    report: dict[str, Any] = {"schema": SCHEMA, "batches": {}}
    if args.resume and args.out.is_file():
        report = json.loads(args.out.read_text(encoding="utf-8"))
        if report.get("schema") != SCHEMA or report.get("pool") != list(pool):
            raise SystemExit("--resume: the report does not match this script's plan")
    report |= {
        "pool": list(pool),
        "plan": [asdict(spec) | {"games": list(spec.games)} for spec in plan],
        "identity": _identity(env),
        "workers": args.workers,
    }
    open_specs = [
        spec
        for spec in plan
        if not batch_is_done(spec, report["batches"].get(spec.name))
        and (not args.only or spec.phase in args.only)
    ]
    # The long memory batch starts first, then the batches that signal a JVM (a stuck fault path
    # should show early), then the rest, longest first.
    open_specs.sort(key=lambda spec: (spec.phase != "memory", spec.fault is None, -spec.weight))
    lock = threading.Lock()
    started = time.monotonic()

    def play(spec: BatchSpec) -> None:
        record = execute(spec, env)
        with lock:
            previous = report["batches"].get(spec.name)
            record["attempts"] = (previous or {}).get("attempts", 0) + 1
            report["batches"][spec.name] = record
            report["total_wall_s"] = round(time.monotonic() - started, 1)
            args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
            statuses = "".join("." if row["status"] == "ok" else "x" for row in record["rows"])
            print(f"{spec.name:28} {statuses} {record['wall_s']:7.1f} s", flush=True)

    with instrumented_requests(), ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(play, open_specs))
    result = evaluate(report)
    report["verdict"] = result
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print_verdict(result)
    return 0 if result["overall"] == PASS else 1


def verdict(args: argparse.Namespace) -> int:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    result = evaluate(report)
    print_verdict(result)
    return 0 if result["overall"] == PASS else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    play = sub.add_parser("run")
    play.add_argument("--jar", type=Path, required=True)
    play.add_argument("--out", type=Path, required=True)
    play.add_argument("--workers", type=int, default=4)
    play.add_argument("--fast", action="store_true", help="serial GC and the jar's AppCDS archive")
    play.add_argument("--resume", action="store_true", help="play only the batches still open")
    play.add_argument("--only", action="append", choices=("reference", *PROPERTIES), default=[])
    play.set_defaults(func=run)
    check = sub.add_parser("verdict")
    check.add_argument("report", type=Path)
    check.set_defaults(func=verdict)
    args = parser.parse_args(argv)
    if args.cmd == "run" and args.workers < 1:
        parser.error("--workers must be positive")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
