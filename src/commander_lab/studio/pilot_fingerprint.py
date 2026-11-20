"""Pilot fingerprint: which pilot code and pilot data played a game (B2, #1658; part of #1524).

``PILOT_VERSION = "1.0.0"`` never changed while the pilot did, so a check that compares it
protects nothing. The fingerprint is a SHA-256 over every file that decides how the pilot
plays (its code under ``agents/`` and ``engine/rules/full_game_pilot*``, its card knowledge,
the curated role profiles, the combo list and the deck guides it reads), with line endings
normalized to LF, plus the decision policy version and the strength tier; a seat's fingerprint
also takes its style. Any change to one of those files changes it; a file outside the list
does not.

The engine-facing ``pilot_identity``/``pilot_version`` stay as they are: they feed the
conformance check and the replay tape, and a change there would move the transcript hash.
The fingerprint goes into the game log header next to them and is the identity the mixing
checks compare (``card_outcomes``, ``paired_comparison``).
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

SCHEMA = "studio-pilot-fingerprint-1"

#: Folders (relative to the repository root) whose ``*.py`` files are pilot code.
CODE_DIRS = (
    "src/commander_lab/agents",
    "src/commander_lab/engine/rules/full_game_pilot",
)
#: Single pilot code modules next to the package (``full_game_pilot_*.py``).
CODE_GLOB = "src/commander_lab/engine/rules/full_game_pilot_*.py"
#: Data files the pilot reads (``card_knowledge``, ``deck_plan``).
DATA_FILES = (
    "data/cards/pilot_card_knowledge.json",
    "data/cards/structural_role_profiles.json",
    "data/meta/spellbook_combos.json",
)
#: The deck guides (``deck_guides``, ``deck_plan`` read ``*.json`` there).
GUIDES_GLOB = "data/deck_guides/guides/*.json"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def pilot_files(root: Path | None = None) -> list[Path]:
    """Every file of the fingerprint, sorted by its path relative to ``root``."""
    base = root if root is not None else _repository_root()
    found: set[Path] = set()
    for folder in CODE_DIRS:
        found.update(p for p in (base / folder).rglob("*.py") if "__pycache__" not in p.parts)
    found.update(base.glob(CODE_GLOB))
    found.update(base.glob(GUIDES_GLOB))
    found.update(base / name for name in DATA_FILES)
    return sorted((p for p in found if p.is_file()), key=lambda p: p.relative_to(base).as_posix())


def files_digest(root: Path | None = None) -> str:
    """SHA-256 over (relative path, LF-normalized content) of every pilot file."""
    base = root if root is not None else _repository_root()
    digest = hashlib.sha256()
    for path in pilot_files(base):
        data = path.read_bytes().replace(b"\r\n", b"\n")
        name = path.relative_to(base).as_posix().encode("utf-8")
        digest.update(len(name).to_bytes(4, "big") + name)
        digest.update(len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _default_files_digest() -> str:
    return files_digest(None)


def pilot_fingerprint(
    *,
    policy_version: str,
    strength: str,
    style: float | None = None,
    root: Path | None = None,
) -> str:
    """The fingerprint of the pilot code and data with policy, strength and (per seat) style.

    ``style=None`` is the table-level fingerprint (code, data, policy, strength); a seat adds
    its style. ``root`` is for tests; the default root is hashed once per process.
    """
    files = _default_files_digest() if root is None else files_digest(root)
    style_text = "table" if style is None else format(float(style), ".6f")
    payload = "\n".join((SCHEMA, files, policy_version, strength, style_text))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
