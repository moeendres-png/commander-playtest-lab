# Stop an unchanged exiled-card play cycle

The fixed-seed public-precon campaign failed in `coverage-4p-009` after
50,000 decisions. Its tail repeatedly chose Yes to `Play Plains?` and
`Continue playing the exiled cards?`. The first unchanged Play/Continue pair
is at records 2710–2711, turn 45, from Dungeon of the Mad Mage.

The pinned native implementation is
`Mage/src/main/java/mage/game/command/dungeons/DungeonOfTheMadMageDungeon.java`,
lines 125–142. It asks whether to play each exiled card, invokes `player.cast`,
retains the cards still in exile, then asks whether to continue. The failed
land attempt leaves the observed state unchanged. Repeated agreement keeps
returning to the same card. No Rules Core change or repin is made here.

The pilot remembers the observation fingerprint after agreeing to a `Play …?`
offer with outcome `playforfree`. At the matching continuation question, it
prefers the offered No when game, actor, source, ability, turn and the complete
principal-scoped observation are unchanged. Both boolean options remain
available. A changed observation keeps the ordinary preference, including
after a successful play when another card has the same name. Missing scope
metadata and a missing No alternative also retain the usual behavior.

The fingerprint is a bounded SHA-256 digest, not a retained full observation.
An intervening boolean clears the pending attempt. Intervening non-boolean
requests need not clear it; this is an observed-progress strategy hint, not
proof that every internal engine field stayed unchanged. It contains no land
legality test and does not supply an action or game result.

## Native games and validation

Two complete candidate four-player games use seed 1, the unchanged v14 JAR and
the same ordered public 100-card decks as their references:

| Pod | Reference | Candidate |
| --- | --- | --- |
| `coverage-4p-000`, control | 1,892 decisions, complete | 1,892 decisions, complete, same semantic hash |
| `coverage-4p-009`, problem | 50,000 decisions, failed | 3,006 decisions, native winner seat 2 |

The candidate's first changed selected response is the continuation at record
2711: Yes becomes No. A later native priority observation at record 2721 has
an empty stack, and the game proceeds to its native result. The candidate has
three payment cancellations; this patch addresses the play cycle rather than
claiming their removal.

The problem reference predates the X-reserve predecessor. There are no
multikicker prompts before the stalled cycle, so the predecessor's optional
mana commitments are inactive. Selected option types/labels and numeric
values match up to record 2711. Incidental engine-generated UUIDs inside HTML
prompts differ between runs and are excluded from that content comparison.
The control reference already includes the predecessor. These are scoped
impact checks, not a claim that the failed reference is a complete game.

The isolated regression started with one failure and seven passing controls.
The final focused run passed 98 tests. A broader guarded run passed 232 tests,
including the prior optional-cast, counter-growth, numeric-budget, request
corpus, option-reachability and Any-ratchet regressions. The suites overlap.
Strict mypy passed over 350 source files; Ruff lint and format checks passed
on the explicitly selected public paths. Access guards were installed before
Python test and game imports. Raw records and scratch helpers stay local.

The two changed runtime files match the measured snapshot byte for byte.
Runtime tree digest:
`d1533f51ecde2a5351a64f5d79cc495e564c95bf067910866a311de416c88f4d`.
Engine pin: `2ec507b721ac04834eaa4d553b494681c46d996f`.
JAR SHA-256:
`5fe48fd25ab055fc12fce99aab807d0d045bc5912dfde626d585ff30dedba788`.
Exact deck hashes, source hashes, selected-response evidence and verified
archive checksums are in the
[measurement artifact](measurements-2026-11-05/exiled-play-retry-summary.json).

The failed reference remains FAIL. This does not establish full-pool
qualification, playing strength or a causal wall-time improvement. Local
timings include concurrent jobs.
