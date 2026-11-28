"""Commander Studio: the shared data contract for BUILD, PLAY and SIMULATE.

See ``docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md``. This package holds the
local store (collection, deck revisions, source observations) and its importers. It contains
no Magic rules: deck checks here are data checks, and the pinned Rules Core stays the only
authority on legality in a game.
"""

from .backup import backup_before_migration
from .decks import DeckIssue, RevisionCard, create_revision, lab_snapshot, validate_revision
from .store import DataClass, StudioStore, register_migration_backup, studio_data_dir

# The store cannot import ``backup`` (it imports the store); the package wires them (#1703).
register_migration_backup(backup_before_migration)

__all__ = [
    "DataClass",
    "DeckIssue",
    "RevisionCard",
    "StudioStore",
    "create_revision",
    "lab_snapshot",
    "studio_data_dir",
    "validate_revision",
]
