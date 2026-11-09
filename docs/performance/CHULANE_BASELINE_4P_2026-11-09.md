# Chulane baseline in the three standard 4P pods (2026-11-09)

Refs #1070. Measurement only: no bridge, fork, pin, pilot, deck or sealed record changes, so nothing here
needs requalification. It answers the "new exact-HEAD XMage full-game validation" item of
`docs/OWNER_DECK_FOCUS_CURRENT.md` for the recorded Chulane baseline and gives later candidate
comparisons something to start from. Evidence class `LOCAL_OBSERVED`, exploratory fixed seat, no CI
credit, not a win-rate estimate.

## 1. What was run

| | |
|---|---|
| Lab commit | `fac1782e7` (`main` after #1147). `engine-bridge/` and `src/` are identical to `5bd29ab6f`, from which the jar below was built |
| XMage pin | `f4d12f6e80` (`config/rules_engines.json`, repin v15) |
| Bridge jar | sha256 `36167ba71e480c6c85f95df3bd24feac5a75c94d0752e71f25544a861c9064a7` (the jar of the 2026-11-08 reference) |
| Deck | `data/decks/deckbau/chulane_current.json` (`custom/chulane`, baseline of 2026-10-31), seat 1 |
| Pods | `mixed`, `precon`, `optimized` of `scripts/deckbau_eval.py` (opponents fixed in the script, see `DECKBAU_INTERFACE.md` section 4) |
| Seeds | 1-12 per pod, 36 games, one JVM per game |
| Command | `python scripts/deckbau_eval.py --deck data/decks/deckbau/chulane_current.json --pod POD --seeds 1-12 --jar JAR --out OUT` |
| Machine | 4 cores. `mixed` and `precon` ran at the same time (two JVMs), `optimized` ran alone afterwards |
| Files | `docs/performance/measurements-2026-11-09/chulane_{mixed,precon,optimized}_seeds1-12_fac1782e7.json` (the local deck path in `plan.deck` was made repo-relative, nothing else changed) and `chulane_readiness_fac1782e7.json` |

Readiness gate first: Chulane is `READY` (83 distinct cards `OK`, 0 `NO_CARD_FACTS`, 0
`NO_PILOT_KNOWLEDGE`, 0 `KNOWN_MISSING_IN_XMAGE`); `deckbau_pool_readiness.py` reports 177 of 177 ready.

## 2. Result

36 of 36 games reached a terminal state in XMage: no abort, no timeout, no engine failure.

| Pod (seats 2-4) | Chulane wins | Other wins | Mean rounds | Decisions per game (median) | Wall per game (median / max) |
|---|---|---|---|---|---|
| `mixed` (Kaervek, Animated Army, Lorehold Spirit) | 2 (seeds 3, 10) | Kaervek 1, Animated Army 0, Lorehold Spirit 9 | 11.75 | 3389 | 41.7 s / 58.1 s |
| `precon` (Lorehold Spirit, Animated Army, Token Triumph) | 3 (seeds 1, 6, 10) | Lorehold Spirit 3, Animated Army 2, Token Triumph 3, 1 draw | 13.19 | 4313 | 50.2 s / 66.9 s |
| `optimized` (Eldrazi Unbound, Kaervek, Hosts of Mordor) | 0 | Eldrazi Unbound 1, Kaervek 1, Hosts of Mordor 10 | 12.29 | 3134 | 33.2 s / 76.2 s |

Chulane won 5 of 36 games (a fair four-player share would be 9). With 36 games and one fixed seat the
interval is wide (Wilson 95 %: 6 % to 29 %), and in two of the three pods one opponent won 9 or 10 of 12
games, so **the win rate stays UNDECIDED**. These are counts, not an estimate, and not a power ranking.

The draw (`precon`, seed 3) is an XMage rule, not an engine failure: Chulane was out on turn 45, Token
Triumph on turn 39, and the two remaining opponents (Lorehold Spirit, Animated Army) kept passing
until XMage asked both "Draw game because of infinite looping?" and both pilots answered yes. Chulane
was not involved. Replaying that seed reproduced the same semantic hash
(`d2ae7aba156a111cb669a36aaad78d5e14abe8e2ad39ccfd951b9d627fd5c1e1`).

## 3. Chulane seat, all 36 games

- Spells cast 924 in 456 own turns (2.03 per own turn; a proxy, not mana efficiency).
- Commander first cast in round 4 to 7 in 33 games (median 6), round 10 once, round 15 once, never once
  (`precon` seed 5, the game ended in round 7.25). Chulane was cast 92 times in total (bounce and recast).
- Mulligans 12 in 36 games. Cancelled mana payments 2 (Wavesifter, Bennie Bracks). Main phase passed with a
  castable spell 1 time. Needless chump blocks 26. Attacks into a killer 0, removal on an own permanent 0,
  wipes cast while ahead 0. Offers without pilot knowledge 24 of 5248.
- Time inside the pilot: 23 s in 36 games.

## 4. Cards castable but not cast (a pilot signal, not a card verdict)

Games in which the card was castable at least once and was never cast, among the games in which it was
castable (Chulane seat, 36 games):

Wood Elves 14 of 18, Whirler Rogue 11 of 13, Wilderness Reclamation 11 of 16, Open the Armory 9 of 20,
Adrix and Nev 8 of 17, Angel of Finality 8 of 15, Cloudblazer 8 of 14, Environmental Scientist 8 of 18,
Noxious Newt 8 of 17, Talisman of Curiosity 8 of 12, Rampant Growth 7 of 8, Nature's Lore 6 of 15,
Springbloom Druid 6 of 15.

This says how the current pilot spends its mana, not how good the card is. Do not cut a card from this
list alone; the cause (pilot ranking, mana hold for instants, ramp ordering) is not analysed here. Every card that was castable at least three times was cast at
least once somewhere in the 36 games.

## 5. Not measured, not claimed

- Exact mana spent against available and hand residence time: `NOT_MEASURED` (the observer records cast
  opportunities, not hand entry and exit).
- Seat rotation: Chulane always sat in seat 1. A paired candidate comparison needs
  `scripts/run_full_game_deck_comparison.py` with the seat-rotated runner.
- Five or six players: unverified; the Deckbau CLI plays four.
- Hidden-information audit, the independent combo-rule review and the EDHREC card reviews of the focus
  document: not part of this run, still open.
- Speed: the pods ran with different machine load; the wall times are not a speed claim.

## 6. Use

A later candidate (`data/decks/deckbau/chulane_vN.json`) is run with the same command, pods and seeds and
compared against the files above (decisions, casts, cancelled payments, the list in section 4). For a win
claim use the paired comparison. The files hold the semantic hash of every game, so a rerun on the same
jar and deck must reproduce them; a changed hash after a pilot or bridge change is expected and is not a
defect by itself.
