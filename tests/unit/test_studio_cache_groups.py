"""The cache's register of kinds and table groups, and its write windows (D-1, #1612).

Separate from ``test_studio_cache_single_flight.py`` (concurrency of one key) and
``test_studio_perf_equivalence.py`` (figures and routes against plain computations): these tests
pin the mechanism itself on a small store."""

from __future__ import annotations

import ast
import re
import sqlite3
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

import pytest

from commander_lab.studio import StudioStore, cache
from commander_lab.studio.store import _SCHEMA

STUDIO = Path(cache.__file__).resolve().parent


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    cache.invalidate()
    yield
    cache.invalidate()


def _store(tmp_path: Path) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _probe_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    """One synthetic kind per group, ``probe_<group>``, reading only that group."""
    probes = {f"probe_{group.value}": cache.Kind(reads=frozenset({group})) for group in cache.Group}
    monkeypatch.setattr(cache, "KINDS", MappingProxyType({**cache.KINDS, **probes}))


def _held(store: StudioStore) -> dict[str, object]:
    """A fresh value for every probe kind and one undeclared kind."""
    names = [f"probe_{group.value}" for group in cache.Group] + ["undeclared"]
    return {name: cache.cached(store, (name,), lambda name=name: [name]) for name in names}


def _kept(store: StudioStore, held: dict[str, object]) -> set[str]:
    return {
        name
        for name, value in held.items()
        if cache.cached(store, (name,), lambda name=name: [name]) is value
    }


# -- the register ----------------------------------------------------------------------------


