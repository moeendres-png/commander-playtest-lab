"""Where the owner's own data lives.

The owner's physical inventory, active-deck scope, pod and playstyle records are not project
code. By default they are read from the repository tree; when ``COMMANDER_LAB_OWNER_DATA``
names a folder, every owner-data path is read from that folder instead, with the same relative
layout (``<folder>/data/collections/current/...``).

With the variable set there is no fallback to the repository: a missing private file stays
missing, so a run never silently continues on stand-in data. With the variable unset nothing
changes.
"""

from __future__ import annotations

import os
from pathlib import Path

OWNER_DATA_ENV = "COMMANDER_LAB_OWNER_DATA"

# Relative paths (POSIX, from the project root). A trailing slash means "everything below".
OWNER_DATA_PATHS: tuple[str, ...] = (
    "data/collections/current/",
    "data/collections/current_deck_allocations.json",
    "data/collections/phase7_optimization_pool.json",
    "data/canonical_import/",
    "data/sync/current_sources.json",
)


def owner_data_root() -> Path | None:
    """The private folder named by ``COMMANDER_LAB_OWNER_DATA``, or None when unset or empty."""
    value = os.environ.get(OWNER_DATA_ENV, "").strip()
    return Path(value).expanduser() if value else None


def is_owner_data(relative: str) -> bool:
    """True when ``relative`` (POSIX, from the project root) is one of the owner-data paths."""
    for entry in OWNER_DATA_PATHS:
        if entry.endswith("/"):
            if relative.startswith(entry) or relative == entry.rstrip("/"):
                return True
        elif relative == entry:
            return True
    return False


def owner_data_path(root: str | Path, relative: str) -> Path:
    """``root/relative``, or the same path under the private folder for an owner-data path."""
    private = owner_data_root()
    if private is not None and is_owner_data(relative):
        return private / relative
    return Path(root) / relative
