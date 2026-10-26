"""Deck-Liste fuer die Lab UI: nur Pfade, keine Karteninhalte.

Quellen (Repo, keine Sammlungen):
- data/decks/precons/*.json (Precon-Pool)
- data/decks/*.json (Zieldecks, z. B. rogshai_current)
- data/opponents/**/*.json (Gegnerdecks)
"""

from __future__ import annotations

from pathlib import Path


def list_decks(repo_root: str | Path) -> dict[str, list[str]]:
    """Alle spielbaren Deck-Pfade, relativ zur Repo-Wurzel, sortiert."""
    root = Path(repo_root)
    precons = sorted(
        str(p.relative_to(root)) for p in (root / "data" / "decks" / "precons").glob("*.json")
    )
    targets = sorted(str(p.relative_to(root)) for p in (root / "data" / "decks").glob("*.json"))
    opponents = sorted(
        str(p.relative_to(root)) for p in (root / "data" / "opponents").rglob("*.json")
    )
    return {"precons": precons, "targets": targets, "opponents": opponents}
