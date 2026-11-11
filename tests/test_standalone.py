from __future__ import annotations

from pathlib import Path

from commander_lab.studio import StudioStore
from commander_lab.studio.commander_cache import cache_commander


def test_store_without_simulation_imports() -> None:
    store = StudioStore.in_memory()
    try:
        assert store.count("card") == 0
    finally:
        store.close()


def test_cache_requires_commander() -> None:
    store = StudioStore.in_memory()
    try:
        try:
            cache_commander(store, [])
            assert False, "must reject empty commander set"
        except ValueError:
            pass
    finally:
        store.close()


def test_static_app_exists() -> None:
    from commander_lab.studio.web import STATIC
    assert (Path(STATIC) / "index.html").is_file()
    assert (Path(STATIC) / "app.js").is_file()
