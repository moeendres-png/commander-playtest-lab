# Precon import with the v14 candidate (2026-10-29)

Refs #979. Measurement of the deck import of all precon decks with the bridge jar built against
XMage pin 2ec507b721 (v14: 21 more Commander precon cards built for real, plus the Sage of the
Maze untap cost and two insertion-order fixes). LOCAL_OBSERVED: no CI-level credit.

| Item | Value |
| --- | --- |
| Jar sha256 | `480ed3d2b274546cc1af99543f1d906995958629ee7fdfdc2bb570cfa2238146` |
| Decks in `data/decks/precons` | 173 (all REAL, the printed decks) |
| Imported | 173 |
| Not imported | 0 (0 infrastructure errors) |
| Wall time | 64.9 s |
| Before (pin 90f5c4d3, v13) | 164 of 173 real decks imported, 9 did not |

The nine decks that this repin makes importable: `2023_blast_from_the_past` (Susan Foreman),
`2023_masters_of_evil` (Missy and eight more Doctor Who cards), `2023_paradox_power` (The
Foretold Soldier and two more), `2023_timey_wimey` (The Pandorica and more), `2024_blame_game`
(Feather, Radiant Arbiter; Immortal Obligation), `2024_revenant_recon` (Eye of Duskmantle),
`2024_tricky_terrain` and its collector's edition (Desert Warfare), `2026_odds_and_ends`
(Exchange of Words; Space Beleren).

The nine SYNTHETIC proxy decks of #982 (`data/decks/precon_variants/`) stood in for exactly
these decks. With real decks available they are no longer needed in new measurements; the
proxies, their list and the pool tests are retired in a follow-up change after the requalification
of this pin, so that the pool figure moves once and with its own evidence. Old measurements keep
the pool they were taken on.
