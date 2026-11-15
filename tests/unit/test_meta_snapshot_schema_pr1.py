"""Meta-Lane PR1: snapshot schema extension (all new fields optional).

Covers docs/meta/PROVENANCE_HEADER.md and src/commander_lab/models/meta.py:
new provenance fields validate, old snapshots still validate unchanged, and
the new fields do not change the functional meta profile (no scoring change).
"""

from __future__ import annotations

COMMANDER = "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh"
# Stable hash of the three-card list below (sorted, casefolded, sha256 of the JSON list).
DECK_HASH = "6005593206d664b77ee02cd16c9c7d445111eeba9e9e4d9d5310f51955b15330"