def test_every_table_of_the_schema_is_in_exactly_one_group() -> None:
    """A new table without a group makes this fail and forces the decision."""
    named = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", _SCHEMA))
    memory = StudioStore.in_memory()
    try:
        tables = {
            str(row[0])
            for row in memory.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    finally:
        memory.close()
    assert tables == named == set(cache.TABLE_GROUP)
    assert len(tables) == 44
    sizes = {group: sum(g is group for g in cache.TABLE_GROUP.values()) for group in cache.Group}
    assert sizes == {
        cache.Group.IMPORT: 27,
        cache.Group.DECKS: 9,
        cache.Group.MARKS: 2,
        cache.Group.PROFILES: 2,
        cache.Group.SIMULATION: 2,
        cache.Group.SNAPSHOT: 1,
        cache.Group.META: 1,
    }


# The modules that import ``cached`` from ``.cache`` by name.
_IMPORTS_CACHED = frozenset(
    path.name
    for path in STUDIO.glob("*.py")
    if "from .cache import cached" in path.read_text(encoding="utf-8")
)


def _first_string(node: ast.expr, assigned: dict[str, ast.expr]) -> str | None:
    if isinstance(node, ast.Name) and node.id in assigned:
        node = assigned[node.id]
    if isinstance(node, ast.Tuple) and node.elts:
        first = node.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _kinds_in_source() -> tuple[set[str], list[str]]:
    """The kinds named by every ``cached`` call and every ``answer_cache.json_answer`` call of
    the Studio package, and the calls whose kind cannot be read from the source."""
    found: set[str] = set()
    unreadable: list[str] = []
    for path in sorted(STUDIO.glob("*.py")):
        if path.name == "cache.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            assigned = {
                target.id: node.value
                for node in ast.walk(function)
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            for call in ast.walk(function):
                if not isinstance(call, ast.Call):
                    continue
                func = call.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                owner = (
                    func.value.id
                    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                    else None
                )
                where = f"{path.name}:{call.lineno}"
                # ``cache.cached``, or ``cached`` imported from ``.cache`` (``memo.cached`` is the
                # other memory and stays outside this register until P2)
                direct = owner is None and path.name in _IMPORTS_CACHED
                if name == "cached" and (owner == "cache" or direct) and len(call.args) >= 2:
                    kind = _first_string(call.args[1], assigned)
                    if kind == "answer" and path.name == "answer_cache.py":
                        continue  # ``json_answer`` itself; its callers name the route below
                    if kind is None:
                        unreadable.append(where)
                    else:
                        found.add(kind)
                elif name == "json_answer" and owner == "answer_cache" and len(call.args) >= 2:
                    route = call.args[1]
                    if isinstance(route, ast.Constant) and isinstance(route.value, str):
                        found.add(f"answer:{route.value}")
                    else:
                        unreadable.append(where)
    return found, sorted(set(unreadable))


def test_every_cached_call_names_a_registered_kind_and_every_kind_is_used() -> None:
    found, unreadable = _kinds_in_source()
    assert unreadable == []
    assert found - set(cache.KINDS) == set()  # no call with an undeclared kind
    assert set(cache.KINDS) - found == set()  # no declaration without a call
    assert len(found) == 28


def test_answer_keys_are_one_kind_per_route_sharing_one_size_limit() -> None:
    assert cache.kind_name(("answer", "pool", (), ())) == "answer:pool"
    assert cache.kind_name(("strength", "x")) == "strength"
    answers = {name: kind for name, kind in cache.KINDS.items() if name.startswith("answer:")}
    assert len(answers) == 6
    assert {kind.limit for kind in answers.values()} == {"answer"}
    assert {kind.seal for kind in answers.values()} == {"bytes"}
    assert cache.kind_of("answer:not_registered").limit == "answer"
    assert cache.kind_of("not_registered").reads == cache.ALL


def test_slot_catalog_and_cohort_sizes_have_their_own_limit(tmp_path: Path) -> None:
    """#1615 point 3: a sweep over many commanders pushes out its own older entries, never the
    warm figures or the route answers."""
    store = _store(tmp_path)
    cache.cached(store, ("corpus_hits", ("A",)), lambda: "warm")
    cache.cached(store, ("answer", "pool", ("A",), ()), lambda: b"{}")
    for number in range(12):
        cache.cached(store, ("slot_catalog", (f"C{number}",)), lambda: "slots")
        cache.cached(store, ("cohort_sizes", (f"C{number}",)), lambda n=number: {"all": n})
    keys = [key for key, _ in cache.snapshot(store)]
    for kind in ("slot_catalog", "cohort_sizes"):
        mine = [key for key in keys if key[0] == kind]
        assert mine == [(kind, (f"C{n}",)) for n in range(4, 12)], kind
    assert ("corpus_hits", ("A",)) in keys
    assert ("answer", "pool", ("A",), ()) in keys


# -- windows ---------------------------------------------------------------------------------


def _mark(store: StudioStore, card_id: str = "card:project:0101") -> None:
    from commander_lab.studio import builder

    builder.set_favorite(store, card_id, True)


def test_a_proven_window_raises_only_the_groups_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _probe_kinds(monkeypatch)
    store = _store(tmp_path)
    held = _held(store)
    with cache.write(store, {cache.Group.MARKS}):
        _mark(store)
    kept = _kept(store, held)
    assert kept == {
        f"probe_{group.value}" for group in cache.Group if group is not cache.Group.MARKS
    }
    assert cache.counters()["* window_proven"] == 1
    assert cache.counters()["probe_marks dropped_written"] == 1


def test_a_window_that_writes_an_undeclared_group_drops_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _probe_kinds(monkeypatch)
    store = _store(tmp_path)
    held = _held(store)
    with cache.write(store, {cache.Group.DECKS}):
        _mark(store)
    assert _kept(store, held) == set()
    assert cache.counters()["* window_undeclared"] == 1
    held = _held(store)
    monkeypatch.setattr(cache, "CHECK", True)
    with (
        pytest.raises(cache.CacheCheckError, match="marks"),
        cache.write(store, {cache.Group.DECKS}),
    ):
        _mark(store, "card:project:0102")
    assert _kept(store, held) == set()  # dropped before the error is raised


def test_a_foreign_commit_drops_everything_and_so_does_a_write_outside_a_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _probe_kinds(monkeypatch)
    store = _store(tmp_path)
    held = _held(store)
    other = sqlite3.connect(tmp_path / "studio" / "studio.sqlite3")
    other.execute("UPDATE card_mark SET note = 'foreign' WHERE 0")  # no change: nothing happens
    other.commit()
    assert _kept(store, held) == set(held)
    other.execute("INSERT INTO meta(key, value) VALUES ('foreign', 'x')")
    other.commit()
    other.close()
    assert _kept(store, held) == set()
    assert cache.counters()["* rebase_foreign"] == 1
    held = _held(store)
    _mark(store)  # the Studio's own write, but outside a window
    assert _kept(store, held) == set()


def test_the_counter_rule_alone_catches_a_foreign_commit_in_the_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second probe: with ``data_version`` blinded, a file counter that rose by more than
    the window's own commits still drops everything."""
    _probe_kinds(monkeypatch)
    store = _store(tmp_path)
    held = _held(store)
    monkeypatch.setattr(cache, "_data_version", lambda _store: 0)
    with cache.write(store, {cache.Group.MARKS}):
        _mark(store)
        other = sqlite3.connect(tmp_path / "studio" / "studio.sqlite3")
        other.execute("INSERT INTO meta(key, value) VALUES ('foreign', 'x')")
        other.commit()
        other.close()
    assert _kept(store, held) == set()
    assert cache.counters()["* window_unproven"] == 1


def test_the_writing_thread_computes_directly_inside_its_window(tmp_path: Path) -> None:
    """I5: inside the window (also after its own commit) nothing is served or remembered, and
    asking for a figure there does not wait for the window itself."""
    store = _store(tmp_path)
    cache.cached(store, ("figure",), lambda: "before")
    seen: list[object] = []

    def body() -> None:
        own = StudioStore.open(tmp_path / "studio")
        with cache.write(own, {cache.Group.MARKS}):
            seen.append(cache.cached(own, ("figure",), lambda: "inside"))
            _mark(own)
            seen.append(cache.cached(own, ("figure",), lambda: "after commit"))
        own.close()

    worker = threading.Thread(target=body)
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert seen == ["inside", "after commit"]
    assert cache.counters()["figure bypass_window"] == 2
    assert cache.cached(store, ("figure",), lambda: "fresh") == "fresh"


def test_nested_windows_join_the_outer_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _probe_kinds(monkeypatch)
    store = _store(tmp_path)
    held = _held(store)
    with cache.write(store, {cache.Group.DECKS}), cache.write(store, {cache.Group.MARKS}):
        _mark(store)
    assert cache.counters()["* window_proven"] == 1
    assert "probe_decks" in _kept(store, held)  # declared, not written: kept


def test_a_reader_waits_for_a_running_window_instead_of_dropping_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _probe_kinds(monkeypatch)
    store = _store(tmp_path)
    held = _held(store)
    committed = threading.Event()

    def writer() -> None:
        own = StudioStore.open(tmp_path / "studio")
        with cache.write(own, {cache.Group.MARKS}):
            _mark(own)
            committed.set()
            time.sleep(0.3)  # the reader meets the new stamp while the window is open
        own.close()

    thread = threading.Thread(target=writer)
    thread.start()
    assert committed.wait(timeout=10)
    reader = StudioStore.open(tmp_path / "studio")
    assert reader.connection.execute("SELECT 1").fetchone()
    value = cache.cached(reader, ("probe_import",), lambda: ["recomputed"])
    thread.join(timeout=10)
    assert value is held["probe_import"]
    assert "* rebase_foreign" not in cache.counters()


def test_a_figure_in_flight_survives_a_write_to_a_group_it_does_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The flight key keeps its generations over a write to another group: concurrent callers
    keep sharing the computation and its value is remembered."""
    _probe_kinds(monkeypatch)
    store = _store(tmp_path)
    started, written = threading.Event(), threading.Event()
    calls: list[int] = []

    def compute() -> list[str]:
        calls.append(1)
        started.set()
        assert written.wait(timeout=10)
        return ["slow"]

    results: list[object] = []

    def ask() -> None:
        reader = StudioStore.open(tmp_path / "studio")
        results.append(cache.cached(reader, ("probe_import",), compute))
        reader.close()

    threads = [threading.Thread(target=ask) for _ in range(4)]
    threads[0].start()
    assert started.wait(timeout=10)
    with cache.write(store, {cache.Group.MARKS}):
        _mark(store)
    for thread in threads[1:]:
        thread.start()
    time.sleep(0.2)
    written.set()
    for thread in threads:
        thread.join(timeout=10)
    assert len(calls) == 1
    assert len(results) == 4 and all(result is results[0] for result in results)
    assert cache.cached(store, ("probe_import",), lambda: ["again"]) is results[0]
    assert cache._flights == {}


def test_check_mode_catches_a_caller_that_changes_a_remembered_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache, "CHECK", True)
    store = _store(tmp_path)
    value = cache.cached(store, ("shared",), lambda: {"cards": [1, 2]})
    assert cache.cached(store, ("shared",), lambda: {}) is value
    value["cards"].append(3)  # type: ignore[index]
    with pytest.raises(cache.CacheCheckError, match="shared"):
        cache.cached(store, ("shared",), lambda: {})
    assert cache.counters()["shared mutated"] == 1


def test_the_series_store_write_is_a_proven_window_of_its_declared_groups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one background writer of the server process (a finished batch series)."""
    from commander_lab.studio.simulations import SimulationBatchManager
    from tests.unit.test_studio_simulations import _seed_test_deck

    monkeypatch.setattr(cache, "CHECK", True)  # an undeclared group would fail the series
    _probe_kinds(monkeypatch)
    store = StudioStore.open(tmp_path)
    rev_id = _seed_test_deck(store)
    held = _held(store)

    def executor(**kwargs: object) -> dict[str, object]:
        return {"status": "finished", "winner_seats": [0], "decision_count": 5, "rounds": 3}

    batch = SimulationBatchManager().start_batch(
        store,
        tmp_path,
        revision_id=rev_id,
        pod="precon",
        games_count=2,
        base_seed=1,
        game_executor=executor,
    )
    deadline = time.monotonic() + 10
    while batch.status in {"pending", "running"} and time.monotonic() < deadline:
        time.sleep(0.05)
    assert batch.status == "completed"
    assert cache.counters()["* window_proven"] == 1
    kept = _kept(store, held)
    store.close()
    assert kept == {"probe_marks", "probe_decks", "probe_profiles", "probe_snapshot", "probe_meta"}
