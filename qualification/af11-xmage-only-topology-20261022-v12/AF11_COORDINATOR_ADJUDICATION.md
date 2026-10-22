# AF11: Coordinator re-adjudication for XMage pin 4da83f62, XMage-only topology

**Date:** 2026-10-22.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261021-v11/` (`456b0e22`). That record remains the adjudication of every epoch run on `456b0e22`.

## Why a new record

Repin v12 moved the pin to `4da83f62` (moeendres-png/mage, four commits on `456b0e22`, engine version 1.4.62). The prior record says a pin change invalidates it. PB-03 run 39835727421 on main `5a002f0a` (epoch `5a002f0accd4-8f74b1efcce7`, sealed by the PR that carries this record) reports FULL107 107/107 and AF00–AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --shortstat 456b0e22 4da83f62` is 35 files, 173 insertions, 48 deletions: the creation order of the tokens of one event, insertion-order collections in the event and effect classes, the fixed player order in 18 cards, and their tests. No upstream merge, no perf port. The diff contains no `pom.xml` and no `LICENSE` file; XMage stays MIT.
- **Lab dependencies (engine-bridge/pom.xml):** no commit since the v9 repin; `xmage.version` stays 1.4.62. The classpath inventory is the 28-jar one recorded for `043579bb`, unchanged because no engine or bridge `pom.xml` changed. Measured on the sealed epoch: the launch classpath recorded in `MIDGAME_REPLAY_TWIN_EXECUTIONS.json` (PB-03 run 39835727421) lists exactly these 28 jars. The assembler compares the inventory with the run's classpath on each run.

## Decision

The three decisions hold for `4da83f62`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `5a002f0accd4-8f74b1efcce7`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00–AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.
