# AF11: Coordinator re-adjudication for XMage pin 90f5c4d3f8, XMage-only topology

**Date:** 2026-10-23.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261022-v12/` (`4da83f62`). That record remains the adjudication of every epoch run on `4da83f62`.

## Why a new record

Repin v13 moved the pin to `90f5c4d3f8` (moeendres-png/mage, two commits on `4da83f62`, engine version 1.4.62). The prior record says a pin change invalidates it. PB-03 run 39971772073 on main `8ebc7b24` (epoch `8ebc7b24b143-83f899db7e31`, sealed by the PR that carries this record) reports FULL107 107/107 and AF00–AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --shortstat 4da83f62 90f5c4d3f8` is 24 files, 2398 insertions, 0 deletions: ten Commander precon card classes, their Mage.Tests files and the `SetCardInfo` lines of three Commander sets. No upstream merge, no engine class change. The diff contains no `pom.xml` and no `LICENSE` file; XMage stays MIT.
- **Lab dependencies (engine-bridge/pom.xml):** no commit since the v9 repin; `xmage.version` stays 1.4.62. The classpath inventory is the 28-jar one recorded for `043579bb`, unchanged because no engine or bridge `pom.xml` changed. Measured on the sealed epoch: the launch classpath recorded in `MIDGAME_REPLAY_TWIN_EXECUTIONS.json` (PB-03 run 39971772073) lists exactly these 28 jars. The assembler compares the inventory with the run's classpath on each run.

## Decision

The three decisions hold for `90f5c4d3f8`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `8ebc7b24b143-83f899db7e31`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00–AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.
