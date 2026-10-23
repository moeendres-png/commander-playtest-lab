# Precon import with the v13 candidate (2026-10-23)

Refs #979. Measurement of the deck import of all precon decks with the bridge jar built against
XMage pin 90f5c4d3f8 (v13: ten Commander precon cards built for real, no engine change).
LOCAL_OBSERVED: no CI-level credit.

| Item | Value |
| --- | --- |
| Jar sha256 | `2e65e12e0fc579f2d7774fa709d0f2f1bfa680bf25fa5940072cdb5e425c6573` |
| Decks in `data/decks/precons` | 195 |
| Imported | 186 |
| Not imported | 9 (0 infrastructure errors) |
| Wall time | 49.5 s |
| Before (pin 4da83f62) | 182 real importable decks |

The four decks that this repin makes importable: `2024_death_toll` (Winter, Cynical Opportunist),
`2024_family_matters` (Zinnia, Valley's Voice), `2024_miracle_worker` (Aminatou, Veil Piercer),
`2026_multiverse_reforged` (Jace, Multiverse Architect plus Dack Fayden, Jhoira, Tamiyo,
Teferi's Reproach, The Ur-Sphinx and Venser).

## Decks that still do not import

| Deck | First unknown card |
| --- | --- |
| `2023_blast_from_the_past` | Susan Foreman |
| `2023_masters_of_evil` | Missy (and more) |
| `2023_paradox_power` | The Foretold Soldier (and two more) |
| `2023_timey_wimey` | The Pandorica (and more) |
| `2024_blame_game` | Feather, Radiant Arbiter; Immortal Obligation |
| `2024_revenant_recon` | Eye of Duskmantle |
| `2024_tricky_terrain` | Desert Warfare |
| `2024_tricky_terrain_collector_s_edition` | Desert Warfare |
| `2026_odds_and_ends` | Exchange of Words; Space Beleren |

The SYNTHETIC proxy decks of #982 stand in for the unimportable precons in the pool and are
counted apart from the real decks. The remaining cards are tracked in #979.
