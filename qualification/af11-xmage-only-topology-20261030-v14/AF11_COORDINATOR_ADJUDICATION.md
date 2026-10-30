# AF11: Coordinator re-adjudication for XMage pin 2ec507b721, XMage-only topology

**Date:** 2026-10-30.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261023-v13/` (`90f5c4d3`). That record remains the adjudication of every epoch run on `90f5c4d3`.

## Why a new record

Repin v14 moved the pin to `2ec507b721` (moeendres-png/mage, four commits on `90f5c4d3`, engine version 1.4.62). The prior record says a pin change invalidates it. PB-03 run 40978379943 on main `d96c6bf0` (epoch `d96c6bf05309-1e96b5a9728b`, sealed by the PR that carries this record) reports FULL107 107/107 and AF00–AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --shortstat 90f5c4d3f8 2ec507b721` is 62 files, 5435 insertions, 63 deletions: 21 Commander precon card classes with their Mage.Tests files, the `SetCardInfo` lines of four sets, a few new effect and event classes and small edits in `Mage/` for the Doctor Who mechanics, the Sage of the Maze untap cost and two insertion-order fixes. No upstream merge. The diff contains no `pom.xml` and no `LICENSE` file; XMage stays MIT. Unlike v13 the pin does change engine classes; none of them touches licence, topology or the process boundary.
- **Lab dependencies (engine-bridge/pom.xml):** no commit since the v9 repin; `xmage.version` stays 1.4.62. The classpath inventory is the 28-jar one recorded for `043579bb`, unchanged because no engine or bridge `pom.xml` changed. Measured on the sealed epoch: the launch classpath recorded in `MIDGAME_REPLAY_TWIN_EXECUTIONS.json` (PB-03 run 40978379943) lists exactly these 28 jars. The assembler compares the inventory with the run's classpath on each run.

## Decision

The three decisions hold for `2ec507b721`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `d96c6bf05309-1e96b5a9728b`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00–AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.
