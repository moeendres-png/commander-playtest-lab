# Precon import with the v14 candidate (2026-10-29)

Refs #979. Measurement of the deck import of all precon decks with the bridge jar built against
XMage pin 2ec507b721 (v14: 21 more Commander precon cards built for real, plus the Sage of the
Maze untap cost and two insertion-order fixes). LOCAL_OBSERVED: no CI-level credit.

| Item | Value |
| --- | --- |
| Jar sha256 | `035a5b4e6ff6ff2911d0b49ff070e4c9e9b0df501539bcc32462b832f3fef3a0` |
| Decks in `data/decks/precons` | 173 (all REAL, the printed decks) |
| Imported | 173 |
| Not imported | 0 (0 infrastructure errors) |
| Wall time | 36.8 s |
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

## Identity against v13

Both comparisons play the same games with the v13 jar (pin 90f5c4d3f8, tree of Lab `5d85d2dc4`)
and the v14 jar (pin 2ec507b721, same pilot): same seeds, same pods, same pilot code.

| Gate | Result |
| --- | --- |
| 36 real-pod seeds (`benchmark_xmage_full_games.py compare`, reference `real36_main_5d85d2dc4_run1.json`) | `identical 36/36`, no abort |
| 44 precon pods on the pool of v13 (164 real decks + 9 SYNTHETIC proxies, plan seed 1, game seed 1) | 44 of 44 ok in both runs; semantic hash and winner equal in 44 of 44 |
| 44 precon pods on the 173 real decks (v14 only, plan seed 1, game seed 1) | 44 of 44 ok, 0 failed |

The hashes did not move although the pin changes engine classes (the object orders of
`SacrificeAllEffect` and Chaos Mutation, Sage of the Maze, phasing events): none of the played
games reaches a state where they differ. That is an observation of these 80 games, not a proof
for other decks. Files: `real36_v14_pin2ec507b721_run1.json`, `precon44_v13_pin90f5c4d3f8_sweep.json`,
`precon44_v14_pin2ec507b721_sweep.json`, `precon44_v14_pin2ec507b721_real173_sweep.json`,
`precon_import_v14_pin2ec507b721.json` (all in `docs/performance/measurements-2026-10-29/`).
Wall times of these runs are not a speed claim (the runs were taken one after the other while
other work used the machine).
