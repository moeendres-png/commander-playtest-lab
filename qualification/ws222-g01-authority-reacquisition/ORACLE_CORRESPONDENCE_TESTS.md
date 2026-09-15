# WS222 ORACLE_CORRESPONDENCE_TESTS

Secondary sources (Scryfall API; by extension MTGJSON/engine DBs) are
comparison/discovery/cross-check/identifier-bridge ONLY — never authority
(R-ART-2). The following bounded 8-identity sample (2026-09-15, live Scryfall
vs WS222 official field snapshot, normalized comparison) demonstrates
correspondence, not source authority:

| Identity | Result | Detail |
|----------|--------|--------|
| Ishai, Ojutai Dragonspeaker | EXACT (normalized), jaccard 1.000 | — |
| Rograkh, Son of Rohgahh | EXACT, 1.000 | — |
| Dig Through Time | EXACT, 1.000 | — |
| Path of Ancestry | EXACT, 1.000 | — |
| Narset, Parter of Veils | EXACT, 1.000 | U+2212 loyalty minus both sides after normalization |
| Jeska, Thrice Reborn | EXACT, 1.000 | same minus normalization |
| Wear // Tear | CORRESPONDS (token multiset 1.000) | Structural join artifact only: Scryfall per-face texts vs Gatherer combined "A // B // Fuse" text; same tokens |
| Vandalblast | CORRESPONDS (0.920) | Cost-brace rendering delta only: Scryfall `{4}{R}` vs official `{4R}`; identical cost semantics |

No Oracle conflict found in the sample. Deltas are rendering/transport
(hyphen/minus, brace packing, face-join structure), never rules substance.
Accordingly: secondary bulk transport MAY serve as a convenience layer under
Model C (official per-card proof + separately versioned secondary transport,
authority/transport explicitly separated), but no secondary snapshot is granted
authority by these tests. `data/cards/oracle_subset.json` remains
`authoritative_oracle_snapshot = false` (out of WS222 scope to change).

Machine companion: `ORACLE_CORRESPONDENCE_TESTS.json`.
Evidence class: DIRECTLY_VERIFIED (live secondary vs sealed official snapshot).
Rerun: manual/bounded (network); repo CI validates only offline snapshot
integrity (see `tests/qualification/test_ws222_authority.py`).
