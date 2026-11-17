"""cache.cached: one computation for concurrent identical calls, never stale, never poisoned."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, cache


def _store(tmp_path: Path) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _run_threads(count: int, work: object) -> list[object]:
    results: list[object] = [None] * count
    errors: list[BaseException] = []

    def target(index: int) -> None:
        try:
            results[index] = work()  # type: ignore[operator]
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=target, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors
    return results


def test_concurrent_identical_calls_compute_once(tmp_path: Path) -> None:
    store = _store(tmp_path)
    calls: list[int] = []
    gate = threading.Event()

    def compute() -> list[int]:
        calls.append(1)
        gate.wait(timeout=5)
        time.sleep(0.05)
        return [42]

    threading.Timer(0.3, gate.set).start()
    results = _run_threads(8, lambda: cache.cached(store, ("single-flight",), compute))
    assert len(results) == 8
    assert all(result == [42] for result in results)
    assert len(calls) == 1
    assert cache._flights == {}  # the lock registry does not leak


def test_a_committed_write_makes_the_next_call_recompute(tmp_path: Path) -> None:
    store = _store(tmp_path)
    calls: list[int] = []

    def compute() -> int:
        calls.append(1)
        return len(calls)

    assert cache.cached(store, ("stale-test",), compute) == 1
    assert cache.cached(store, ("stale-test",), compute) == 1
    store.connection.execute("INSERT INTO meta(key, value) VALUES ('single-flight-test', 'x')")
    store.connection.commit()
    assert cache.cached(store, ("stale-test",), compute) == 2
    assert len(calls) == 2


def test_an_exception_is_not_cached_and_releases_the_key(tmp_path: Path) -> None:
    store = _store(tmp_path)
    calls: list[int] = []

    def compute() -> int:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("first computation fails")
        return 5

    with pytest.raises(RuntimeError):
        cache.cached(store, ("poison-test",), compute)
    assert cache._flights == {}
    assert cache.cached(store, ("poison-test",), compute) == 5
    assert cache.cached(store, ("poison-test",), compute) == 5
    assert len(calls) == 2


def test_waiters_of_a_failed_computation_compute_for_themselves(tmp_path: Path) -> None:
    store = _store(tmp_path)
    calls: list[int] = []
    lock = threading.Lock()
    started = threading.Event()

    def compute() -> int:
        with lock:
            calls.append(1)
            first = len(calls) == 1
        if first:
            started.set()
            time.sleep(0.2)
            raise RuntimeError("leader fails")
        return 9

    outcomes: list[object] = []

    def call() -> None:
        try:
            outcomes.append(cache.cached(store, ("waiter-test",), compute))
        except RuntimeError as error:
            outcomes.append(error)

    leader = threading.Thread(target=call)
    leader.start()
    assert started.wait(timeout=5)
    waiters = [threading.Thread(target=call) for _ in range(3)]
    for thread in waiters:
        thread.start()
    for thread in [leader, *waiters]:
        thread.join(timeout=30)
    assert sum(isinstance(item, RuntimeError) for item in outcomes) == 1
    assert [item for item in outcomes if item == 9] == [9, 9, 9]
    assert len(calls) == 2  # the leader, then one waiter; the others read its value
    assert cache._flights == {}


def test_a_state_change_while_computing_is_not_remembered(tmp_path: Path) -> None:
    store = _store(tmp_path)
    other = StudioStore.open(tmp_path / "studio")

    def compute() -> str:
        other.connection.execute("INSERT INTO meta(key, value) VALUES ('mid-compute', 'x')")
        other.connection.commit()
        return "old"

    assert cache.cached(store, ("mid-test",), compute) == "old"
    assert cache.cached(store, ("mid-test",), lambda: "new") == "new"


def test_max_entries_still_evicts_the_oldest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for index in range(cache.MAX_ENTRIES + 5):
        cache.cached(store, ("evict", index), lambda index=index: index)
    assert len(cache._entries) <= cache.MAX_ENTRIES
    assert cache._flights == {}


def test_entries_of_an_older_state_are_dropped_when_a_new_one_is_stored(tmp_path: Path) -> None:
    store = _store(tmp_path)
    cache.cached(store, ("old-state", 1), lambda: "a")
    cache.cached(store, ("old-state", 2), lambda: "b")
    old_stamp = cache.store_stamp(store)
    assert any(key[0] == old_stamp for key in cache._entries)
    store.connection.execute("INSERT INTO meta(key, value) VALUES ('prune-test', 'x')")
    store.connection.commit()
    assert cache.cached(store, ("old-state", 1), lambda: "c") == "c"
    assert not any(key[0] == old_stamp for key in cache._entries)
