"""Every name a module lists in ``__all__`` must exist, so ``from pkg import *`` works."""

from __future__ import annotations

import importlib
import pkgutil

import commander_lab


def test_every_all_entry_is_an_attribute_of_its_module() -> None:
    checked = 0
    problems: list[str] = []
    for info in pkgutil.walk_packages(commander_lab.__path__, "commander_lab."):
        module = importlib.import_module(info.name)
        names = getattr(module, "__all__", None)
        if names is None:
            continue
        checked += 1
        problems.extend(f"{info.name}.{name}" for name in names if not hasattr(module, name))
    assert checked, "nothing was checked: no module defines __all__"
    assert not problems, problems


def test_star_import_of_the_hub_packages_works() -> None:
    for name in ("commander_lab.models", "commander_lab.agents", "commander_lab.engine"):
        namespace: dict[str, object] = {}
        exec(f"from {name} import *", namespace)
        assert len(namespace) > 1
