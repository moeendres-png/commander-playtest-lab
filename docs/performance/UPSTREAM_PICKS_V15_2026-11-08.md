# Upstream picks and dependency update with the v15 candidate (2026-11-08)

Refs #1070. Measurements of the fork candidate head `f4d12f6e80` (repin v15): the v14 pin
`2ec507b721` plus twelve upstream XMage commits from the U-1 delta, the cancelled-payment fix
(U-4), Guava 33.7.2-jre and jsoup 1.23.2, and two adaptations of fork code. LOCAL_OBSERVED: no
CI-level credit. The CI-level evidence is the fork `maven.yml` run, the Conformance run of the
repin branch and PB-03 on the merge commit (see the successor lock
`qualification/xmage-upstream-fixes-repin-v15-20261108/SUCCESSOR_SOURCE_LOCK.json`).

## What is in the pin

| Group | Commits | Effect on play |
| --- | --- | --- |
| Verify test fixes | 2 | none (tests only; the BCHR set skip and a verify fix) |
| Ramses and Blood Tyrant loss triggers, Heart-Piercer Manticore reflexive trigger, Irma copiable values, Dark Impostor zcc | 5 | card fixes, rarely reached |
| Last known information of phased-out permanents (damage sources and remaining battlefield lookups) | 2 | engine fix |
| Redirect effects, "this spell can't be copied", `CantBeCopiedSourceEffect` stack lookup | 3 | engine fix |
| Commander damage info on double-faced permanents | 1 | engine fix |
| Cancelled payment keeps the activation status (Convoke, Delve, Improvise; U-4, 36-seed trial run first) | 1 | engine fix, the one that touches payment |
| Guava 33.4.8-jre to 33.7.2-jre, jsoup 1.21.2 to 1.23.2 | 1 | none in play (library versions) |
| Adaptation of Doomsday Confluence and Zinnia, and of `CommanderPlaysCountStateRestoreTest` | 2 | fork code follows the picked fixes |

Not in the pin: JIT or JVM speed flags, the H2 version (1.4.197), the rest of the upstream delta.

## Native qualification (fork CI)

Fork `maven.yml`, `workflow_dispatch` on `claude/trial-ue4-20261031`, run 42081350653, job
`build (17, temurin, jdk)`, head `f4d12f6e80`: Mage.Tests 7618 run, 0 failures, 0 errors, 126
skipped (the v14 pin ran 7586); Mage.Verify 28 run, 0 failures, 0 errors, 8 skipped. The two
Verify failures that the v14 lock carried as baseline-attributed (set BCHR, card Vox) are gone.

## Identity against the reference (LOCAL_OBSERVED)

The measuring worktree held Lab `8cc0d1563` (main plus the HID-01 launch plan) with the pin
literal of the earlier fork head `f8db5f9394`, so the jars carry that literal; the engine classes
are those of the fork head named in each file. The jar of the final pin is built by the
Conformance run and by PB-03.

| Gate | Result |
| --- | --- |
| 36 real-pod seeds with the jar at `f8db5f9394` (before the cancelled-payment fix) | 36 of 36 ok; semantic hash and winner equal to `real36_pilot_tiebreak_3578aaa38_run1.json` in 36 of 36 |
| 36 real-pod seeds with the jar at the candidate head | 36 of 36 ok; equal to the run above and to the same reference in 36 of 36 |
| 173 real precon decks import with the candidate head | 173 imported, 0 failed, 31.8 s |
| 44 precon pods on the 173 real decks (plan seed 1, game seed 1), v14 jar against candidate head | 44 of 44 ok in both; semantic hash and winner equal in 44 of 44 |

The hashes did not move although the pin changes engine classes (payment, copy and phasing
paths). That is an observation of these 80 games, not a proof for other decks or states: none of
the played games reaches a state where the picked fixes differ. The Lab pilot changes of main
since the 2026-10-31 reference move other hashes; the 36-seed reference is rerun after the
requalification, so this gate compares jars on the same Lab code, not Lab commits.

Files in `docs/performance/measurements-2026-11-08/`: `real36_S_pin_f8db5f9394_run1.json`,
`real36_T_candidate_head_run1.json`, `precon_import_candidate_head.json`,
`precon44_real173_candidate_head_sweep.json`, `precon44_real173_v14_pin2ec507b721_sweep.json`,
`speed_same_db_summary.json`.

## Dependencies

`scripts/report_java_dependencies.py` on the jars (table `checked_on` 2026-10-31):

| Jar | ADVISORY_OPEN | CHECKED_CLEAN | UNKNOWN |
| --- | --- | --- | --- |
| v14 jar (Guava 33.4.8-jre, jsoup 1.21.2) | 3 libraries: Guava (HIGH), jsoup (HIGH, MODERATE), H2 1.4.197 (two console advisories, CRITICAL) | 7 | 4 |
| candidate head (Guava 33.7.2-jre, jsoup 1.23.2) | 1 (H2 1.4.197, console advisories, not reachable: nothing starts the console) | 7 | 6 |

Guava and jsoup change from ADVISORY_OPEN to UNKNOWN because the table lists their advisories
and no clean entry for the fixed versions; UNKNOWN is not a pass. The AUTO_SERVER exposure of H2
is addressed in the launch plan (`-Dh2.bindAddress=127.0.0.1`, HID-01), not in this pin.

## Speed hygiene (lesson)

A first comparison of the candidate jar against the v14 jar showed about 38 percent more wall
time. The cause was the card database file (`.runtime/engine/db/cards.h2.mv.db`) of the measuring
worktree (120 MB, differently built), not the fork code: the v14 source rebuilt on that worktree
was as slow (22.7 s per game), and the candidate head with the 283 MB database of the v14 check
worktree needed 17.5 s per game against 17.4 s for the v14 jar. Speed comparisons are valid only
interleaved and on the same card database copy. `speed_same_db_summary.json` lists the single
runs; it is not a speed claim for the pin.
